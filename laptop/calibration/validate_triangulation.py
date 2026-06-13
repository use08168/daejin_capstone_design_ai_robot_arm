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
GRID_C, GRID_R = 6, 4   # 커버리지 격자 (가로 6 × 세로 4)


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
    W, H = (int(c["image_size"][0]), int(c["image_size"][1])) if "image_size" in c else (1280, 720)

    lefts = sorted(f for f in os.listdir(CAP) if f.endswith("_L.png"))
    all_err = []
    all_scale = []
    depths = []
    used = 0
    grid = [[0] * GRID_C for _ in range(GRID_R)]   # 좌 카메라 코너 분포

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
        for pt in ptsL:   # 커버리지: 두 카메라가 "공통으로" 본 코너만(=삼각측량 가능 영역, 좌 카메라 좌표)
            gx = min(GRID_C - 1, max(0, int(pt[0] / W * GRID_C)))
            gy = min(GRID_R - 1, max(0, int(pt[1] / H * GRID_R)))
            grid[gy][gx] += 1
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
    scale_mean = float(all_scale.mean())

    # ---- 커버리지 분석: 어디가 부족한지 + 무엇을 더 찍을지 ----
    nz = sorted(n for row in grid for n in row if n > 0)
    med = nz[len(nz) // 2] if nz else 0
    thr = max(1, med * 0.2)
    weak = [[cc, r] for r in range(GRID_R) for cc in range(GRID_C) if grid[r][cc] < thr]
    dmin, dmax, davg = float(min(depths)), float(max(depths)), float(np.mean(depths))
    advice = []
    if any(wk[0] in (0, GRID_C - 1) or wk[1] in (0, GRID_R - 1) for wk in weak):
        advice.append("부족한 칸이 화면 가장자리라면: 그곳이 로봇 작업 영역(팔이 닿고 물체가 놓이는 곳)이면 채우고, 팔이 닿지 않는 끝부분이면 무시해도 됩니다. 정확도는 '로봇이 실제 쓰는 영역 + 물체 거리'에서만 좋으면 충분합니다.")
    if weak:
        advice.append(f"부족한 칸 {len(weak)}곳(빨간 테두리)에 보드를 놓고, **두 화면 모두에** 보이게 더 촬영하세요. (격자는 '양쪽 카메라 공통' 코너 기준 = 3D 가능 영역)")
        advice.append("특정 칸이 계속 빨가면 두 카메라 공통 시야 밖입니다. 라이브 화면에서 그 위치에 보드를 대 좌·우 모두 잡히는지 먼저 확인 — 한쪽만 잡히면 카메라를 모아야 하는데, 카메라를 움직이면 보정이 무효라 [새 환경으로 초기화] 후 전부 재촬영해야 합니다. 그래서 카메라 배치(겹침)는 촬영 '전에' 확정하세요. 옮기기 싫으면 그 영역은 작업공간에서 제외.")
    if dmin > 0 and dmax / dmin < 1.5:
        advice.append(f"촬영 거리가 비슷합니다({dmin:.0f}~{dmax:.0f}mm). 더 가깝게·멀게 거리를 다양화하세요.")
    if davg > 900:
        advice.append(f"평균 거리 {davg:.0f}mm로 먼 편 — 보드를 더 가까이(화면을 크게 채우게) 찍으면 코너가 정확해집니다.")
    if abs(scale_mean - 1) > 0.005:
        advice.append(f"스케일 {scale_mean:.4f}(이상 1.0). 위 커버리지·거리 다양화로 개선됩니다. 인쇄 배율 100%·보드 평탄도도 확인.")
    if not advice:
        advice.append("커버리지 양호 — 오차가 크면 보드 평탄도/인쇄 배율(100%)·마커 실측 mm를 확인하세요.")

    return {
        "ok": True,
        "pairs_used": used,
        "corner_pairs": int(len(all_err)),
        "mean_abs_err_mm": round(float(np.abs(all_err).mean()), 2),
        "bias_mm": round(float(all_err.mean()), 2),
        "std_mm": round(float(all_err.std()), 2),
        "scale": round(scale_mean, 4),
        "depth_mm": round(float(np.mean(depths)), 0),
        "depth_min": round(dmin, 0),
        "depth_max": round(dmax, 0),
        "grid": grid, "grid_cols": GRID_C, "grid_rows": GRID_R,
        "weak_cells": weak, "advice": advice,
    }


def main():
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
