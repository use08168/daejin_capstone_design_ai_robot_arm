"""
OpenCV 웹캠 캡처 → MJPEG 스트림.

핵심 설계: 카메라마다 **백그라운드 스레드 하나가 장치를 점유**하고 최신 프레임을
공유 버퍼에 보관한다. HTTP 스트림(여러 클라이언트/탐지 토글)은 이 공유 프레임만
읽으므로, 같은 카메라를 중복으로 열다 충돌하는 문제(DSHOW C++ 예외)가 사라진다.
"""
import threading
import time

import cv2

# Windows 에선 CAP_DSHOW 백엔드가 열기가 빠르고 안정적
_BACKEND = cv2.CAP_DSHOW


class _CameraThread:
    """카메라 1대를 점유하고 최신 프레임을 계속 갱신하는 스레드."""

    def __init__(self, index: int, width: int = 1280, height: int = 720):
        self.index = index
        self.width = width
        self.height = height
        self._frame = None
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _open(self):
        cap = cv2.VideoCapture(self.index, _BACKEND)
        if cap.isOpened():
            # 설정은 실패해도 무시(일부 DSHOW 장치에서 예외 발생 가능)
            for prop, val in (
                (cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")),
                (cv2.CAP_PROP_FRAME_WIDTH, self.width),
                (cv2.CAP_PROP_FRAME_HEIGHT, self.height),
            ):
                try:
                    cap.set(prop, val)
                except cv2.error:
                    pass
            return cap
        cap.release()
        return None

    def _loop(self):
        """자가 치유 루프: 열기에 실패하거나(다른 프로세스가 점유 중 등)
        프레임이 끊기면 카메라를 닫고 주기적으로 다시 연다."""
        cap = None
        miss = 0
        while self._running:
            if cap is None:
                cap = self._open()
                if cap is None:
                    time.sleep(1.0)   # 점유 중일 수 있음 → 잠시 후 재시도
                    continue
            try:
                ok, frame = cap.read()
            except cv2.error:
                ok, frame = False, None
            if not ok:
                miss += 1
                if miss > 30:         # 장시간 프레임 없음 → 재오픈
                    cap.release()
                    cap = None
                    miss = 0
                time.sleep(0.05)
                continue
            miss = 0
            with self._lock:
                self._frame = frame
        if cap is not None:
            cap.release()

    def read(self):
        """최신 프레임 복사본 반환 (없으면 None)."""
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def stop(self):
        self._running = False


# 인덱스별 카메라 스레드 캐시
_cameras = {}
_cameras_lock = threading.Lock()


def get_camera(index: int) -> _CameraThread:
    with _cameras_lock:
        cam = _cameras.get(index)
        if cam is None:
            cam = _CameraThread(index)
            _cameras[index] = cam
        return cam


def list_cameras(max_index: int = 6):
    """열리는 카메라 인덱스 목록을 반환. 이미 스레드가 점유 중인 인덱스는
    충돌을 피하려고 다시 열지 않고 프레임 유무로 판단한다."""
    found = []
    for i in range(max_index):
        cam = _cameras.get(i)
        if cam is not None:
            if cam.read() is not None:
                found.append(i)
            continue
        cap = cv2.VideoCapture(i, _BACKEND)
        ok = cap.isOpened()
        if ok:
            # 막 열린 카메라는 첫 프레임이 늦으므로 잠시 워밍업하며 재시도
            got = False
            for _ in range(15):  # 최대 ~0.75s
                try:
                    r, _f = cap.read()
                except cv2.error:
                    r = False
                if r and _f is not None:
                    got = True
                    break
                time.sleep(0.05)
            ok = got
        cap.release()
        if ok:
            found.append(i)
    return found


def camera_names():
    """DirectShow 장치 이름 목록(인덱스 = 위치). pygrabber 없으면 None."""
    try:
        from pygrabber.dshow_graph import FilterGraph
        return FilterGraph().get_input_devices()
    except Exception:
        return None


# ---- 좌/우 카메라 선택 설정 (서버 저장) ----
import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "cam_config.json")
_DEFAULT_CFG = {"left": 2, "right": 1}


def get_config():
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            c = json.load(f)
        return {"left": int(c.get("left", 2)), "right": int(c.get("right", 1))}
    except Exception:
        return dict(_DEFAULT_CFG)


def set_config(left, right):
    cfg = {"left": int(left), "right": int(right)}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return cfg


def _draw_crosshair(frame):
    """화면 정중앙에 십자선 표시."""
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    color = (0, 0, 0)  # 검은색
    gap, arm = 8, 18
    cv2.line(frame, (cx - gap - arm, cy), (cx - gap, cy), color, 1, cv2.LINE_AA)
    cv2.line(frame, (cx + gap, cy), (cx + gap + arm, cy), color, 1, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - gap - arm), (cx, cy - gap), color, 1, cv2.LINE_AA)
    cv2.line(frame, (cx, cy + gap), (cx, cy + gap + arm), color, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 2, color, -1, cv2.LINE_AA)


def mjpeg_frames(index: int, detect: bool = False, charuco: bool = False, fps: int = 20):
    """multipart/x-mixed-replace 용 JPEG 프레임 제너레이터.

    detect=True  → YOLO 박스 오버레이.
    charuco=True → ChArUco 코너/마커 오버레이(캘리브레이션 촬영용).
    """
    cam = get_camera(index)
    interval = 1.0 / fps

    # 첫 프레임 대기 (최대 ~5초)
    t0 = time.time()
    while cam.read() is None and time.time() - t0 < 5.0:
        time.sleep(0.1)

    annotate = None
    if charuco:
        from .charuco import annotate as _ann
        annotate = lambda f: _ann(f)[0]
    elif detect:
        from .detector import annotate as annotate

    while True:
        frame = cam.read()
        if frame is None:
            time.sleep(0.1)
            continue
        if annotate is not None:
            frame = annotate(frame)
        _draw_crosshair(frame)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )
        time.sleep(interval)
