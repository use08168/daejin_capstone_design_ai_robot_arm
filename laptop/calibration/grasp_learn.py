"""
L1 — 자가생성 파지 데이터로 '물체 → 파지' 모델 학습.

시뮬레이터가 접촉검출(C)로 스스로 라벨링한 파지 지도(grasp_learn.csv)를 학습데이터로,
  ① 분류기: 물체(위치·형상·크기) → 파지 가능?(success)
  ② 회귀기: 물체 → 파지 자세(관절각 J1..J6, 성공 샘플만)
를 학습한다. C-space 충돌예측(cspace_learn.py)과 동일한 레시피를 파지에 적용.

목적: 물체를 두면 수천 자세를 검색하지 않고 즉시 '잡을 수 있나 + 어떤 자세로'를 추론(검증층).
런타임: 물체3D → 분류기로 가능여부 → 회귀기로 파지자세 초기값 → IK/검색으로 미세보정 → 실행.

생성(docs/image/): grasp-learned.png  워크스페이스 슬라이스의 예측 파지가능확률 + 실제 성공/실패점
저장(calibration/): grasp_model.joblib  (분류기·회귀기·스케일러·특징목록)
사용: python calibration/grasp_learn.py <grasp_learn.csv>
"""
import csv
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 라벨(Windows)
matplotlib.rcParams["axes.unicode_minus"] = False
import numpy as np
from sklearn.metrics import confusion_matrix, mean_absolute_error, recall_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler

OUT_DIR = r"C:\robotic_arm\docs\image"
MODEL_PATH = os.path.join(os.path.dirname(__file__), "grasp_model.joblib")
# approach(0=수직·1=수평)를 입력특징에 포함 → per-approach 파지가능 + 접근 선택(argmax) 학습
FEATS = ["obj_x", "obj_y", "obj_z", "type", "R", "H", "approach"]
JCOLS = ["J1", "J2", "J3", "J4", "J5", "J6"]


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if "approach" not in rows[0]:
        sys.exit("⚠ 구형 CSV(approach 열 없음) — 4페이지 Ctrl+F5 후 재생성 필요")
    X = np.array([[float(r[f]) for f in FEATS] for r in rows], dtype=float)
    y = np.array([int(float(r["success"])) for r in rows], dtype=int)
    ap = X[:, FEATS.index("approach")].astype(int)
    mask = y == 1
    Js = np.array([[float(r[j]) for j in JCOLS] for r in rows if int(float(r["success"])) == 1], dtype=float)
    return X, y, ap, X[mask], Js, rows


def train_classifier(X, y, ap):
    Xtr, Xte, ytr, yte, _, ate = train_test_split(X, y, ap, test_size=0.2, random_state=0, stratify=y)
    sc = StandardScaler().fit(Xtr)
    clf = MLPClassifier(hidden_layer_sizes=(64, 64), max_iter=600, random_state=0)
    t0 = time.time(); clf.fit(sc.transform(Xtr), ytr); dt = time.time() - t0
    pred = clf.predict(sc.transform(Xte))
    acc = (pred == yte).mean()
    rec_yes = recall_score(yte, pred, pos_label=1)   # 잡을 수 있는걸 놓치지 않는 비율
    rec_no = recall_score(yte, pred, pos_label=0)
    print(f"[분류] (물체+접근)→파지가능 · 학습 {dt:.1f}s · 테스트 정확도 {acc*100:.1f}%")
    print(f"        파지가능 재현율 {rec_yes*100:.1f}% · 불가 재현율 {rec_no*100:.1f}%")
    for a, nm in [(0, "수직"), (1, "수평")]:
        m = ate == a
        if m.any():
            print(f"        {nm} 접근 정확도 {(pred[m] == yte[m]).mean()*100:.1f}% ({m.sum()}개)")
    return clf, sc, acc


