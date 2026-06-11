"""
삼각측량 검증 — ChArUco 보드 코너를 3D로 복원해 실제 30mm 간격과 비교.

stereo_calib.npz 를 불러와, 캡처 쌍마다 좌/우 공통 코너를 삼각측량하고
코너 사이 거리(측정) vs 보드 정답 거리(known)를 비교한다.
오차가 작고 스케일≈1 이면 3D 파이프라인이 정확하다는 뜻.
"""
import os

import cv2
import numpy as np

CAP = r"C:\robotic_arm\laptop\calibration\captures"
CAL = r"C:\robotic_arm\laptop\calibration\stereo_calib.npz"

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
BOARD = cv2.aruco.CharucoBoard((6, 8), 30.0, 23.0, DICT)   # mm
DET = cv2.aruco.CharucoDetector(BOARD)
CHESS = BOARD.getChessboardCorners()   # (35,3) mm
MIN = 6


def triangulate(ptsL, ptsR, K1, d1, K2, d2, P1, P2):
    udL = cv2.undistortPoints(ptsL.reshape(-1, 1, 2), K1, d1, P=K1)
    udR = cv2.undistortPoints(ptsR.reshape(-1, 1, 2), K2, d2, P=K2)
    p4 = cv2.triangulatePoints(P1, P2, udL.reshape(-1, 2).T, udR.reshape(-1, 2).T)
    return (p4[:3] / p4[3]).T   # (N,3) mm, 좌 카메라 좌표계


def run():
    if not os.path.exists(CAL):
        return {"ok": False, "error": "캘리브레이션 결과 없음 — 2단계를 먼저 실행하세요."}
    c = np.load(CAL)
    K1, d1, K2, d2 = c["K1"], c["d1"], c["K2"], c["d2"]
    P1, P2 = c["P1"], c["P2"]

    lefts = sorted(f for f in os.listdir(CAP) if f.endswith("_L.png"))
    all_err = []
    all_scale = []
    depths = []
    used = 0

    for lf in lefts:
        idx = lf.replace("_L.png", "")
        L = cv2.imread(os.path.join(CAP, lf))
        R = cv2.imread(os.path.join(CAP, idx + "_R.png"))
        ccL, ciL, _, _ = DET.detectBoard(L)
        ccR, ciR, _, _ = DET.detectBoard(R)
        if ccL is None or ccR is None:
            continue
        idsL, idsR = ciL.flatten(), ciR.flatten()
        common = np.intersect1d(idsL, idsR)
        if len(common) < MIN:
            continue
        mapL = {int(i): ccL[k][0] for k, i in enumerate(idsL)}
        mapR = {int(i): ccR[k][0] for k, i in enumerate(idsR)}
        ptsL = np.array([mapL[int(i)] for i in common], np.float32)
        ptsR = np.array([mapR[int(i)] for i in common], np.float32)
        P3 = triangulate(ptsL, ptsR, K1, d1, K2, d2, P1, P2)
        depths.append(float(np.mean(P3[:, 2])))

        # 모든 코너쌍 거리 비교
        for a in range(len(common)):
            for b in range(a + 1, len(common)):
                meas = np.linalg.norm(P3[a] - P3[b])
                known = np.linalg.norm(CHESS[int(common[a])] - CHESS[int(common[b])])
                if known > 1e-6:
                    all_err.append(meas - known)
                    all_scale.append(meas / known)
        used += 1

    if len(all_err) == 0:
        return {"ok": False, "error": "검증할 코너쌍 없음 — 촬영/캘리브레이션을 확인하세요."}
    all_err = np.array(all_err); all_scale = np.array(all_scale)
    return {
        "ok": True,
        "pairs_used": used,
        "corner_pairs": int(len(all_err)),
        "mean_abs_err_mm": round(float(np.abs(all_err).mean()), 2),
        "bias_mm": round(float(all_err.mean()), 2),
        "std_mm": round(float(all_err.std()), 2),
        "scale": round(float(all_scale.mean()), 4),
        "depth_mm": round(float(np.mean(depths)), 0),
        "depth_min": round(float(min(depths)), 0),
        "depth_max": round(float(max(depths)), 0),
    }


def main():
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
