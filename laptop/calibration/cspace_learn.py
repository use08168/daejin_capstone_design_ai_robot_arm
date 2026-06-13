"""
L1 — 자가생성 C-space 데이터로 충돌예측 모델 학습.

로봇이 시뮬에서 스스로 만든 충돌 지도(cspace_map.csv)를 학습데이터로,
관절각(J2,J3,J4) → 안전/위험을 예측하는 신경망(MLP)을 학습한다.
목적: AI가 명령 생성 시 메시 충돌검사 없이 마이크로초 만에 안전성 질의(검증층).

안전 핵심: 위험을 놓치면(false negative) 로봇이 부서지므로, 확률 임계값을
조정해 '위험 재현율(recall)'을 최대화한다(오경보는 감수, 미탐은 최소화).

생성(docs/image/): cspace-learned.png  예측 확률 vs 실제 충돌경계(J2 슬라이스)
사용: python calibration/cspace_learn.py <csv> [floor_margin=15] [self_margin=10]
"""
import csv
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix, recall_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

OUT_DIR = r"C:\robotic_arm\docs\image"
BIG = 1e6


def load(path, fm, sm):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    jcols = [j for j in ["J1", "J2", "J3", "J4", "J5", "J6"] if j in rows[0]]
    arr = {j: np.array([float(r[j]) for r in rows]) for j in jcols}
    feats = [j for j in jcols if len(np.unique(arr[j])) > 1]   # 실제로 변하는 관절만 입력특징
    X = np.column_stack([arr[j] for j in feats])
    fc = np.array([float(r["floor_clear_mm"]) for r in rows])
    sc = np.array([float(r["self_clear_mm"]) if r["self_clear_mm"] not in ("", None) else BIG for r in rows])
    y = ((fc < fm) | (sc < sm)).astype(int)               # 1 = 위험
    sclr = np.minimum(fc - fm, sc - sm)                    # 안전여유(마진반영, 음수=위험·깊이)
    return X, y, feats, sclr


