import os

import cv2
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render

from . import charuco, stereo3d
from .camera import get_camera, mjpeg_frames
from .detector import detections as detect_objects

CAM_LEFT = 2
CAM_RIGHT = 1
CAPTURE_DIR = r"C:\robotic_arm\laptop\calibration\captures"


# ============ 페이지 ============

def index(request):
    """1페이지 — 라이브 카메라 + 객체 탐지. 캘리브레이션되면 3D 자동 활성화."""
    return render(request, "armvision/index.html", {"calibrated": stereo3d.is_calibrated()})


def setup(request):
    """2페이지 — 6단계 캘리브레이션 위저드."""
    return render(request, "armvision/setup.html")


def control(request):
    """3페이지 — 자연어 제어(골격, 추후 구현)."""
    return render(request, "armvision/control.html")


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
    fL = get_camera(CAM_LEFT).read()
    fR = get_camera(CAM_RIGHT).read()
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
    fL = get_camera(CAM_LEFT).read()
    fR = get_camera(CAM_RIGHT).read()
    if fL is None or fR is None:
        return JsonResponse({"error": "프레임 없음"})
    nL, nR = charuco.count(fL), charuco.count(fR)
    idx = _capture_count() + 1
    cv2.imwrite(os.path.join(CAPTURE_DIR, f"pair_{idx:02d}_L.png"), fL)
    cv2.imwrite(os.path.join(CAPTURE_DIR, f"pair_{idx:02d}_R.png"), fR)
    return JsonResponse({"saved": idx, "cornersL": nL, "cornersR": nR,
                         "ok": nL >= charuco.MIN_GOOD and nR >= charuco.MIN_GOOD})


def calibrate_status(request):
    fL = get_camera(CAM_LEFT).read()
    fR = get_camera(CAM_RIGHT).read()
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
