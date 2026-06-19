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
    """3페이지 — 자연어 제어(AI 서버 연동) + 웹캠/로봇팔 자세 미러."""
    cam_left, cam_right = _cams()
    return render(request, "armvision/control.html",
                  {"cam_left": cam_left, "cam_right": cam_right})


from django.views.decorators.clickjacking import xframe_options_sameorigin


@xframe_options_sameorigin   # 5페이지(자연어)가 ?embed=1로 iframe 임베드 가능하게(기본 DENY 해제)
def arm3d(request):
    """3페이지 3D 제어(?view=control) / 4페이지 3D 시뮬레이터(?view=sim) — 같은 엔진, 패널만 다름."""
    return render(request, "armvision/arm3d.html",
                  {"view": "sim" if request.GET.get("view") == "sim" else "control"})


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

    audio = b""
    if data.get("audio_b64"):
        import base64
        try:
            audio = base64.b64decode(data["audio_b64"].split(",")[-1])
        except Exception:
            audio = b""

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
        res = ai_client.plan(text=text, audio=audio, img_left=imgL, img_right=imgR, detections_json=det)
        return JsonResponse({"ok": True, "vision": bool(imgL or imgR), **res})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})


# ============ DSL 실행 — set_joint(직접 관절) 안전 실행 (3페이지 ▶) ============

_JOINT_CH = {"J1": 0, "J2": 1, "J3": 2, "J4": 3, "J5": 4, "J6": 5, "J7": 6}
# 실측 서보 펄스(채널별 us0/us180) — arduino/docs/servo_calibration.md
_SERVO_CAL = {0: [600, 2740], 1: [530, 2670], 2: [520, 2700], 3: [540, 2720], 4: [600, 2750], 5: [560, 2750]}  # J4↔J5 모터교체 J4(ch3):0°=2720,180°=540 J5(ch4):0°=2750,180°=600 / J6(ch5):0°=2750,180°=560 실측


def _ang_to_us(ch, ang):
    a = max(0.0, min(180.0, 180.0 - ang))            # 시뮬↔실물 미러
    us0, us180 = _SERVO_CAL.get(ch, [600, 2740])
    return round(us0 + (a / 180.0) * (us180 - us0))


# 현재 관절각(실물 기준, 기본=홈 90°). 3D 미러가 이걸 폴링해 실제 팔을 따라감.
# exec_joint가 갱신 → 미러가 localStorage가 아닌 '서버 진실'을 따름(드리프트 방지).
_JOINT_STATE = {f"J{i}": 90.0 for i in range(1, 7)}

# ============ 로봇팔 작동 속도 — 단일 설정(모든 경로 공통, 한 곳에서 제어) ============
# 관절·그리퍼·각 페이지 램프가 전부 이 값을 사용 → 속도 일관. /arm/config/ 로 조회·변경.
ARM_CFG = {"deg_per_s": 30.0, "grip_us_per_s": 700.0}
_RAMP_DT = 0.02   # 램프 갱신 주기(초) — 50Hz


def _ramp(ch, a, target, deg=True):
    """채널 ch을 a→target까지 공통 속도로 안전 램프. deg=True 관절(°→펄스), False 그리퍼(µs).
    반환 (성공, 멈춘값). 전압강하 방지를 위해 작은 단계로 점진 전송."""
    import time
    from . import arduino_bridge
    inc = max(0.1, (ARM_CFG["deg_per_s"] if deg else ARM_CFG["grip_us_per_s"]) * _RAMP_DT)
    while abs(a - target) > inc:
        a += inc if target >= a else -inc
        us = _ang_to_us(ch, a) if deg else round(a)
        if not arduino_bridge.send_pulse(ch, us).get("ok"):
            return False, a
        time.sleep(_RAMP_DT)
    arduino_bridge.send_pulse(ch, _ang_to_us(ch, target) if deg else round(target))
    return True, target


@csrf_exempt
def arm_exec_joint(request):
    """{joint:'J1', angle:180, from:90} → 브라운아웃 방지 램프로 한 관절 이동.
    한 번에 한 관절만(다중 모터 동시구동=전압강하 방지). 실물 연결 필수."""
    import json
    import time
    from . import arduino_bridge
    d = json.loads(request.body or "{}")
    joint = d.get("joint")
    ch = _JOINT_CH.get(joint)
    if ch is None:
        return JsonResponse({"ok": False, "error": f"알 수 없는 관절: {joint}"})
    if not arduino_bridge.is_connected():
        return JsonResponse({"ok": False, "error": "실물 미연결 — 4페이지에서 연결하세요."})
    try:
        target = max(0.0, min(180.0, float(d.get("angle"))))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "각도 오류"})
    prev = _JOINT_STATE.get(joint, 90.0)
    _JOINT_STATE[joint] = target                      # 낙관적 갱신 → 미러가 즉시 병행 이동
    ok, a = _ramp(ch, prev, target, deg=True)         # 공통 속도 램프
    _JOINT_STATE[joint] = target if ok else a
    if not ok:
        return JsonResponse({"ok": False, "error": "전송 실패(연결 끊김?)", "disconnected": True})
    return JsonResponse({"ok": True, "joint": joint, "channel": ch, "angle": target})