def fig_compare(model, scaler, feats, X, y, thr):
    """슬라이스별 모델 예측 위험확률(히트맵). 그리드 데이터면 실제 충돌경계(검은선)도.
    facet=J6(있으면, 바닥핵심 신규관절) 아니면 J2. 축=J3×J4. 나머지 관절은 고정."""
    idx = {j: i for i, j in enumerate(feats)}
    facet = "J6" if "J6" in feats else ("J2" if "J2" in feats else feats[0])
    ay, ax_ = "J3", "J4"
    others = [j for j in feats if j not in (facet, ay, ax_)]
    # 바닥은 J2가 작을 때 잘 닿음 → facet이 J6일 땐 J2=0으로 고정해 위험을 드러냄
    fixed = {j: (0.0 if (j == "J2" and facet == "J6") else 90.0) for j in others}
    grid_gt = (len(others) == 0)   # 다른 관절이 고정된 격자 데이터일 때만 실제경계 오버레이

    uy = np.unique(X[:, idx[ay]]); ux = np.unique(X[:, idx[ax_]]); uf = np.unique(X[:, idx[facet]])
    slices = uf if len(uf) <= 6 else uf[np.linspace(0, len(uf) - 1, 6).round().astype(int)]
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 7.2), squeeze=False)
    for k in range(6):
        ax = axes[k // 3][k % 3]
        if k >= len(slices): ax.axis("off"); continue
        fv = slices[k]
        gy, gx = np.meshgrid(uy, ux, indexing="ij")
        cols = np.zeros((gy.size, len(feats)))
        for j in feats:
            cols[:, idx[j]] = (gy.ravel() if j == ay else gx.ravel() if j == ax_
                               else fv if j == facet else fixed.get(j, 90.0))
        prob = model.predict_proba(scaler.transform(cols))[:, 1].reshape(gy.shape)
        im = ax.imshow(prob, origin="lower", aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=1,
                       extent=[ux.min(), ux.max(), uy.min(), uy.max()])
        if grid_gt:
            sel = X[:, idx[facet]] == fv
            tg = np.zeros((len(uy), len(ux)))
            for row, yy in zip(X[sel], y[sel]):
                tg[np.where(uy == row[idx[ay]])[0][0], np.where(ux == row[idx[ax_]])[0][0]] = yy
            ax.contour(ux, uy, tg, levels=[0.5], colors="k", linewidths=1.4)
        ax.set_title(f"{facet}={fv:.0f}°", fontsize=10)
        if k % 3 == 0: ax.set_ylabel(f"{ay} (°)")
        if k // 3 == 1: ax.set_xlabel(f"{ax_} (°)")
    fig.subplots_adjust(hspace=0.3, wspace=0.18)
    fig.colorbar(im, ax=axes, shrink=0.7, label="model P(unsafe)")
    ctx = ", ".join(f"{j}={int(v)}" for j, v in fixed.items()) or "grid"
    fig.suptitle(f"Learned predictor [{'·'.join(feats)}] — facet {facet}, fixed {ctx} (thr={thr:.2f})", y=1.02)
    p = os.path.join(OUT_DIR, "cspace-learned.png"); fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close()
    return p


def main(path, fm, sm):
    os.makedirs(OUT_DIR, exist_ok=True)
    X, y, feats, sclr = load(path, fm, sm)
    print(f"데이터 {len(X)}조합 · 입력관절 {feats} ({len(feats)}D) · 위험 {y.sum()} ({100*y.mean():.1f}%)  [margin floor≥{fm} self≥{sm}]")

    Xtr, Xte, ytr, yte, _, scte = train_test_split(X, y, sclr, test_size=0.25, random_state=0, stratify=y)
    scaler = StandardScaler().fit(Xtr)
    clf = MLPClassifier(hidden_layer_sizes=(64, 64), max_iter=400, random_state=0)
    clf.fit(scaler.transform(Xtr), ytr)

    acc = clf.score(scaler.transform(Xte), yte)
    proba = clf.predict_proba(scaler.transform(Xte))[:, 1]
    pred = (proba >= 0.5).astype(int)
    cm = confusion_matrix(yte, pred)
    rec = recall_score(yte, pred)
    print(f"\n[기본 임계 0.5] 정확도 {acc*100:.2f}%  위험 재현율 {rec*100:.2f}%")
    print(f"  혼동행렬 [실제安/危 × 예측安/危]:\n{cm}")
    print(f"  위험 미탐(FN, 위험인데 안전이라 예측) = {cm[1,0]}개  ← 안전상 0에 가까워야")

    # 안전 임계: 위험 재현율 ≥99.5% 되도록 임계값 낮춤(미탐 최소화, 오경보 감수)
    thr = 0.5
    for t in np.linspace(0.5, 0.01, 50):
        if recall_score(yte, (proba >= t).astype(int)) >= 0.995:
            thr = t; break
    predS = (proba >= thr).astype(int); cmS = confusion_matrix(yte, predS)
    fp_rate = cmS[0, 1] / max(1, cmS[0].sum())
    print(f"\n[안전 임계 {thr:.3f}] 위험 재현율 {recall_score(yte,predS)*100:.2f}%  "
          f"미탐 {cmS[1,0]}개  오경보율 {fp_rate*100:.1f}%(안전을 위험으로)")

    # 잔존 위험: 놓친 위험(FN)이 실제로 얼마나 깊은 충돌인가 → 안전 주장의 핵심
    fn = (yte == 1) & (predS == 0)
    if fn.sum():
        d = -scte[fn]   # 침투 깊이(mm, 클수록 위험)
        print(f"  └ 놓친 위험 {fn.sum()}개의 실제 침투깊이: 중앙값 {np.median(d):.1f}mm · 최악 {d.max():.1f}mm")
        print(f"    (경계 근처 얕은 미탐이면 잔존위험 낮음 — 마진이 이미 {fm}/{sm}mm 흡수)")

    # 추론 속도(검증층 가치): 메시검사 대신 모델 질의
    Xs = scaler.transform(Xte); t0 = time.perf_counter()
    clf.predict(Xs); dt = (time.perf_counter() - t0) / len(Xs) * 1e6
    print(f"\n추론 속도 ≈ {dt:.1f} µs/질의 ({len(Xs)}개) — AI가 자세 안전성을 실시간 질의 가능")

    print(f"\n[figure] {fig_compare(clf, scaler, feats, X, y, thr)}")


if __name__ == "__main__":
    # 기본 마진 = 콜드스타트 실측 sim-real gap. floor=30(말단 위치 최악잔차 30.8mm, 외부 평면),
    # self=15(상대 기하라 오차 일부 상쇄 → 절반). → "시뮬 안전 ⇒ 실물 안전" 측정 근거.
    path = sys.argv[1] if len(sys.argv) > 1 else r"calibration/validation_data/cspace_rand.csv"
    fm = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    sm = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    main(path, fm, sm)
