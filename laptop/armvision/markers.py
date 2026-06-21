"""
로봇팔 ArUco 마커 (DICT_6X6_250) 검출 + 카메라→로봇 변환 T 산출.

- id 0 (70mm) = 고정 베이스 → 로봇 기준 좌표계 정의 (단계 ⑤)
- id 1~ (40mm) = 각 링크 추적/콜드스타트 (단계 ⑥)

ChArUco 보드(DICT_5X5_100)와 다른 사전이라 동시에 써도 충돌 없음.
T 는 좌 카메라 좌표 → 로봇(베이스 마커) 좌표 변환: X_robot = T · X_camera.
"""
import os

import cv2
import numpy as np

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
_detector = cv2.aruco.ArucoDetector(DICT, cv2.aruco.DetectorParameters())

BASE_ID = 0
BASE_MM = 70.0

CAL = r"C:\robotic_arm\laptop\calibration\stereo_calib.npz"
T_PATH = r"C:\robotic_arm\laptop\calibration\camera_robot_T.npz"
# id0(베이스) 프레임에서 본 J1축(id1) 고정 오프셋 — 1회 측정 후 영구. 이후 카메라가 id0만 봐도 J1 원점 복원(팔 불필요).
OFFSET_PATH = r"C:\robotic_arm\laptop\calibration\base_j1_offset.npz"
# 환경 고정 월드 앵커(id8~12) — Phase A에서 로봇기준 코너를 등록해두면, Phase B(작업공간)에서
# id0/팔 없이 보이는 앵커만으로 카메라→로봇 변환을 복원(설치마다 가볍게).
ANCHOR_IDS = (8, 9, 10, 11, 12)
ANCHORS_PATH = r"C:\robotic_arm\laptop\calibration\world_anchors.npz"


def _load_offset():
    return np.load(OFFSET_PATH)["offset"] if os.path.exists(OFFSET_PATH) else None


def has_offset() -> bool:
    return os.path.exists(OFFSET_PATH)


def _load_anchors():
    """{id(int): 로봇기준 코너(4,3)}. 없으면 {}."""
    if not os.path.exists(ANCHORS_PATH):
        return {}
    d = np.load(ANCHORS_PATH)
    return {int(k.split("_")[1]): d[k] for k in d.files}


def registered_anchor_ids():
    return sorted(_load_anchors().keys())


def has_anchors() -> bool:
    return len(_load_anchors()) > 0


def detect(frame):
    """프레임에서 ArUco 마커 검출 → {id(int): corners(4,2) float32}. (코너순서 TL,TR,BR,BL)"""
    corners, ids, _ = _detector.detectMarkers(frame)
    out = {}
    if ids is not None:
        for c, i in zip(corners, ids.flatten()):
            out[int(i)] = c.reshape(4, 2).astype(np.float32)
    return out


def _triangulate(cornersL, cornersR, cal):
    """좌·우 대응 코너(4,2)쌍 → 3D (4,3) [좌 카메라 좌표, mm]."""
    udL = cv2.undistortPoints(cornersL.reshape(-1, 1, 2), cal["K1"], cal["d1"], P=cal["K1"])
    udR = cv2.undistortPoints(cornersR.reshape(-1, 1, 2), cal["K2"], cal["d2"], P=cal["K2"])
    p4 = cv2.triangulatePoints(cal["P1"], cal["P2"], udL.reshape(-1, 2).T, udR.reshape(-1, 2).T)
    return (p4[:3] / p4[3]).T