def eval_approach_selection(clf, sc, X, y, ap):
    """물체별로 모델이 더 잘 잡을 접근(argmax P)을 고르고, 실제 라벨과 비교 — '접근 선택' 정확도.
    각 물체의 수직행·수평행을 짝지어, 한쪽만 성공하는 결정적 물체에서 옳게 고르는지 본다."""
    key = {}
    for i in range(len(X)):
        k = (round(X[i, 0], 1), round(X[i, 1], 1), round(X[i, 2], 1))
        key.setdefault(k, {})[int(ap[i])] = (X[i], y[i])
    pv = clf.predict_proba(sc.transform(X))[:, 1]
    pmap = {}
    for i in range(len(X)):
        k = (round(X[i, 0], 1), round(X[i, 1], 1), round(X[i, 2], 1))
        pmap.setdefault(k, {})[int(ap[i])] = pv[i]
    dec = ok = 0
    for k, d in key.items():
        if 0 in d and 1 in d:
            yv, yh = d[0][1], d[1][1]
            if yv != yh:                       # 결정적(한쪽만 성공)
                dec += 1
                pick = 0 if pmap[k][0] >= pmap[k][1] else 1
                if (pick == 0 and yv == 1) or (pick == 1 and yh == 1):
                    ok += 1
    if dec:
        print(f"[접근선택] 결정적 물체(한쪽만 가능) {dec}개 중 옳은 접근 선택 {ok} ({100*ok/dec:.1f}%)")


def train_regressor(Xs, Js):
    if len(Xs) < 30:
        print(f"[회귀] 성공 샘플 부족({len(Xs)}) — 건너뜀")
        return None, None
    Xtr, Xte, Jtr, Jte = train_test_split(Xs, Js, test_size=0.2, random_state=0)
    sc = StandardScaler().fit(Xtr)
    reg = MLPRegressor(hidden_layer_sizes=(128, 128), max_iter=1500, random_state=0)
    t0 = time.time(); reg.fit(sc.transform(Xtr), Jtr); dt = time.time() - t0
    pred = reg.predict(sc.transform(Xte))
    mae = mean_absolute_error(Jte, pred)
    per = [mean_absolute_error(Jte[:, k], pred[:, k]) for k in range(6)]
    print(f"[회귀] 학습 {dt:.1f}s · 관절각 MAE {mae:.1f}° (성공 {len(Xs)}샘플)")
    print("        관절별 MAE(°): " + " ".join(f"J{k+1}={per[k]:.0f}" for k in range(6)))
    print("        ※ 같은 물체에 여러 파지(다봉)가 있어 MAE가 크면, 런타임에 IK/검색으로 미세보정 전제")
    return reg, sc


def fig_maps(clf, sc, X, y, ap):
    """수직/수평 각각의 파지가능확률 맵(워크스페이스 x-z 슬라이스) + 실제 성공(○)/실패(×)점."""
    ix, iy, iz = 0, 1, 2
    ymid = np.median(X[:, iy]); Rm, Hm = np.median(X[:, 4]), np.median(X[:, 5])
    gx = np.linspace(X[:, ix].min(), X[:, ix].max(), 90)
    gz = np.linspace(X[:, iz].min(), X[:, iz].max(), 90)
    GX, GZ = np.meshgrid(gx, gz)
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 6.2))
    for a, nm, axp in [(0, "수직 top-down", axes[0]), (1, "수평 side", axes[1])]:
        grid = np.column_stack([GX.ravel(), np.full(GX.size, ymid), GZ.ravel(),
                                np.zeros(GX.size), np.full(GX.size, Rm), np.full(GX.size, Hm),
                                np.full(GX.size, a)])
        P = clf.predict_proba(sc.transform(grid))[:, 1].reshape(GX.shape)
        im = axp.contourf(GX, GZ, P, levels=np.linspace(0, 1, 21), cmap="RdYlGn")
        near = (np.abs(X[:, iy] - ymid) < 60) & (ap == a)
        s, f = near & (y == 1), near & (y == 0)
        axp.scatter(X[s, ix], X[s, iz], s=9, c="#063", marker="o", linewidths=0)
        axp.scatter(X[f, ix], X[f, iz], s=14, c="k", marker="x", linewidths=0.8)
        axp.set_title(f"{nm} 파지가능확률 (y≈{ymid:.0f}, R≈{Rm:.0f})")
        axp.set_xlabel("obj_x (mm)"); axp.set_ylabel("obj_z (mm)")
        fig.colorbar(im, ax=axp, label="P(파지 가능)")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "grasp-learned.png")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    print(f"[그림] {out}  (좌=수직·우=수평 capability map)")


