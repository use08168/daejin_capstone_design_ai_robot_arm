"""
능동학습(Active Learning) — 모델이 스스로 '헷갈리는 자세'를 골라 라벨링.

원리: 결정경계 근처(P(위험)≈0.5)의 불확실한 자세를 우선 라벨링하면,
균일 랜덤보다 적은 데이터로 같은 정확도에 도달한다(데이터 효율).
+ "모델이 무엇을 배울지 스스로 결정" = 자가학습 서사 강화.

여기선 이미 모은 C-space 데이터를 '오라클 풀'로 써서 루프를 완결한다(브라우저 왕복 X):
  소량 시드 → 학습 → 풀에서 가장 불확실한 N개 선택 → 라벨 공개 → 추가 → 반복.
균일 랜덤 샘플링과 공정 비교(같은 시드·예산) → 학습곡선으로 효율 입증.

실제 운용(풀 밖 새 자세)에선 이 '라벨 공개'를 4페이지 시뮬 충돌검사가 대신한다.

생성(docs/image/): cspace-active.png  능동 vs 랜덤 학습곡선(위험 재현율·정확도 vs 라벨수)
사용: python calibration/cspace_active.py <csv> [floor_margin=30] [self_margin=15]
"""
import csv
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import recall_score

OUT_DIR = r"C:\robotic_arm\docs\image"
BIG = 1e6
SEED, STEP, ROUNDS, TESTN = 1000, 1000, 12, 20000


def load(path, fm, sm):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    jcols = [j for j in ["J1", "J2", "J3", "J4", "J5", "J6"] if j in rows[0]]
    arr = {j: np.array([float(r[j]) for r in rows]) for j in jcols}
    feats = [j for j in jcols if len(np.unique(arr[j])) > 1]
    X = np.column_stack([arr[j] for j in feats])
    fc = np.array([float(r["floor_clear_mm"]) for r in rows])
    sc = np.array([float(r["self_clear_mm"]) if r["self_clear_mm"] not in ("", None) else BIG for r in rows])
    y = ((fc < fm) | (sc < sm)).astype(int)
    return X, y, feats


def _fit(Xtr, ytr):
    clf = RandomForestClassifier(n_estimators=120, n_jobs=-1, random_state=0)
    clf.fit(Xtr, ytr)
    return clf


def _run_once(X, y, Xte, yte, rest, strategy, seed):
    rng = np.random.RandomState(seed)
    perm = rng.permutation(rest)
    labeled = list(perm[:SEED]); pool = list(perm[SEED:])
    curve = []
    for rd in range(ROUNDS + 1):
        clf = _fit(X[labeled], y[labeled])
        p = clf.predict(Xte)
        curve.append((len(labeled), (p == yte).mean(), recall_score(yte, p)))
        if rd == ROUNDS or not pool:
            break
        if strategy == "active":
            prob = clf.predict_proba(X[pool])[:, 1]
            pick = np.argsort(-np.abs(prob - 0.5))[-STEP:]   # 0.5에 가까운(불확실) STEP개
        else:
            pick = rng.choice(len(pool), min(STEP, len(pool)), replace=False)
        chosen = [pool[i] for i in pick]
        labeled += chosen
        pset = set(chosen); pool = [i for i in pool if i not in pset]
    return np.array(curve)


def run(X, y, Xte, yte, rest, strategy, nseeds=3):
    """nseeds회 평균 → 분산 줄여 능동 vs 랜덤 추세를 깨끗이."""
    curves = [_run_once(X, y, Xte, yte, rest, strategy, s) for s in range(nseeds)]
    return np.mean(curves, axis=0)   # (rounds, 3): n, acc, recall


def main(path, fm, sm):
    os.makedirs(OUT_DIR, exist_ok=True)
    X, y, feats = load(path, fm, sm)
    print(f"데이터 {len(X)} · {feats} · 위험 {100*y.mean():.1f}%  [margin {fm}/{sm}]")

    rng = np.random.RandomState(0)
    idx = rng.permutation(len(X))
    test, rest = idx[:TESTN], idx[TESTN:]
    Xte, yte = X[test], y[test]

    cur_a = run(X, y, Xte, yte, rest, "active")
    cur_r = run(X, y, Xte, yte, rest, "random")

    # 효율: 랜덤 최종 재현율에 능동이 몇 라벨에 도달?
    final_r = cur_r[-1][2]; total = cur_r[-1][0]
    reach = next((n for n, a, rc in cur_a if rc >= final_r), total)
    print(f"\n랜덤 최종({int(total)}라벨) 위험재현율 {final_r*100:.1f}%")
    print(f"능동은 {int(reach)}라벨에서 도달 → 라벨 {100*(1-reach/total):.0f}% 절약")
    print(f"\n[라벨수] 능동재현율 / 랜덤재현율")
    for (n, _, ra), (_, _, rr) in zip(cur_a, cur_r):
        print(f"  {int(n):5d}: {ra*100:5.1f}% / {rr*100:5.1f}%")

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    na = [c[0] for c in cur_a]
    ax[0].plot(na, [c[2] for c in cur_a], "o-", color="#ef4444", label="active (uncertainty)")
    ax[0].plot([c[0] for c in cur_r], [c[2] for c in cur_r], "s--", color="#3b82f6", label="random")
    ax[0].set_title("Unsafe recall (safety)"); ax[0].set_xlabel("# labels"); ax[0].set_ylabel("recall"); ax[0].legend(); ax[0].grid(alpha=0.3)
    ax[1].plot(na, [c[1] for c in cur_a], "o-", color="#ef4444", label="active")
    ax[1].plot([c[0] for c in cur_r], [c[1] for c in cur_r], "s--", color="#3b82f6", label="random")
    ax[1].set_title("Accuracy"); ax[1].set_xlabel("# labels"); ax[1].set_ylabel("accuracy"); ax[1].legend(); ax[1].grid(alpha=0.3)
    fig.suptitle("Active learning vs random — collision predictor data efficiency")
    fig.tight_layout()
    p = os.path.join(OUT_DIR, "cspace-active.png"); fig.savefig(p, dpi=130); plt.close()
    print(f"\n[figure] {p}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"calibration/validation_data/cspace_rand_100k.csv"
    fm = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    sm = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    main(path, fm, sm)