def _frame_from_corners(P):
    """마커 4코너 3D(TL,TR,BR,BL) → (T 4x4, info). 마커 평면이 로봇 기준 좌표계.
    마커 좌표계: X=오른쪽(TL→TR), Y=위(BL→TL), Z=마커 바깥(X×Y)."""
    o = P.mean(0)
    xax = (P[1] - P[0]) + (P[2] - P[3]); xax /= (np.linalg.norm(xax) or 1)
    yax = (P[0] - P[3]) + (P[1] - P[2])
    yax = yax - np.dot(yax, xax) * xax; yax /= (np.linalg.norm(yax) or 1)   # x에 직교화
    zax = np.cross(xax, yax)
    R = np.column_stack([xax, yax, zax])     # 마커 축(카메라 좌표 기준, 열벡터)
    Rt = R.T
    T = np.eye(4)
    T[:3, :3] = Rt
    T[:3, 3] = -Rt @ o                       # X_robot = R^T (X_cam - o)
    # 검증용: 변 길이(=마커 실측 70mm 와 비교 → 스케일/캘리 sanity)
    edges = [np.linalg.norm(P[1] - P[0]), np.linalg.norm(P[2] - P[1]),
             np.linalg.norm(P[3] - P[2]), np.linalg.norm(P[0] - P[3])]
    info = {"dist_mm": float(np.linalg.norm(o)), "marker_mm": float(np.mean(edges))}
    return T, info


def _build_T(mL, mR, cal):
    """검출 마커로 카메라→로봇 T 구성(방향=id0, 원점=J1). id1 보이면 오프셋 저장.
    반환 (T, info, origin) — id0 없으면 (None, None, None)."""
    if BASE_ID not in mL or BASE_ID not in mR:
        return None, None, None
    P = _triangulate(mL[BASE_ID], mR[BASE_ID], cal)
    T, info = _frame_from_corners(P)               # 방향·원점: id0 (베이스에 고정 → 카메라 옮겨도 id0만 보이면 OK)
    origin = "id0"
    if 1 in mL and 1 in mR:                        # 원점을 J1 회전축(id1)으로 이동
        p1 = _triangulate(mL[1], mR[1], cal).mean(0)
        p1r = (T @ np.array([p1[0], p1[1], p1[2], 1.0]))[:3]   # id0 프레임에서 본 id1 위치
        T[:3, 3] = T[:3, 3] - p1r
        np.savez(OFFSET_PATH, offset=p1r)          # ★ 오프셋 영구 저장(1회) — 이후 id0만으로 재현
        origin = "id1(J1축·실시간 + 오프셋 저장됨)"
    else:
        off = _load_offset()
        if off is not None:
            T[:3, 3] = T[:3, 3] - off              # ★ 저장 오프셋으로 J1 원점 복원 — 팔/id1 불필요
            origin = "id1(J1축·저장 오프셋, 팔 없이)"
        else:
            origin = "id0 (오프셋 미보정 — 팔+id1 보이게 1회 산출 필요)"
    return T, info, origin


def compute_base_transform(frameL, frameR):
    """양 카메라에서 id0 베이스 마커로 카메라→로봇 변환 T 산출·저장. (단계 5)"""
    if not os.path.exists(CAL):
        return {"ok": False, "error": "스테레오 캘리브레이션 먼저 (3단계까지 완료)."}
    mL, mR = detect(frameL), detect(frameR)
    if BASE_ID not in mL or BASE_ID not in mR:
        where = []
        if BASE_ID in mL: where.append("좌")
        if BASE_ID in mR: where.append("우")
        seen = "+".join(where) if where else "양쪽 모두 안 보임"
        return {"ok": False, "error": f"id0 베이스 마커가 양 카메라에 동시에 보여야 합니다 (현재: {seen})."}
    c = np.load(CAL)
    cal = {k: c[k] for k in ("K1", "d1", "K2", "d2", "P1", "P2")}
    T, info, origin = _build_T(mL, mR, cal)
    np.savez(T_PATH, T=T)
    return {"ok": True, "origin": origin, "has_offset": has_offset(),
            **{k: round(v, 1) for k, v in info.items()}}


