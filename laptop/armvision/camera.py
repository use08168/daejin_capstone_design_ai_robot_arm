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

    def _loop(self):
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
        while self._running:
            if not cap.isOpened():
                time.sleep(0.5)
                continue
            try:
                ok, frame = cap.read()
            except cv2.error:
                ok, frame = False, None
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame = frame
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
