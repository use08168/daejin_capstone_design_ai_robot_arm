"""
ChArUco 스테레오 캘리브레이션.

입력: calibration/captures/pair_*_L.png, *_R.png
출력: calibration/stereo_calib.npz  (K1,d1,K2,d2,R,T,E,F,P1,P2,imageSize, 오차)

단위: 보드를 mm 로 정의 → 모든 3D 결과(T, 삼각측량)가 mm.
좌/우(L/R)는 1페이지에서 선택한 카메라로 촬영된 pair_*_L.png / _R.png 로 결정된다(좌=기준 카메라).
"""
import os

import cv2
import numpy as np

CAP = r"C:\robotic_arm\laptop\calibration\captures"
OUT = r"C:\robotic_arm\laptop\calibration\stereo_calib.npz"

# 인쇄 PDF와 동일 격자, 단위만 mm
DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
BOARD = cv2.aruco.CharucoBoard((6, 8), 30.0, 23.0, DICT)   # mm
DET = cv2.aruco.CharucoDetector(BOARD)
CHESS = BOARD.getChessboardCorners()   # (35,3) mm, id 순서
MIN = 6


def detect(img):
    cc, ci, _, _ = DET.detectBoard(img)
    n = 0 if cc is None else len(cc)
    return cc, ci, n


def run():
    if not os.path.isdir(CAP):
        return {"ok": False, "error": "촬영 폴더 없음 — 1단계(촬영)부터 진행하세요."}
    lefts = sorted(f for f in os.listdir(CAP) if f.endswith("_L.png"))
    objL, imgL, objR, imgR = [], [], [], []
    s_obj, s_l, s_r = [], [], []
    image_size = None

    for lf in lefts:
        idx = lf.replace("_L.png", "")
        L = cv2.imread(os.path.join(CAP, lf))
        R = cv2.imread(os.path.join(CAP, idx + "_R.png"))
        if image_size is None:
            h, w = L.shape[:2]
            image_size = (w, h)

        ccL, ciL, nL = detect(L)
        ccR, ciR, nR = detect(R)

        # 내부 캘리브레이션용 (각 카메라 독립)
        if nL >= MIN:
            op, ip = BOARD.matchImagePoints(ccL, ciL)
            if op is not None and len(op) >= MIN:
                objL.append(op.astype(np.float32)); imgL.append(ip.astype(np.float32))
        if nR >= MIN:
            op, ip = BOARD.matchImagePoints(ccR, ciR)
            if op is not None and len(op) >= MIN:
                objR.append(op.astype(np.float32)); imgR.append(ip.astype(np.float32))

        # 스테레오용 (좌·우 공통 코너)
        if nL >= MIN and nR >= MIN:
            idsL = ciL.flatten(); idsR = ciR.flatten()
            common = np.intersect1d(idsL, idsR)
            if len(common) >= MIN:
                mapL = {int(i): ccL[k][0] for k, i in enumerate(idsL)}
                mapR = {int(i): ccR[k][0] for k, i in enumerate(idsR)}
                op = np.array([CHESS[int(i)] for i in common], np.float32)
                lp = np.array([mapL[int(i)] for i in common], np.float32)
                rp = np.array([mapR[int(i)] for i in common], np.float32)
                s_obj.append(op); s_l.append(lp); s_r.append(rp)

    print(f"내부 뷰  L={len(objL)}  R={len(objR)}  | 스테레오 쌍={len(s_obj)}  | 이미지 {image_size}")
    if len(objL) < 6 or len(objR) < 6 or len(s_obj) < 6:
        return {"ok": False, "error": f"데이터 부족 (내부 L{len(objL)}/R{len(objR)}, 스테레오 {len(s_obj)}). 촬영을 더 하세요."}

    # 1) 내부 캘리브레이션
    errL, K1, d1, _, _ = cv2.calibrateCamera(objL, imgL, image_size, None, None)
    errR, K2, d2, _, _ = cv2.calibrateCamera(objR, imgR, image_size, None, None)
    print(f"내부 재투영오차(px)  L={errL:.3f}  R={errR:.3f}")

    # 2) 스테레오 (내부 고정)
    errS, K1, d1, K2, d2, R, T, E, F = cv2.stereoCalibrate(
        s_obj, s_l, s_r, K1, d1, K2, d2, image_size,
        flags=cv2.CALIB_FIX_INTRINSIC,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6),
    )
    baseline = float(np.linalg.norm(T))
    print(f"스테레오 재투영오차(px) = {errS:.3f}")
    print(f"베이스라인(두 카메라 거리) = {baseline:.1f} mm")

    # 3) 투영행렬 (좌 카메라 기준)
    P1 = K1 @ np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = K2 @ np.hstack([R, T.reshape(3, 1)])

    np.savez(OUT, K1=K1, d1=d1, K2=K2, d2=d2, R=R, T=T, E=E, F=F,
             P1=P1, P2=P2, image_size=np.array(image_size),
             err_intrinsic_L=errL, err_intrinsic_R=errR, err_stereo=errS,
             baseline_mm=baseline)
    print("저장:", OUT)
    return {
        "ok": True,
        "n_intrinsic_L": len(objL), "n_intrinsic_R": len(objR), "n_stereo": len(s_obj),
        "err_L": round(float(errL), 3), "err_R": round(float(errR), 3),
        "err_stereo": round(float(errS), 3), "baseline_mm": round(baseline, 1),
        "image_size": list(image_size),
    }


def main():
    import json
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