def register_anchors(frameL, frameR):
    """Phase A(단계 5): id0로 로봇 프레임 잡고, 보이는 앵커(id8~12)의 로봇기준 코너(4,3)를 누적 저장."""
    if not os.path.exists(CAL):
        return {"ok": False, "error": "스테레오 캘리브레이션 먼저."}
    c = np.load(CAL)
    cal = {k: c[k] for k in ("K1", "d1", "K2", "d2", "P1", "P2")}
    mL, mR = detect(frameL), detect(frameR)
    T, _info, origin = _build_T(mL, mR, cal)
    if T is None:
        return {"ok": False, "error": "id0 베이스 마커가 양 카메라에 보여야 앵커를 로봇좌표로 등록합니다."}
    cur = _load_anchors()                                    # 기존 등록에 누적
    found = []
    for aid in ANCHOR_IDS:
        if aid in mL and aid in mR:
            Pc = _triangulate(mL[aid], mR[aid], cal)          # (4,3) 카메라
            Pr = (T @ np.c_[Pc, np.ones(4)].T).T[:, :3]       # 로봇기준 (4,3)
            cur[aid] = Pr
            found.append(aid)
    if not found:
        return {"ok": False, "error": "앵커(id8~12)가 양 카메라에 안 보입니다."}
    np.savez(ANCHORS_PATH, **{f"a_{k}": v for k, v in cur.items()})
    return {"ok": True, "registered": sorted(found), "total": sorted(cur.keys()),
            "origin": origin, "n_total": len(cur)}


def compute_transform_from_anchors(frameL, frameR):
    """Phase B(단계 11): 보이는 앵커들로 카메라→로봇 T 복원(id0/팔 불필요). Kabsch SVD + 잔차 rms."""
    if not os.path.exists(CAL):
        return {"ok": False, "error": "스테레오 캘리브레이션 먼저 (작업공간 보정)."}
    A = _load_anchors()
    if not A:
        return {"ok": False, "error": "등록된 앵커 없음 — Phase A(단계 5)에서 앵커 등록 먼저."}
    c = np.load(CAL)
    cal = {k: c[k] for k in ("K1", "d1", "K2", "d2", "P1", "P2")}
    mL, mR = detect(frameL), detect(frameR)
    cam, rob, used = [], [], []
    for aid, Pr in A.items():
        if aid in mL and aid in mR:
            cam.append(_triangulate(mL[aid], mR[aid], cal))   # (4,3) 카메라
            rob.append(Pr); used.append(aid)
    if not used:
        return {"ok": False, "error": "등록된 앵커가 현재 화면에 안 보입니다 (작업공간 카메라가 앵커를 보게)."}
    cam = np.vstack(cam); rob = np.vstack(rob)                # (4N,3)
    cc, rc = cam.mean(0), rob.mean(0)
    H = (cam - cc).T @ (rob - rc)
    U, _S, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1; R = Vt.T @ U.T
    t = rc - R @ cc
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = t                # X_robot = T·X_cam
    pred = (R @ cam.T).T + t
    rms = float(np.sqrt(((pred - rob) ** 2).sum(1).mean()))   # 정합 잔차(자가검증)
    np.savez(T_PATH, T=T)
    return {"ok": True, "anchors_used": sorted(used), "n": len(used), "rms_mm": round(rms, 2)}


def marker_status(frameL, frameR):
    """각 카메라에서 보이는 마커 id 목록 (UI 표시용)."""
    return {"left": sorted(detect(frameL).keys()), "right": sorted(detect(frameR).keys())}


def measure(frameL, frameR):
    """양 카메라 공통 마커들을 삼각측량 → 중심 3D. T 있으면 로봇 기준 mm.
    반환: {ok, frame, markers:{id:[x,y,z]}, left_only, right_only}."""
    if not os.path.exists(CAL):
        return {"ok": False, "error": "스테레오 캘리브레이션 필요 (3단계까지)."}
    c = np.load(CAL)
    cal = {k: c[k] for k in ("K1", "d1", "K2", "d2", "P1", "P2")}
    T = np.load(T_PATH)["T"] if os.path.exists(T_PATH) else None
    mL, mR = detect(frameL), detect(frameR)
    common = sorted(set(mL) & set(mR))
    res = {}
    for mid in common:
        P = _triangulate(mL[mid], mR[mid], cal)      # (4,3) 좌 카메라 좌표
        ctr = P.mean(0)
        if T is not None:
            ctr = (T @ np.array([ctr[0], ctr[1], ctr[2], 1.0]))[:3]
        res[mid] = [round(float(v), 1) for v in ctr]
    return {"ok": True, "frame": "robot" if T is not None else "camera",
            "markers": res,
            "left_only": sorted(set(mL) - set(mR)),
            "right_only": sorted(set(mR) - set(mL))}


def has_transform() -> bool:
    return os.path.exists(T_PATH)
