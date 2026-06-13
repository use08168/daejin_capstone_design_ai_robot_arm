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


def compute_base_transform(frameL, frameR):
    """양 카메라에서 id0 베이스 마커를 보고 카메라→로봇 변환 T 산출·저장.
    반환: {ok, error?|dist_mm, marker_mm}."""
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
    P = _triangulate(mL[BASE_ID], mR[BASE_ID], cal)
    T, info = _frame_from_corners(P)
    np.savez(T_PATH, T=T)
    return {"ok": True, **{k: round(v, 1) for k, v in info.items()}}


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