@csrf_exempt
def arm_joints(request):
    """현재 관절각(서버 보유) → 3D 미러가 폴링해 실제 팔을 따라감."""
    return JsonResponse({"ok": True, "joints": _JOINT_STATE})


@csrf_exempt
def arm_config(request):
    """로봇팔 작동 속도(모든 경로 공통). GET 조회 / POST {deg_per_s, grip_us_per_s} 변경.
    모든 페이지·서버 램프가 이 값을 사용 → 한 곳에서 속도 제어."""
    import json
    if request.method == "POST":
        d = json.loads(request.body or "{}")
        if "deg_per_s" in d:
            ARM_CFG["deg_per_s"] = max(2.0, min(120.0, float(d["deg_per_s"])))
        if "grip_us_per_s" in d:
            ARM_CFG["grip_us_per_s"] = max(100.0, min(3000.0, float(d["grip_us_per_s"])))
    return JsonResponse({"ok": True, **ARM_CFG})


@csrf_exempt
def arm_set_angle(request):
    """{joint, angle} → 단일 펄스 즉시 전송(램프 없음). 실시간 조그 스트리밍용.
    클라이언트가 작은 각도씩 연속 호출 → 부드러운 실시간 추종. 상태 갱신."""
    import json
    from . import arduino_bridge
    d = json.loads(request.body or "{}")
    joint = d.get("joint"); ch = _JOINT_CH.get(joint)
    if ch is None or ch == GRIP_CH:
        return JsonResponse({"ok": False, "error": f"관절 아님: {joint}"})
    if not arduino_bridge.is_connected():
        return JsonResponse({"ok": False, "error": "실물 미연결"})
    try:
        ang = max(0.0, min(180.0, float(d.get("angle"))))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "각도 오류"})
    r = arduino_bridge.send_pulse(ch, _ang_to_us(ch, ang))
    if not r.get("ok"):
        return JsonResponse({"ok": False, "error": "전송 실패(연결 끊김?)", "disconnected": True})
    _JOINT_STATE[joint] = ang
    return JsonResponse({"ok": True, "joint": joint, "angle": ang})


@csrf_exempt
def arm_home(request):
    """3D 미러를 홈(전 관절 90°)으로 맞춤. 실물을 수동으로 홈에 둔 뒤 호출 → 미러 동기화.
    상태만 90°로 재설정(서보를 강제 이동하지 않음 — 다중모터 동시구동 전압강하 방지)."""
    for j in _JOINT_STATE:
        _JOINT_STATE[j] = 90.0
    return JsonResponse({"ok": True, "joints": _JOINT_STATE})


# ============ J7 그리퍼 제어 (열기 550 / 닫기 2500, 천천히 램프) ============

GRIP_CH = 6
GRIP_US = {"open": 550, "close": 2500}   # 실측: 완전 열림 550µs, 완전 닫힘 2500µs
_grip_us = [GRIP_US["close"]]            # 현재 펄스(시작=닫힘 가정) — 점프 없이 램프


@csrf_exempt
def arm_gripper(request):
    """{action:'open'|'close'} → J7(ch6)을 천천히 램프(브라운아웃 방지). 실물 연결 필요."""
    import json
    import time
    from . import arduino_bridge
    d = json.loads(request.body or "{}")
    action = d.get("action")
    if action not in GRIP_US:
        return JsonResponse({"ok": False, "error": "action 은 open|close"})
    if not arduino_bridge.is_connected():
        return JsonResponse({"ok": False, "error": "실물 미연결 — 4페이지에서 연결하세요."})
    target = GRIP_US[action]
    ok, a = _ramp(GRIP_CH, _grip_us[0], target, deg=False)   # 공통 속도 램프(µs)
    _grip_us[0] = target if ok else a
    if not ok:
        return JsonResponse({"ok": False, "error": "전송 실패(연결 끊김?)", "disconnected": True})
    return JsonResponse({"ok": True, "action": action, "us": target})


# ============ Teach-and-repeat (관절각 기록·재생 집기) ============
# 잡는 자세의 관절각 6개 + 그리퍼 동작을 자세(step)로 기록 → 시퀀스로 재생.
# IK 없이 "접근→하강→그리퍼 닫기→들기→이동→놓기" 전체를 검증. 재생은 한 관절씩(전압강하 방지).
TEACH_FILE = r"C:\robotic_arm\laptop\calibration\teach_seq.json"
_JOINTS6 = ("J1", "J2", "J3", "J4", "J5", "J6")


def _teach_load():
    try:
        import json
        with open(TEACH_FILE, encoding="utf-8") as f:
            return json.load(f).get("steps", [])
    except (OSError, ValueError):
        return []


def _teach_save(steps):
    import json
    os.makedirs(os.path.dirname(TEACH_FILE), exist_ok=True)
    with open(TEACH_FILE, "w", encoding="utf-8") as f:
        json.dump({"steps": steps}, f, ensure_ascii=False, indent=2)