def fig_3d(clf, sc, X):
    """워크스페이스 3D 격자에서 파지가능 영역을 점구름으로 — 색=어느 접근(파랑 수직만·초록 수평만·청록 둘다)."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (projection='3d' 등록)
    Rm, Hm = np.median(X[:, 4]), np.median(X[:, 5])
    gx = np.linspace(X[:, 0].min(), X[:, 0].max(), 30)
    gy = np.linspace(X[:, 1].min(), X[:, 1].max(), 30)
    gz = np.linspace(X[:, 2].min(), X[:, 2].max(), 30)
    GX, GY, GZ = np.meshgrid(gx, gy, gz, indexing="ij")
    pts = np.column_stack([GX.ravel(), GY.ravel(), GZ.ravel()])

    def predP(a):
        grid = np.column_stack([pts, np.zeros(len(pts)), np.full(len(pts), Rm),
                                np.full(len(pts), Hm), np.full(len(pts), a)])
        return clf.predict_proba(sc.transform(grid))[:, 1]

    pv, ph = predP(0), predP(1)
    both = (pv > 0.5) & (ph > 0.5)
    vonly = (pv > 0.5) & (ph <= 0.5)
    honly = (ph > 0.5) & (pv <= 0.5)
    fig = plt.figure(figsize=(10, 8.5))
    ax = fig.add_subplot(111, projection="3d")
    # '둘다'는 흐린 배경, '한쪽만'(접근이 갈리는 결정적 영역)은 진하게 강조
    for m, c, lab, a, s in [(both, "#15b5b0", "둘 다 가능", 0.06, 5),
                            (vonly, "#1f4fff", "수직만", 0.7, 13),
                            (honly, "#2ca02c", "수평만", 0.7, 13)]:
        ax.scatter(pts[m, 0], pts[m, 1], pts[m, 2], c=c, s=s, alpha=a, depthshade=True, label=f"{lab} ({m.sum()})")
    ax.scatter([0], [0], [0], c="k", marker="^", s=70, label="로봇 베이스")
    ax.set_title(f"학습된 3D 파지가능 영역 (R≈{Rm:.0f}·H≈{Hm:.0f}mm) — 색=접근")
    ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)"); ax.set_zlabel("z (mm)")
    ax.legend(loc="upper left", fontsize=8); ax.view_init(elev=22, azim=-60)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "grasp-learned-3d.png")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    print(f"[그림] {out}  (3D 파지가능 영역 · 접근별 색)")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\use08\Downloads\grasp_learn.csv"
    X, y, ap, Xs, Js, rows = load(path)
    nv, nh = (ap == 0).sum(), (ap == 1).sum()
    print(f"데이터 {len(rows)}행 · 수직 {nv}(성공 {int(y[ap==0].sum())}) · 수평 {nh}(성공 {int(y[ap==1].sum())}) · 특징 {FEATS}")
    clf, csc, acc = train_classifier(X, y, ap)
    eval_approach_selection(clf, csc, X, y, ap)
    reg, rsc = train_regressor(Xs, Js)
    fig_maps(clf, csc, X, y, ap)
    fig_3d(clf, csc, X)
    joblib.dump({"clf": clf, "clf_scaler": csc, "reg": reg, "reg_scaler": rsc,
                 "feats": FEATS, "jcols": JCOLS}, MODEL_PATH)
    print(f"[저장] {MODEL_PATH}")
    print("런타임: 물체→ clf(수직)·clf(수평) 확률 비교 → 더 높은(가능한) 접근 선택 → 검색/IK로 정밀화")


if __name__ == "__main__":
    main()
