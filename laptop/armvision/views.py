import datetime
import os
import shutil

import cv2
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from . import charuco, markers, stereo3d
from .camera import get_camera, get_config, mjpeg_frames
from .detector import detections as detect_objects

CAPTURE_DIR = r"C:\robotic_arm\laptop\calibration\captures"
COLDSTART_PATH = r"C:\robotic_arm\laptop\calibration\coldstart_data.json"


def _cams():
    """현재 설정된 (좌, 우) 카메라 인덱스."""
    c = get_config()
    return c["left"], c["right"]


# ============ 페이지 ============

def index(request):
    """1페이지 — 라이브 카메라 + 객체 탐지. 캘리브레이션되면 3D 자동 활성화."""
    cfg = get_config()
    return render(request, "armvision/index.html", {
        "calibrated": stereo3d.is_calibrated(),
        "cam_left": cfg["left"], "cam_right": cfg["right"],
    })


def cameras_list(request):
    """노트북의 카메라 목록 + 현재 좌/우 선택.

    DirectShow 장치 목록(pygrabber)을 우선 사용 — 카메라를 열지 않으므로
    여러 웹캠을 동시에 점유하다 일부를 놓치는 문제가 없다.
    pygrabber 없을 때만 인덱스를 직접 열어보며 탐색(fallback).
    """
    from .camera import camera_names, list_cameras
    names = camera_names()
    if names:
        cams = [{"index": i, "name": n} for i, n in enumerate(names)]
    else:
        cams = [{"index": i, "name": f"카메라 {i}"} for i in list_cameras()]
    cfg = get_config()
    return JsonResponse({"cameras": cams, "left": cfg["left"], "right": cfg["right"]})


@csrf_exempt
def cameras_config(request):
    """좌/우 카메라 선택 저장(POST) 또는 조회(GET)."""
    from .camera import set_config
    if request.method == "POST":
        import json
        d = json.loads(request.body.decode("utf-8"))
        cfg = set_config(d.get("left"), d.get("right"))
        return JsonResponse({"ok": True, **cfg})
    return JsonResponse(get_config())


def setup(request):
    """2페이지 — 6단계 캘리브레이션 위저드."""
    cam_left, cam_right = _cams()
    return render(request, "armvision/setup.html",
                  {"cam_left": cam_left, "cam_right": cam_right})


def control(request):
    """3페이지 — 자연어 제어(골격, 추후 구현)."""
    return render(request, "armvision/control.html")


def arm3d(request):
    """4페이지 — 3D 로봇팔 제어 뷰어(3D-only, 실물 연동 예정)."""
    return render(request, "armvision/arm3d.html")


CAD_DIR = r"C:\robotic_arm\laptop\cad"


def cad_list(request):
    """cad 폴더의 STL 파일 목록."""
    files = []
    if os.path.isdir(CAD_DIR):
        files = sorted(f for f in os.listdir(CAD_DIR) if f.lower().endswith(".stl"))
    return JsonResponse({"files": files})


def cad_file(request, name):
    """cad STL 파일 서빙 (Three.js STLLoader 용)."""
    from django.http import FileResponse, Http404
    safe = os.path.basename(name)
    path = os.path.join(CAD_DIR, safe)
    if not os.path.isfile(path):
        raise Http404("not found")
    return FileResponse(open(path, "rb"), content_type="application/octet-stream")


ASSEMBLY_PATH = os.path.join(CAD_DIR, "assembly.json")


def arm3d_load(request):
    """저장된 조립/리깅 설정 반환 (없으면 빈 객체)."""
    import json
    if os.path.isfile(ASSEMBLY_PATH):
        with open(ASSEMBLY_PATH, encoding="utf-8") as f:
            return JsonResponse(json.load(f))
    return JsonResponse({})


# ============ 실물 로봇팔 연동 (시리얼) ============

def arm_status(request):
    from . import arduino_bridge
    return JsonResponse(arduino_bridge.status())


@csrf_exempt
def arm_connect(request):
    import json
    from . import arduino_bridge
    d = json.loads(request.body.decode("utf-8")) if request.body else {}
    port = d.get("port") or "COM9"
    baud = int(d.get("baud") or 115200)
    try:
        return JsonResponse(arduino_bridge.connect(port, baud))
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


@csrf_exempt
def arm_disconnect(request):
    from . import arduino_bridge
    return JsonResponse(arduino_bridge.disconnect())


@csrf_exempt
def arm_move(request):
    """{'joints':[{'channel','us'},...]} 또는 {'channel','us'} 펄스 전송."""
    import json
    from . import arduino_bridge
    try:
        d = json.loads(request.body.decode("utf-8"))
        if "joints" in d:
            return JsonResponse(arduino_bridge.send_many(d["joints"]))
        return JsonResponse(arduino_bridge.send_pulse(d["channel"], d["us"]))
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


