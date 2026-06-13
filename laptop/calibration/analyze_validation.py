"""
검증 데이터 분석 — measure_data.csv (자세별 관절각 + 마커 3D) → 통계 + 그래프.

생성 결과(docs/image/):
  val-noise.png   측정 반복성(마커별 위치 표준편차)
  val-rigid.png   강체 거리 불변성(같은 링크 마커쌍 거리 vs 자세)
  val-axis-*.png  관절 축 복원(관절 단독 변경 시 마커가 그리는 원 + 피팅)

사용: python calibration/analyze_validation.py <csv경로>
"""
import csv
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT_DIR = r"C:\robotic_arm\docs\image"
JOINTS = ["J1", "J2", "J3", "J4", "J5", "J6"]


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    data = []
    for r in rows:
        ang = {j: float(r[j]) for j in JOINTS if r.get(j) not in (None, "")}
        mk = {}
        for i in range(8):
            try:
                mk[i] = np.array([float(r[f"id{i}_x"]), float(r[f"id{i}_y"]), float(r[f"id{i}_z"])])
            except (ValueError, KeyError):
                pass
        data.append({"ang": ang, "mk": mk})
    return data


def fit_circle_3d(pts):
    """3D 점들 → (중심, 반지름, 축방향, 평면좌표(x,y,cx,cy))."""
    pts = np.array(pts)
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c)
    e1, e2, normal = vt[0], vt[1], vt[2]
    x = (pts - c) @ e1
    y = (pts - c) @ e2
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0], sol[1]
    r = math.sqrt(max(0.0, sol[2] + cx ** 2 + cy ** 2))
    center = c + cx * e1 + cy * e2
    return center, r, normal, (x, y, cx, cy, r)


def fig_noise(data, base_key):
    """반복성: base 자세(동일 관절각)들의 마커별 위치 표준편차."""
    grp = [d for d in data if tuple(sorted(d["ang"].items())) == base_key]
    ids = sorted({i for d in grp for i in d["mk"]})
    sig = []
    for i in ids:
        pts = np.array([d["mk"][i] for d in grp if i in d["mk"]])
        sig.append(float(np.sqrt((pts.std(0) ** 2).sum())) if len(pts) > 1 else 0.0)
    plt.figure(figsize=(6, 3.2))
    plt.bar([f"id{i}" for i in ids], sig, color="#3b82f6")
    plt.axhline(np.mean(sig), color="#ef4444", ls="--", lw=1, label=f"mean {np.mean(sig):.2f} mm")
    plt.ylabel("3D position σ (mm)")
    plt.title(f"Measurement repeatability (n={len(grp)} repeats)")
    plt.legend(); plt.tight_layout()
    p = os.path.join(OUT_DIR, "val-noise.png"); plt.savefig(p, dpi=130); plt.close()
    return p, max(sig), len(grp)


def fig_rigid(data, pairs):
    """강체 거리: 같은 링크 마커쌍 거리 vs 자세."""
    plt.figure(figsize=(7, 3.4))
    summ = []
    for (a, b) in pairs:
        ds, xs = [], []
        for k, d in enumerate(data):
            if a in d["mk"] and b in d["mk"]:
                ds.append(float(np.linalg.norm(d["mk"][a] - d["mk"][b]))); xs.append(k + 1)
        if not ds:
            continue
        ds = np.array(ds)
        plt.plot(xs, ds, "o-", ms=3, label=f"id{a}-id{b}: {ds.mean():.1f}±{ds.std():.2f}mm")
        summ.append((a, b, ds.mean(), ds.std()))
    plt.xlabel("pose index"); plt.ylabel("inter-marker distance (mm)")
    plt.title("Rigid-body distance invariance"); plt.legend(fontsize=8); plt.tight_layout()
    p = os.path.join(OUT_DIR, "val-rigid.png"); plt.savefig(p, dpi=130); plt.close()
    return p, summ


def fig_axis(data, joint, marker, base_key):
    """관절 단독 변경 시 marker가 그리는 원 + 피팅 → 축 복원."""
    others = [j for j in JOINTS if j != joint]
    base = dict(base_key)
    sel = []
    for d in data:
        if marker not in d["mk"] or joint not in d["ang"]:
            continue
        if all(abs(d["ang"].get(o, base.get(o, 90)) - base.get(o, 90)) < 1 for o in others):
            sel.append((d["ang"][joint], d["mk"][marker]))
    sel = {a: p for a, p in sel}  # 각도별 1개(중복 제거)
    if len(sel) < 3:
        return None
    angs = sorted(sel); pts = [sel[a] for a in angs]
    center, r, normal, (x, y, cx, cy, _) = fit_circle_3d(pts)
    plt.figure(figsize=(4.6, 4.4))
    th = np.linspace(0, 2 * np.pi, 200)
    plt.plot(cx + r * np.cos(th), cy + r * np.sin(th), "-", color="#9ca3af", lw=1, label=f"fit r={r:.0f}mm")
    plt.plot(x, y, "o-", color="#3b82f6", ms=6)
    for a, xi, yi in zip(angs, x, y):
        plt.annotate(f"{a:.0f}°", (xi, yi), fontsize=8, xytext=(4, 4), textcoords="offset points")
    plt.plot([cx], [cy], "x", color="#ef4444", ms=10, label="axis center")
    plt.gca().set_aspect("equal"); plt.title(f"{joint} axis recovery (marker id{marker})")
    plt.xlabel("in-plane (mm)"); plt.ylabel("in-plane (mm)"); plt.legend(fontsize=8); plt.tight_layout()
    p = os.path.join(OUT_DIR, f"val-axis-{joint.lower()}.png"); plt.savefig(p, dpi=130); plt.close()
    return p, r, len(angs)


def main(path):
    os.makedirs(OUT_DIR, exist_ok=True)
    data = load(path)
    # base 자세 = 가장 많이 나온 관절각 조합(반복성 그룹)
    from collections import Counter
    keys = Counter(tuple(sorted(d["ang"].items())) for d in data)
    base_key = keys.most_common(1)[0][0]
    print(f"총 {len(data)}자세 · 기준자세 {dict(base_key)} ({keys.most_common(1)[0][1]}회)")

    p, mx, n = fig_noise(data, base_key)
    print(f"[noise] {p}  최대 σ {mx:.2f}mm (반복 {n}회)")
    p, summ = fig_rigid(data, [(1, 2), (3, 4), (5, 6)])
    print(f"[rigid] {p}")
    for a, b, m, s in summ:
        print(f"   id{a}-id{b}: {m:.1f} ± {s:.2f} mm")
    for joint, marker in [("J1", 7), ("J3", 4), ("J4", 6), ("J2", 7)]:
        res = fig_axis(data, joint, marker, base_key)
        if res:
            print(f"[axis {joint}] {res[0]}  반경 {res[1]:.0f}mm ({res[2]}각도)")
        else:
            print(f"[axis {joint}] 데이터 부족(마커 누락/각도<3)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\use08\Downloads\measure_data.csv")
