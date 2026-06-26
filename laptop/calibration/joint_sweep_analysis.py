"""6단계 관절 보정 스윕 데이터 시각화 — joint_sweep.json.

(a) 팔 마커(id0~7) 3D envelope: 스윕 동안 각 링크 마커가 그린 자취(로봇 기준).
(b) 말단(id7) 점을 명령 J2로 색칠: 어깨각에 따른 말단 분포(중력 sag 진단 토대).
실행: python calibration/joint_sweep_analysis.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

plt.rcParams["axes.unicode_minus"] = False
from matplotlib import font_manager
_avail = {f.name for f in font_manager.fontManager.ttflist}
for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if _f in _avail:
        plt.rcParams["font.family"] = _f
        break

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "joint_sweep.json")
OUT = os.path.join(HERE, "..", "docs", "image", "joint_sweep.png")


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    poses = d.get("poses", [])
    if not poses:
        print("데이터 없음:", SRC)
        return
    markers = {}                     # id -> [(x,y,z), ...]
    ee, ej2 = [], []                 # 말단(id7) 점 + 그때 J2
    for p in poses:
        for k, v in p.get("markers", {}).items():
            markers.setdefault(int(k), []).append(v)
        m7 = p.get("markers", {}).get("7")
        if m7:
            ee.append(m7); ej2.append(p["cmd"]["J2"])

    fig = plt.figure(figsize=(13, 5.6))
    cmap = plt.get_cmap("tab10")

    # (a) 마커 envelope
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    for mid, pts in sorted(markers.items()):
        a = np.array(pts)
        ax.scatter(a[:, 0], a[:, 1], a[:, 2], s=14, color=cmap(mid % 10), label=f"id{mid}", depthshade=True)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")
    ax.set_title(f"Arm marker envelope (robot frame, {len(poses)} poses)")
    ax.legend(fontsize=8, ncol=2, loc="upper left")

    # (b) 말단(id7) vs J2
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    e = np.array(ee)
    sc = ax2.scatter(e[:, 0], e[:, 1], e[:, 2], c=ej2, cmap="viridis", s=30)
    ax2.set_xlabel("X (mm)"); ax2.set_ylabel("Y (mm)"); ax2.set_zlabel("Z (mm)")
    ax2.set_title(f"End-effector id7 (color = commanded J2, {len(ee)} pts)")
    fig.colorbar(sc, ax=ax2, label="J2 (deg)", shrink=0.6, pad=0.1)

    plt.tight_layout()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    plt.savefig(OUT, dpi=110)
    print("saved:", os.path.normpath(OUT))
    print("마커별 점수:", {k: len(v) for k, v in sorted(markers.items())})


if __name__ == "__main__":
    main()
