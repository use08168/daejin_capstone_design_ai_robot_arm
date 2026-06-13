"""
실운용 능동학습 루프 — Python(질의 생성) ↔ 4페이지 시뮬(라벨링) 왕복.

소량 시드에서 시작해, 매 라운드 '모델이 가장 헷갈리는 자세'를 골라 시뮬로 라벨링하고
누적·재학습한다. 라벨이 풀 안이 아니라 '새로 생성된 자세'라는 점이 데모(cspace_active.py)와 다른 실운용.

상태: calibration/active/labeled.csv (누적), history.csv (라운드 지표)
오라클(고정 평가셋): cspace_rand_100k.csv

워크플로:
  1) python cspace_active_loop.py init  2000      → active/cspace_query.csv (랜덤 시드)
  2) 4페이지 제어 → 🏷 질의 라벨링 → 그 csv 선택 → cspace_labeled.csv 다운로드
  3) python cspace_active_loop.py merge <labeled.csv 경로>   → 누적·재학습·지표
  4) python cspace_active_loop.py query 1000       → active/cspace_query.csv (불확실 자세)
  5) (2)~(4) 반복 …    마지막에  python cspace_active_loop.py plot
"""
import csv
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "active")
LABELED = os.path.join(DIR, "labeled.csv")
HIST = os.path.join(DIR, "history.csv")
QUERY = os.path.join(DIR, "cspace_query.csv")
ORACLE = os.path.join(HERE, "validation_data", "cspace_rand_100k.csv")
FEATS = ["J2", "J3", "J4", "J5", "J6"]   # J1=수직축→고정
RANGE = (0.0, 180.0)
FM, SM, BIG = 30.0, 15.0, 1e6


def _xy(rows):
    X = np.array([[float(r[j]) for j in FEATS] for r in rows])
    fc = np.array([float(r["floor_clear_mm"]) for r in rows])
    sc = np.array([float(r["self_clear_mm"]) if r.get("self_clear_mm") not in ("", None) else BIG for r in rows])
    return X, ((fc < FM) | (sc < SM)).astype(int)


def _read(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def _write_query(configs):
    os.makedirs(DIR, exist_ok=True)
    with open(QUERY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["J1", "J2", "J3", "J4", "J5", "J6"])
        for c in configs:
            w.writerow([90] + [round(v, 1) for v in c])
    print(f"질의 {len(configs)}개 → {QUERY}")
    print("→ 4페이지 제어 → 🏷 질의 라벨링 → 이 파일 선택 → cspace_labeled.csv 다운로드")


def _train(X, y):
    sc = StandardScaler().fit(X)
    clf = MLPClassifier(hidden_layer_sizes=(64, 64), max_iter=400, random_state=0)
    clf.fit(sc.transform(X), y)
    return clf, sc


def init(n):
    rng = np.random.RandomState(0)
    _write_query(rng.uniform(*RANGE, size=(n, len(FEATS))))


def query(n):
    rows = _read(LABELED)
    X, y = _xy(rows)
    clf, sc = _train(X, y)
    rng = np.random.RandomState(len(rows))               # 라운드마다 다른 후보
    pool = rng.uniform(*RANGE, size=(max(50 * n, 20000), len(FEATS)))
    prob = clf.predict_proba(sc.transform(pool))[:, 1]
    pick = np.argsort(np.abs(prob - 0.5))[:n]             # 0.5에 가장 가까운(불확실) n개
    _write_query(pool[pick])


def _eval(clf, sc):
    Xo, yo = _xy(_read(ORACLE))
    p = clf.predict(sc.transform(Xo))
    tp = int(((p == 1) & (yo == 1)).sum()); fn = int(((p == 0) & (yo == 1)).sum())
    return (p == yo).mean(), tp / max(1, tp + fn)


def merge(path):
    new = _read(path)
    os.makedirs(DIR, exist_ok=True)
    exist = _read(LABELED) if os.path.exists(LABELED) else []
    allrows = exist + new
    cols = ["J1", "J2", "J3", "J4", "J5", "J6", "floor_clear_mm", "self_clear_mm", "self_target", "collision"]
    with open(LABELED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(allrows)
    X, y = _xy(allrows)
    clf, sc = _train(X, y)
    acc, rec = _eval(clf, sc)
    rnd = (sum(1 for _ in open(HIST)) if os.path.exists(HIST) else 1)
    print(f"누적 {len(allrows)}개(+{len(new)}) · 위험 {100*y.mean():.1f}%")
    print(f"오라클 평가: 정확도 {acc*100:.2f}%  위험재현율 {rec*100:.2f}%")
    new_hist = not os.path.exists(HIST)
    with open(HIST, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_hist: w.writerow(["round", "n_labeled", "accuracy", "recall"])
        w.writerow([rnd, len(allrows), round(acc, 4), round(rec, 4)])


def plot():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    h = _read(HIST)
    n = [int(r["n_labeled"]) for r in h]; rec = [float(r["recall"]) for r in h]; acc = [float(r["accuracy"]) for r in h]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].plot(n, rec, "o-", color="#ef4444"); ax[0].set_title("Unsafe recall (oracle)"); ax[0].set_xlabel("# labels"); ax[0].grid(alpha=0.3)
    ax[1].plot(n, acc, "o-", color="#3b82f6"); ax[1].set_title("Accuracy (oracle)"); ax[1].set_xlabel("# labels"); ax[1].grid(alpha=0.3)
    fig.suptitle("Real active-learning loop — self-improvement per round"); fig.tight_layout()
    p = os.path.join(r"C:\robotic_arm\docs\image", "cspace-active-loop.png"); fig.savefig(p, dpi=130); plt.close()
    print(f"[figure] {p}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "init"
    if mode == "init": init(int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
    elif mode == "query": query(int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
    elif mode == "merge": merge(sys.argv[2])
    elif mode == "plot": plot()
    else: print("모드: init N | query N | merge <csv> | plot")
