"""
C-space 충돌 지도 분석 — 시뮬 스윕 결과(cspace_map.csv) → 통계 + 히트맵/3D.

입력 CSV(4페이지 'C-space 스윕' 버튼이 생성):
  J2,J3,J4,floor_clear_mm,self_clear_mm,self_target,collision
    floor_clear_mm : 바닥 여유(음수=바닥 침범)
    self_clear_mm  : 자기충돌 여유(음수=링크 침투, 빈칸=대상없음/안전)
    collision      : 마진0 기준 충돌 여부(0/1)

생성(docs/image/):
  cspace-heatmap.png  J2 슬라이스별 J3×J4 안전여유 히트맵 + 충돌경계
  cspace-3d.png       (J2,J3,J4) 안전/충돌 3D 산점

마진(#4 콜드스타트 sim-real gap 연동): 안전 = floor_clear≥FM 그리고 self_clear≥SM.
사용: python calibration/cspace_analysis.py <csv> [floor_margin=15] [self_margin=10]
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
BIG = 1e6   # self_clear 빈칸 = 대상 없음 = 충분히 안전


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    J2 = np.array([float(r["J2"]) for r in rows])
    J3 = np.array([float(r["J3"]) for r in rows])
    J4 = np.array([float(r["J4"]) for r in rows])
    fc = np.array([float(r["floor_clear_mm"]) for r in rows])
    sc = np.array([float(r["self_clear_mm"]) if r["self_clear_mm"] not in ("", None) else BIG for r in rows])
    return J2, J3, J4, fc, sc


def fig_heatmap(J2, J3, J4, fc, sc, fm, sm):
    """J2 슬라이스별 J3×J4 안전여유(마진 반영) 히트맵."""
    clr = np.minimum(fc - fm, sc - sm)           # 마진 반영 여유(음수=위험)
    u2 = np.unique(J2); u3 = np.unique(J3); u4 = np.unique(J4)
    slices = u2 if len(u2) <= 6 else u2[np.linspace(0, len(u2) - 1, 6).round().astype(int)]
    ncol = min(3, len(slices)); nrow = int(math.ceil(len(slices) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.6 * nrow), squeeze=False)
    vmax = max(10, np.percentile(np.abs(clr), 95))
    for k, a2 in enumerate(slices):
        ax = axes[k // ncol][k % ncol]
        grid = np.full((len(u3), len(u4)), np.nan)
        sel = J2 == a2
        for j3, j4, c in zip(J3[sel], J4[sel], clr[sel]):
            grid[np.where(u3 == j3)[0][0], np.where(u4 == j4)[0][0]] = c
        im = ax.imshow(grid, origin="lower", aspect="auto", cmap="RdYlGn",
                       vmin=-vmax, vmax=vmax,
                       extent=[u4.min(), u4.max(), u3.min(), u3.max()])
        # 충돌 경계(여유=0)
        ax.contour(np.linspace(u4.min(), u4.max(), len(u4)),
                   np.linspace(u3.min(), u3.max(), len(u3)), grid,
                   levels=[0], colors="k", linewidths=1.2)
        ax.set_title(f"J2={a2:.0f}°", fontsize=10)
        if k % ncol == 0:
            ax.set_ylabel("J3 (°)")
        if k // ncol == nrow - 1:
            ax.set_xlabel("J4 (°)")
    for k in range(len(slices), nrow * ncol):
        axes[k // ncol][k % ncol].axis("off")
    fig.subplots_adjust(hspace=0.32, wspace=0.18)
    fig.colorbar(im, ax=axes, shrink=0.7, label="safety clearance (mm, <0 = unsafe)")
    fig.suptitle(f"C-space safety map (margin floor≥{fm} self≥{sm} mm)", y=1.02)
    p = os.path.join(OUT_DIR, "cspace-heatmap.png"); fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close()
    return p


def fig_3d(J2, J3, J4, fc, sc, fm, sm):
    """(J2,J3,J4) 안전(초록)/위험(빨강) 3D 산점."""
    unsafe = (fc < fm) | (sc < sm)
    fig = plt.figure(figsize=(7, 6)); ax = fig.add_subplot(111, projection="3d")
    ax.scatter(J2[~unsafe], J3[~unsafe], J4[~unsafe], s=6, c="#22c55e", alpha=0.25, label="safe")
    ax.scatter(J2[unsafe], J3[unsafe], J4[unsafe], s=10, c="#ef4444", alpha=0.7, label="unsafe")
    ax.set_xlabel("J2 (°)"); ax.set_ylabel("J3 (°)"); ax.set_zlabel("J4 (°)")
    ax.set_title(f"C-space: {(~unsafe).sum()} safe / {unsafe.sum()} unsafe configs")
    ax.legend(); ax.view_init(elev=20, azim=-60)
    p = os.path.join(OUT_DIR, "cspace-3d.png"); fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close()
    return p


def main(path, fm, sm):
    os.makedirs(OUT_DIR, exist_ok=True)
    J2, J3, J4, fc, sc = load(path)
    n = len(J2)
    raw = ((fc < 0) | (sc < 0)).sum()
    marg = ((fc < fm) | (sc < sm)).sum()
    floor_only = (fc < fm).sum(); self_only = (sc < sm).sum()
    print(f"총 {n}조합 (J2×J3×J4)")
    print(f"  마진0 충돌      : {raw} ({100*raw/n:.1f}%)")
    print(f"  마진반영 위험   : {marg} ({100*marg/n:.1f}%)  [floor≥{fm} self≥{sm} mm]")
    print(f"    └ 바닥 위반   : {floor_only}   자기충돌 위반: {self_only}")
    print(f"  안전 영역       : {n-marg} ({100*(n-marg)/n:.1f}%)")
    print(f"[heatmap] {fig_heatmap(J2, J3, J4, fc, sc, fm, sm)}")
    print(f"[3d]      {fig_3d(J2, J3, J4, fc, sc, fm, sm)}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\use08\Downloads\cspace_map.csv"
    fm = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0   # 콜드스타트 실측 sim-real gap
    sm = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    main(path, fm, sm)