@csrf_exempt
def arm3d_save(request):
    """조립/리깅 설정을 서버 JSON 파일에 저장."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"})
    os.makedirs(CAD_DIR, exist_ok=True)
    with open(ASSEMBLY_PATH, "w", encoding="utf-8") as f:
        f.write(request.body.decode("utf-8"))
    return JsonResponse({"ok": True})


# ============ 스트림 ============

def video_feed(request):
    try:
        cam = int(request.GET.get("cam", 0))
    except ValueError:
        cam = 0
    detect = request.GET.get("detect") in ("1", "true", "on")
    cha = request.GET.get("charuco") in ("1", "true", "on")
    return StreamingHttpResponse(
        mjpeg_frames(cam, detect=detect, charuco=cha),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )


# ============ 탐지 / 3D ============

def detections_json(request):
    try:
        cam = int(request.GET.get("cam", 0))
    except ValueError:
        cam = 0
    frame = get_camera(cam).read()
    if frame is None:
        return JsonResponse({"cam": cam, "objects": [], "error": "no frame"})
    objs = detect_objects(frame)
    for o in objs:
        o["center"] = [round(o["center"][0], 1), round(o["center"][1], 1)]
        o["bbox"] = [round(v, 1) for v in o["bbox"]]
        o["conf"] = round(o["conf"], 2)
    h, w = frame.shape[:2]
    return JsonResponse({"cam": cam, "width": w, "height": h, "count": len(objs), "objects": objs})


def positions3d_json(request):
    if not stereo3d.is_calibrated():
        return JsonResponse({"calibrated": False, "objects": []})
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    if fL is None or fR is None:
        return JsonResponse({"calibrated": True, "objects": [], "error": "no frame"})
    objs = stereo3d.match_and_triangulate(detect_objects(fL), detect_objects(fR))
    return JsonResponse({"calibrated": True, "count": len(objs), "objects": objs})


# ============ 캘리브레이션 위저드 ============

def _capture_count():
    if not os.path.isdir(CAPTURE_DIR):
        return 0
    return len([f for f in os.listdir(CAPTURE_DIR) if f.endswith("_L.png")])


def setup_state(request):
    """위저드 진행 상태."""
    return JsonResponse({
        "captures": _capture_count(),
        "calibrated": stereo3d.is_calibrated(),
    })


def capture_pair(request):
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    if fL is None or fR is None:
        return JsonResponse({"error": "프레임 없음"})
    nL, nR = charuco.count(fL), charuco.count(fR)
    idx = _capture_count() + 1
    cv2.imwrite(os.path.join(CAPTURE_DIR, f"pair_{idx:02d}_L.png"), fL)
    cv2.imwrite(os.path.join(CAPTURE_DIR, f"pair_{idx:02d}_R.png"), fR)
    return JsonResponse({"saved": idx, "cornersL": nL, "cornersR": nR,
                         "ok": nL >= charuco.MIN_GOOD and nR >= charuco.MIN_GOOD})


def calibrate_status(request):
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    return JsonResponse({
        "cornersL": charuco.count(fL) if fL is not None else 0,
        "cornersR": charuco.count(fR) if fR is not None else 0,
        "min_good": charuco.MIN_GOOD, "max": charuco.MAX_CORNERS,
        "captures": _capture_count(),
    })


def run_calibration(request):
    from calibration import calibrate_stereo
    res = calibrate_stereo.run()
    if res.get("ok"):
        stereo3d.reload()
    return JsonResponse(res)


def run_validation(request):
    from calibration import validate_triangulation
    return JsonResponse(validate_triangulation.run())


def marker_status(request):
    """양 카메라에서 보이는 로봇 ArUco 마커 id 목록 + 베이스(id0) 동시 검출 여부."""
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    if fL is None or fR is None:
        return JsonResponse({"left": [], "right": [], "base_ok": False, "error": "프레임 없음"})
    st = markers.marker_status(fL, fR)
    st["base_ok"] = (markers.BASE_ID in st["left"] and markers.BASE_ID in st["right"])
    st["has_T"] = markers.has_transform()
    return JsonResponse(st)


@csrf_exempt
def coldstart_save(request):
    """스윕으로 모은 {자세 관절각, 마커 3D} 데이터셋 저장 + 엔드이펙터 마커로 작업공간 산출."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"})
    import json
    import math
    data = json.loads(request.body.decode("utf-8"))
    poses = data.get("poses", [])

    all_ids = set()
    for p in poses:
        for k in p.get("markers", {}):
            all_ids.add(int(k))
    ws = None
    if all_ids and poses:
        ee = max(all_ids)                        # 가장 끝(엔드이펙터) 마커
        # J1 회전축 = id1 평균 위치 (로봇팔의 실제 중심축). 없으면 원점(id0) 기준.
        id1 = [p["markers"].get("1") for p in poses if p.get("markers", {}).get("1")]
        if id1:
            cx = sum(v[0] for v in id1) / len(id1)
            cy = sum(v[1] for v in id1) / len(id1)
            cz = sum(v[2] for v in id1) / len(id1)
            axis_spread = round(max(math.hypot(v[0] - cx, v[1] - cy) for v in id1), 1)
            axis_id, axis = 1, [round(cx, 1), round(cy, 1), round(cz, 1)]
        else:
            cx = cy = cz = 0.0
            axis_spread, axis_id, axis = None, 0, [0, 0, 0]
        pts = [p["markers"].get(str(ee)) for p in poses if p.get("markers", {}).get(str(ee))]
        if pts:
            # J1 축 기준 상대좌표 + 수평 도달거리
            xs = [v[0] - cx for v in pts]; ys = [v[1] - cy for v in pts]; zs = [v[2] - cz for v in pts]
            reach = [math.hypot(v[0] - cx, v[1] - cy) for v in pts]
            ws = {"ee_id": ee, "axis_id": axis_id, "axis": axis, "axis_spread": axis_spread,
                  "n": len(pts),
                  "x": [round(min(xs), 1), round(max(xs), 1)],
                  "y": [round(min(ys), 1), round(max(ys), 1)],
                  "z": [round(min(zs), 1), round(max(zs), 1)],
                  "reach_min": round(min(reach), 1), "reach_max": round(max(reach), 1)}
    os.makedirs(os.path.dirname(COLDSTART_PATH), exist_ok=True)
    with open(COLDSTART_PATH, "w", encoding="utf-8") as f:
        json.dump({"poses": poses, "workspace": ws}, f, ensure_ascii=False, indent=1)
    return JsonResponse({"ok": True, "poses": len(poses), "workspace": ws})