def _move_joint_to(joint, target):
    """한 관절을 현재각(_JOINT_STATE)에서 target까지 안전 램프(~2°/40ms). 상태 갱신."""
    import time
    from . import arduino_bridge
    ch = _JOINT_CH.get(joint)
    if ch is None or ch == GRIP_CH:
        return {"ok": False, "error": f"관절 아님: {joint}"}
    target = max(0.0, min(180.0, float(target)))
    ok, a = _ramp(ch, _JOINT_STATE.get(joint, 90.0), target, deg=True)   # 공통 속도 램프
    _JOINT_STATE[joint] = target if ok else a
    return {"ok": True} if ok else {"ok": False, "error": "전송 실패(연결 끊김?)", "disconnected": True}


def _grip_to(action):
    """그리퍼 열기/닫기 안전 램프(재생기·exec 공용)."""
    import time
    from . import arduino_bridge
    if action not in GRIP_US:
        return {"ok": False, "error": "grip 오류"}
    ok, a = _ramp(GRIP_CH, _grip_us[0], GRIP_US[action], deg=False)   # 공통 속도 램프(µs)
    _grip_us[0] = GRIP_US[action] if ok else a
    return {"ok": True} if ok else {"ok": False, "error": "전송 실패(연결 끊김?)", "disconnected": True}


def _move_pose(joints):
    """여러 관절을 목표 자세로 — 한 관절씩(J1→J6, 전압강하 방지)."""
    for j in _JOINTS6:
        if joints.get(j) is not None:
            r = _move_joint_to(j, joints[j])
            if not r.get("ok"):
                return r
    return {"ok": True}


@csrf_exempt
def teach_list(request):
    return JsonResponse({"ok": True, "steps": _teach_load()})


@csrf_exempt
def teach_record(request):
    """현재 관절각(_JOINT_STATE) + 그리퍼 동작을 자세로 기록."""
    import json
    d = json.loads(request.body or "{}")
    steps = _teach_load()
    grip = d.get("grip") if d.get("grip") in GRIP_US else None
    steps.append({
        "name": (d.get("name") or f"자세{len(steps)+1}").strip(),
        "joints": {j: round(float(_JOINT_STATE.get(j, 90.0)), 1) for j in _JOINTS6},
        "grip": grip,
    })
    _teach_save(steps)
    return JsonResponse({"ok": True, "steps": steps})


@csrf_exempt
def teach_delete(request):
    import json
    d = json.loads(request.body or "{}")
    steps = _teach_load(); i = d.get("index")
    if isinstance(i, int) and 0 <= i < len(steps):
        steps.pop(i); _teach_save(steps)
    return JsonResponse({"ok": True, "steps": steps})


@csrf_exempt
def teach_clear(request):
    _teach_save([])
    return JsonResponse({"ok": True, "steps": []})


@csrf_exempt
def teach_reorder(request):
    """{index, dir:'up'|'down'} — 자세 순서 변경."""
    import json
    d = json.loads(request.body or "{}")
    steps = _teach_load(); i = d.get("index")
    if isinstance(i, int) and 0 <= i < len(steps):
        j = i + (1 if d.get("dir") == "down" else -1)
        if 0 <= j < len(steps):
            steps[i], steps[j] = steps[j], steps[i]; _teach_save(steps)
    return JsonResponse({"ok": True, "steps": steps})


@csrf_exempt
def teach_goto(request):
    """{index} — 해당 자세 하나로 이동(+그리퍼). 티칭 중 미리보기용."""
    import json
    from . import arduino_bridge
    if not arduino_bridge.is_connected():
        return JsonResponse({"ok": False, "error": "실물 미연결 — 4페이지에서 연결하세요."})
    d = json.loads(request.body or "{}")
    steps = _teach_load(); i = d.get("index")
    if not (isinstance(i, int) and 0 <= i < len(steps)):
        return JsonResponse({"ok": False, "error": "잘못된 index"})
    st = steps[i]
    r = _move_pose(st.get("joints", {}))
    if not r.get("ok"):
        return JsonResponse(r)
    if st.get("grip"):
        r = _grip_to(st["grip"])
        if not r.get("ok"):
            return JsonResponse(r)
    return JsonResponse({"ok": True, "step": st})


@csrf_exempt
def teach_play(request):
    """기록된 시퀀스를 순서대로 재생(한 관절씩 안전 램프 + 그리퍼)."""
    from . import arduino_bridge
    if not arduino_bridge.is_connected():
        return JsonResponse({"ok": False, "error": "실물 미연결 — 4페이지에서 연결하세요."})
    steps = _teach_load()
    if not steps:
        return JsonResponse({"ok": False, "error": "기록된 자세가 없습니다."})
    done = []
    for idx, st in enumerate(steps):
        r = _move_pose(st.get("joints", {}))
        if not r.get("ok"):
            return JsonResponse({"ok": False, "error": f"[{idx} {st.get('name')}] {r.get('error')}", "done": done})
        if st.get("grip"):
            r = _grip_to(st["grip"])
            if not r.get("ok"):
                return JsonResponse({"ok": False, "error": f"[{idx} 그리퍼] {r.get('error')}", "done": done})
        done.append(st.get("name"))
    return JsonResponse({"ok": True, "played": done})
