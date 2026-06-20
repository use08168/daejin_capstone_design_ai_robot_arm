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
FEATS = ["obj_x", "obj_y", "obj_z", "type", "R", "H"]   # 모델 입력특징
JCOLS = ["J1", "J2", "J3", "J4", "J5", "J6"]


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    X = np.array([[float(r[f]) for f in FEATS] for r in rows], dtype=float)
    y = np.array([int(float(r["success"])) for r in rows], dtype=int)
    # 회귀 타깃(성공 샘플만): 파지 관절각
    mask = y == 1
    Js = np.array([[float(r[j]) for j in JCOLS] for r in rows if int(float(r["success"])) == 1], dtype=float)
    return X, y, X[mask], Js, rows


def train_classifier(X, y):
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    sc = StandardScaler().fit(Xtr)
    clf = MLPClassifier(hidden_layer_sizes=(64, 64), max_iter=600, random_state=0)
    t0 = time.time(); clf.fit(sc.transform(Xtr), ytr); dt = time.time() - t0
    pred = clf.predict(sc.transform(Xte))
    acc = (pred == yte).mean()
    rec_yes = recall_score(yte, pred, pos_label=1)   # 잡을 수 있는걸 놓치지 않는 비율
    rec_no = recall_score(yte, pred, pos_label=0)
    cm = confusion_matrix(yte, pred)
    print(f"[분류] 학습 {dt:.1f}s · 테스트 정확도 {acc*100:.1f}%")
    print(f"        파지가능 재현율 {rec_yes*100:.1f}% · 불가 재현율 {rec_no*100:.1f}%")
    print(f"        혼동행렬 [TN FP; FN TP] = {cm.tolist()}")
    return clf, sc, acc


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


def fig_map(clf, sc, X, y):
    """워크스페이스 x-z 슬라이스(중앙 y)의 예측 파지가능확률 + 실제 성공(○)/실패(×)점."""
    ix, iy, iz = 0, 1, 2
    ymid = np.median(X[:, iy])
    Rm, Hm = np.median(X[:, 4]), np.median(X[:, 5])
    gx = np.linspace(X[:, ix].min(), X[:, ix].max(), 90)
    gz = np.linspace(X[:, iz].min(), X[:, iz].max(), 90)
    GX, GZ = np.meshgrid(gx, gz)
    grid = np.column_stack([GX.ravel(), np.full(GX.size, ymid), GZ.ravel(),
                            np.zeros(GX.size), np.full(GX.size, Rm), np.full(GX.size, Hm)])
    P = clf.predict_proba(sc.transform(grid))[:, 1].reshape(GX.shape)
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    im = ax.contourf(GX, GZ, P, levels=np.linspace(0, 1, 21), cmap="RdYlGn")
    near = np.abs(X[:, iy] - ymid) < 60   # 슬라이스 근처 실제점만
    s, f = near & (y == 1), near & (y == 0)
    ax.scatter(X[s, ix], X[s, iz], s=9, c="#063", marker="o", label="실제 파지성공", linewidths=0)
    ax.scatter(X[f, ix], X[f, iz], s=14, c="k", marker="x", label="실제 실패", linewidths=0.8)
    ax.set_title(f"학습된 파지가능확률 (y≈{ymid:.0f}mm 슬라이스, R≈{Rm:.0f})")
    ax.set_xlabel("obj_x (mm)"); ax.set_ylabel("obj_z (mm)"); ax.legend(loc="upper right", fontsize=8)
    fig.colorbar(im, ax=ax, label="P(파지 가능)")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "grasp-learned.png")
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)
    print(f"[그림] {out}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\use08\Downloads\grasp_learn.csv"
    X, y, Xs, Js, rows = load(path)
    print(f"데이터 {len(rows)}행 · 파지가능 {int(y.sum())} ({100*y.mean():.0f}%) · 입력특징 {FEATS}")
    clf, csc, acc = train_classifier(X, y)
    reg, rsc = train_regressor(Xs, Js)
    fig_map(clf, csc, X, y)
    joblib.dump({"clf": clf, "clf_scaler": csc, "reg": reg, "reg_scaler": rsc,
                 "feats": FEATS, "jcols": JCOLS}, MODEL_PATH)
    print(f"[저장] {MODEL_PATH}")
    print("다음: 능동학습(모델이 애매한 물체 골라 재라벨) → 런타임 'AI 파지 제안'")


if __name__ == "__main__":
    main()