def measure_markers(request):
    """현재 프레임에서 공통 마커들을 로봇 기준 3D로 측정 (단계 ⑥ 기본기)."""
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    if fL is None or fR is None:
        return JsonResponse({"ok": False, "error": "프레임 없음"})
    return JsonResponse(markers.measure(fL, fR))


@csrf_exempt
def compute_transform(request):
    """단계 ⑤ — id0 베이스 마커로 카메라→로봇 변환 T 산출·저장."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"})
    cam_left, cam_right = _cams()
    fL = get_camera(cam_left).read()
    fR = get_camera(cam_right).read()
    if fL is None or fR is None:
        return JsonResponse({"ok": False, "error": "프레임 없음"})
    res = markers.compute_base_transform(fL, fR)
    if res.get("ok"):
        stereo3d.reload()   # 새 T 반영 → 이후 3D 좌표가 로봇 기준
    return JsonResponse(res)


@csrf_exempt
def reset_calibration(request):
    """새 환경 캘리브레이션 — 기존 촬영본·캘리브레이션 결과를 타임스탬프 폴더로 **보관(archive)** 하고
    촬영 수를 0으로 초기화한다. 삭제가 아니라 이동이라 `_archive_*` 폴더에서 복구 가능."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST only"})
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1) 촬영본 보관
    moved = 0
    if os.path.isdir(CAPTURE_DIR):
        arch = os.path.join(CAPTURE_DIR, f"_archive_{ts}")
        for f in os.listdir(CAPTURE_DIR):
            if f.endswith("_L.png") or f.endswith("_R.png"):
                os.makedirs(arch, exist_ok=True)
                shutil.move(os.path.join(CAPTURE_DIR, f), os.path.join(arch, f))
                moved += 1

    # 2) 기존 캘리브레이션 결과 보관 → is_calibrated() False → 새로 보정 전까지 3D 비활성
    calib_archived = False
    if os.path.isfile(stereo3d.CAL):
        bak = os.path.join(os.path.dirname(stereo3d.CAL), "_archive")
        os.makedirs(bak, exist_ok=True)
        shutil.move(stereo3d.CAL, os.path.join(bak, f"stereo_calib_{ts}.npz"))
        stereo3d.reload()
        calib_archived = True

    return JsonResponse({"ok": True, "archived_pairs": moved // 2,
                         "calib_archived": calib_archived, "stamp": ts})


# ============ AI 서버(EdgeXpert) 연동 — 3페이지 자연어 제어 ============

def ai_health(request):
    """AI 서버 warm 상태 확인."""
    from . import ai_client
    return JsonResponse(ai_client.health())


@csrf_exempt
def ai_plan(request):
    """3페이지 명령 → (옵션)현재 웹캠+탐지 첨부 → AI 서버 → 의도/DSL 반환."""
    import json
    from . import ai_client
    data = json.loads(request.body or "{}") if request.body else {}
    text = (data.get("text") or "").strip()
    use_vision = data.get("vision", True)

    imgL = imgR = b""
    det = ""
    if use_vision:
        try:
            cam_left, cam_right = _cams()
            fL = get_camera(cam_left).read()
            fR = get_camera(cam_right).read()
            if fL is not None:
                imgL = cv2.imencode(".jpg", fL)[1].tobytes()
            if fR is not None:
                imgR = cv2.imencode(".jpg", fR)[1].tobytes()
            if fL is not None:
                objs = detect_objects(fL)
                det = json.dumps([{"label": o.get("label"), "conf": round(o.get("conf", 0), 2)}
                                  for o in objs], ensure_ascii=False)
        except Exception:
            pass   # 카메라 없으면 텍스트만으로 진행

    try:
        res = ai_client.plan(text=text, img_left=imgL, img_right=imgR, detections_json=det)
        return JsonResponse({"ok": True, "vision": bool(imgL or imgR), **res})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})
