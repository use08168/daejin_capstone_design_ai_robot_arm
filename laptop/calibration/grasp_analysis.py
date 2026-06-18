"""
파지 데이터셋 분석 — 시뮬 스윕 결과(grasp_dataset.csv) → 도달영역(reachable workspace) 3D 그래프 + 통계.

입력 CSV(4페이지 '파지 스윕(J1~J6)' 버튼이 생성):
  J1..J6, tcp_x, tcp_y, tcp_z, app_x, app_y, app_z, floor_clear_mm, self_clear_mm, collision
    tcp_*       : 그리퍼 중심(TCP) 월드 위치 (mm). y가 위(바닥 y=0).
    app_*       : 접근 단위벡터. 수직(top-down) 파지 app_y≈-1, 수평 |app_y|≈0.
    collision   : 1=바닥/자기 충돌(잡기 불가 자세)

도달영역 = 충돌 없는 자세의 TCP 점군. 큰 샘플(10만+)일수록 작업공간 외형이 또렷해짐.
파지방향 분류: 수직(app_y<-0.6) / 수평(|app_y|<0.4) / 대각(그 외).

생성(docs/image/):
  grasp-reach3d.png      도달 TCP 3D 산점(파지방향별 색) — 작업공간 외형
  grasp-reach-top.png    높이(Y) 슬라이스별 X-Z 평면 도달영역(위에서 본 그림)

사용: python calibration/grasp_analysis.py <csv> [--vert|--horz|--any]
  --vert/--horz 로 특정 파지방향만, 기본 전체.
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

try:                                   # 한글 라벨
    matplotlib.rcParams["font.family"] = "Malgun Gothic"
    matplotlib.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

OUT_DIR = r"C:\robotic_arm\docs\image"


def load(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    g = {k: np.array([float(r[k]) for r in rows]) for k in
         ("tcp_x", "tcp_y", "tcp_z", "app_y", "collision")}
    return g, len(rows)


def classify(app_y):
    """수직(0) / 수평(1) / 대각(2)."""
    cat = np.full(app_y.shape, 2, dtype=int)
    cat[app_y < -0.6] = 0
    cat[np.abs(app_y) < 0.4] = 1
    return cat


def fig_reach3d(x, y, z, cat, fname):
    """도달 TCP 3D 산점 — 파지방향별 색."""
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    names = ["수직(top-down)", "수평(side)", "대각"]
    cols = ["#2e7dd1", "#27a35a", "#9aa0a6"]
    for c in (2, 1, 0):                # 대각 먼저(뒤), 수직 마지막(앞)
        m = cat == c
        if m.any():
            ax.scatter(x[m], z[m], y[m], s=2, c=cols[c], alpha=0.25, label=f"{names[c]} ({m.sum()})")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Z (mm)"); ax.set_zlabel("Y=높이 (mm)")
    ax.set_title("그리퍼 도달영역 (충돌 없는 파지 TCP) — 파지방향별")
    ax.legend(loc="upper left", fontsize=9, markerscale=4)
    try:
        ax.set_box_aspect((np.ptp(x), np.ptp(z), np.ptp(y)))
    except Exception:
        pass
    plt.tight_layout(); _save(fig, fname)


def fig_reach_top(x, y, z, fname):
    """높이(Y) 슬라이스별 X-Z 평면 도달영역(위에서 본 그림)."""
    lo, hi = np.percentile(y, 5), np.percentile(y, 95)
    levels = np.linspace(lo, hi, 6)
    fig, axs = plt.subplots(2, 3, figsize=(13, 8))
    band = (hi - lo) / 10 + 5
    for ax, yc in zip(axs.ravel(), levels):
        m = np.abs(y - yc) < band
        ax.scatter(x[m], z[m], s=3, c="#2e7dd1", alpha=0.35)
        ax.set_title(f"높이 Y~{yc:.0f}mm  ({m.sum()}점)", fontsize=10)
        ax.set_xlabel("X (mm)"); ax.set_ylabel("Z (mm)")
        ax.set_aspect("equal", "box"); ax.grid(alpha=0.2)
        ax.set_xlim(x.min(), x.max()); ax.set_ylim(z.min(), z.max())
    fig.suptitle("높이별 도달영역(위에서 본 X-Z 평면) — 빈 곳 = 미도달", fontsize=13)
    plt.tight_layout(); _save(fig, fname)


def _save(fig, fname):
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, fname); fig.savefig(p, dpi=120); plt.close(fig)
    print(f"  저장: {p}")


def main():
    if len(sys.argv) < 2:
        print("사용: python calibration/grasp_analysis.py <grasp_dataset.csv> [--vert|--horz|--any]")
        return
    path = sys.argv[1]
    want = "any"
    for a in sys.argv[2:]:
        if a in ("--vert", "--horz", "--any"):
            want = a[2:]
    g, n = load(path)
    free = g["collision"] == 0
    x, y, z, ay = g["tcp_x"][free], g["tcp_y"][free], g["tcp_z"][free], g["app_y"][free]
    cat = classify(ay)
    print(f"총 {n}자세 · 충돌없음 {free.sum()} ({100*free.mean():.1f}%)")
    print(f"  수직 {int((cat==0).sum())} · 수평 {int((cat==1).sum())} · 대각 {int((cat==2).sum())}")
    print(f"  작업공간 X[{x.min():.0f},{x.max():.0f}] Y[{y.min():.0f},{y.max():.0f}] Z[{z.min():.0f},{z.max():.0f}] mm")

    if want != "any":
        keep = (cat == (0 if want == "vert" else 1))
        x, y, z, cat = x[keep], y[keep], z[keep], cat[keep]
        print(f"  필터({want}): {keep.sum()}점만 표시")

    fig_reach3d(x, y, z, cat, "grasp-reach3d.png")
    fig_reach_top(x, y, z, "grasp-reach-top.png")
    print("완료. docs/image/grasp-reach3d.png · grasp-reach-top.png")


if __name__ == "__main__":
    main()
