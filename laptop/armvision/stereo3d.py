"""
스테레오 3D — 좌/우 탐지 매칭(③) + 삼각측량(④).

캘리브레이션 결과(stereo_calib.npz)는 **지연 로딩**한다 → 아직 캘리브레이션 전이라
파일이 없어도 import/서버 기동에 문제 없음. 캘리브레이션 직후 reload()로 갱신.

좌표계: 좌 카메라 기준(P1 = K1[I|0]). 로봇 기준 변환은 ⑤단계(ArUco).
"""
import math
import os

import cv2
import numpy as np

CAL = r"C:\robotic_arm\laptop\calibration\stereo_calib.npz"

_calib = None


def is_calibrated() -> bool:
    return os.path.exists(CAL)


def reload():
    """캘리브레이션 파일 재로딩(캘리브레이션 실행 직후 호출)."""
    global _calib
    _calib = None


def _load():
    global _calib
    if _calib is None:
        if not os.path.exists(CAL):
            return None
        c = np.load(CAL)
        _calib = {k: c[k] for k in ("K1", "d1", "K2", "d2", "F", "P1", "P2")}
    return _calib


def _triangulate(uvL, uvR, cal):
    pL = cv2.undistortPoints(np.array([[uvL]], np.float32), cal["K1"], cal["d1"], P=cal["K1"])
    pR = cv2.undistortPoints(np.array([[uvR]], np.float32), cal["K2"], cal["d2"], P=cal["K2"])
    p4 = cv2.triangulatePoints(cal["P1"], cal["P2"], pL.reshape(-1, 2).T, pR.reshape(-1, 2).T)
    X = (p4[:3] / p4[3]).reshape(3)
    return [float(X[0]), float(X[1]), float(X[2])]


def match_and_triangulate(dets_left, dets_right, max_epi_px=60.0):
    """좌/우 탐지 리스트 → 매칭된 물체의 3D 좌표 리스트. 미캘리브레이션이면 []."""
    cal = _load()
    if cal is None:
        return []
    F = cal["F"]
    out = []
    used = set()
    for dl in dets_left:
        x0, y0 = dl["center"]
        line = cv2.computeCorrespondEpilines(
            np.array([[[x0, y0]]], np.float32), 1, F).reshape(3)
        a, b, c = line
        norm = math.hypot(a, b) or 1.0
        best, bestd = -1, max_epi_px
        for j, dr in enumerate(dets_right):
            if j in used or dr["class"] != dl["class"]:
                continue
            x, y = dr["center"]
            dd = abs(a * x + b * y + c) / norm
            if dd < bestd:
                bestd, best = float(dd), j
        if best >= 0:
            used.add(best)
            dr = dets_right[best]
            xyz = _triangulate(dl["center"], dr["center"], cal)
            out.append({
                "class": dl["class"],
                "xyz_mm": [round(v, 1) for v in xyz],
                "uvL": [round(x0, 1), round(y0, 1)],
                "uvR": [round(dr["center"][0], 1), round(dr["center"][1], 1)],
                "epi_px": round(float(bestd), 1),
            })
    # 매칭된 3D 물체에 클래스별 id 부여 (3D X 기준 좌→우) — 카메라 간 일관
    groups = {}
    for o in out:
        groups.setdefault(o["class"], []).append(o)
    for cls, lst in groups.items():
        lst.sort(key=lambda o: o["xyz_mm"][0])
        for n, o in enumerate(lst, 1):
            o["id"] = f"{cls}_{n}"
    return out
