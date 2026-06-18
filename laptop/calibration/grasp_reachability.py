"""
방향 조건부 도달영역(capability map) — grasp_dataset.csv → 복셀별 수직/수평 파지 가능여부.

핵심: 같은 위치라도 '수직(top-down)으로 잡을 수 있는가'와 '수평(side)으로 잡을 수 있는가'는
서로 다른 도달영역이다. AI가 물체 위치를 받으면 이 맵을 조회해 **가능한 접근방식**을 정한다.

입력 CSV(4페이지 '파지 스윕'): J1..J6, tcp_x/y/z, app_x/y/z, [qx..qw], floor/self, collision
  접근분류: 수직 app_y<-0.6 / 수평 |app_y|<0.4 / 대각(그 외)

생성(docs/image/):
  grasp-capability3d.png   복셀 중심 3D — 수직만(파랑)/수평만(초록)/둘다(주황)
  grasp-capability-top.png 높이별 X-Z — 수직/수평 가능영역 비교
저장: calibration/grasp_capability.json  {voxel_mm, vert:[키], horz:[키]} — 런타임 조회용

사용:
  python calibration/grasp_reachability.py <csv> [voxel_mm=35] [minN=2]
  python calibration/grasp_reachability.py <csv> --query X Y Z      # 그 위치의 가능 접근 출력
"""
import csv
import json
import os
import sys

import numpy as np

OUT_DIR = r"C:\robotic_arm\docs\image"
MAP_PATH = r"C:\robotic_arm\laptop\calibration\grasp_capability.json"


def load_free(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    A = np.array([[float(r["tcp_x"]), float(r["tcp_y"]), float(r["tcp_z"]),
                   float(r["app_y"]), float(r["collision"])] for r in rows])
    free = A[A[:, 4] == 0]
    return free[:, :3], free[:, 3]            # 위치(N,3), app_y(N,)


def classify(app_y):
    cat = np.full(app_y.shape, 2, dtype=int)   # 2=대각
    cat[app_y < -0.6] = 0                       # 수직
    cat[np.abs(app_y) < 0.4] = 1                # 수평
    return cat


def voxelize(P, cat, vox, minN):
    """복셀별 카테고리 카운트 → 가능여부 집합."""
    keys = np.floor(P / vox).astype(int)
    vert, horz = {}, {}
    for k, c in zip(map(tuple, keys), cat):
        if c == 0:
            vert[k] = vert.get(k, 0) + 1
        elif c == 1:
            horz[k] = horz.get(k, 0) + 1
    vset = {k for k, n in vert.items() if n >= minN}
    hset = {k for k, n in horz.items() if n >= minN}
    return vset, hset


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    path = sys.argv[1]
    if "--query" in sys.argv:
        i = sys.argv.index("--query"); x, y, z = map(float, sys.argv[i + 1:i + 4])
        rad = float(sys.argv[i + 4]) if len(sys.argv) > i + 4 else 45.0
        P, ay = load_free(path); cat = classify(ay)
        d = np.linalg.norm(P - np.array([x, y, z]), axis=1); near = d < rad
        nv, nh = int((near & (cat == 0)).sum()), int((near & (cat == 1)).sum())   # 반경내 수직/수평 후보 수
        opts = [f"{n}({c})" for n, c in [("수직", nv), ("수평", nh)] if c >= 2]
        print(f"({x:.0f},{y:.0f},{z:.0f}) r{rad:.0f}mm → 가능 접근: {opts or '없음(미도달)'} · 최근접 {d.min():.0f}mm")
        return

    vox = float(sys.argv[2]) if len(sys.argv) > 2 else 35.0
    minN = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    P, ay = load_free(path)
    cat = classify(ay)
    vset, hset = voxelize(P, cat, vox, minN)
    both = vset & hset
    print(f"복셀 {vox:.0f}mm · 최소{minN}샘플 기준")
    print(f"  수직 가능 복셀 {len(vset)} · 수평 {len(hset)} · 둘다 {len(both)} · 수직만 {len(vset-hset)} · 수평만 {len(hset-vset)}")

    json.dump({"voxel_mm": vox, "minN": minN,
               "vert": [f"{a},{b},{c}" for (a, b, c) in vset],
               "horz": [f"{a},{b},{c}" for (a, b, c) in hset]},
              open(MAP_PATH, "w", encoding="utf-8"))
    print(f"  저장: {MAP_PATH}")
    _plots(vset, hset, both, vox)


def _plots(vset, hset, both, vox):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    try:
        matplotlib.rcParams["font.family"] = "Malgun Gothic"; matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass

    def ctr(s):
        a = np.array(list(s), dtype=float)
        return (a + 0.5) * vox if len(a) else np.empty((0, 3))
    vonly, honly, bo = ctr(vset - hset), ctr(hset - vset), ctr(both)
    fig = plt.figure(figsize=(9, 7)); ax = fig.add_subplot(111, projection="3d")
    for pts, c, lb in [(vonly, "#2e7dd1", f"수직만 ({len(vset-hset)})"),
                       (honly, "#27a35a", f"수평만 ({len(hset-vset)})"),
                       (bo, "#e8902a", f"둘다 ({len(both)})")]:
        if len(pts):
            ax.scatter(pts[:, 0], pts[:, 2], pts[:, 1], s=14, c=c, alpha=0.5, label=lb)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Z (mm)"); ax.set_zlabel("Y=높이 (mm)")
    ax.set_title("방향별 파지 가능영역 (복셀) — 빈 곳=미도달"); ax.legend(loc="upper left", fontsize=9)
    os.makedirs(OUT_DIR, exist_ok=True)
    p1 = os.path.join(OUT_DIR, "grasp-capability3d.png"); fig.savefig(p1, dpi=120); plt.close(fig)

    allk = vset | hset
    if allk:
        ys = sorted({k[1] for k in allk})
        levels = [ys[int(t)] for t in np.linspace(0, len(ys) - 1, min(6, len(ys)))]
        fig, axs = plt.subplots(2, 3, figsize=(13, 8))
        for ax, yl in zip(axs.ravel(), levels):
            for s, c, mk in [(vset - hset, "#2e7dd1", "o"), (hset - vset, "#27a35a", "s"), (both, "#e8902a", "^")]:
                pts = ctr({k for k in s if k[1] == yl})
                if len(pts):
                    ax.scatter(pts[:, 0], pts[:, 2], s=24, c=c, marker=mk, alpha=0.6)
            ax.set_title(f"높이 Y~{(yl+0.5)*vox:.0f}mm", fontsize=10)
            ax.set_xlabel("X"); ax.set_ylabel("Z"); ax.set_aspect("equal", "box"); ax.grid(alpha=0.2)
        fig.suptitle("높이별 가능영역 — 파랑=수직만 초록=수평만 주황=둘다", fontsize=12)
        plt.tight_layout(); p2 = os.path.join(OUT_DIR, "grasp-capability-top.png"); fig.savefig(p2, dpi=120); plt.close(fig)
        print(f"  저장: {p1} · {p2}")


if __name__ == "__main__":
    main()
