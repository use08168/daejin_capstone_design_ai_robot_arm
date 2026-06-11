"""
로봇팔용 ArUco 마커 PDF 생성 (A4, 2페이지).

1쪽: 베이스 마커 (id 0, 70mm) — 카메라↔로봇 기준 변환 T (단계 ⑤)
2쪽: 추적용 마커 (id 1~12, 40mm) — 각 링크/그리퍼에 부착, 움직임 추적·콜드스타트

모두 DICT_6X6_250 (ChArUco 보드의 DICT_5X5_100 과 다른 사전 → 충돌 없음).
반드시 100% 배율로 인쇄. 곡면엔 작게 붙이거나 평평한 부위(관절 하우징)에.
"""
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

W, H = 210.0, 297.0  # A4 mm
DICTID = cv2.aruco.DICT_6X6_250
DICT = cv2.aruco.getPredefinedDictionary(DICTID)

BASE_ID, BASE_MM = 0, 70.0
TRACK_IDS = list(range(1, 13))   # 1..12
TRACK_MM = 40.0


def marker_img(mid, px=600):
    return cv2.aruco.generateImageMarker(DICT, mid, px)


def mm_axes(fig, x, y, w, h):
    ax = fig.add_axes([x / W, y / H, w / W, h / H]); ax.axis("off")
    return ax


def overlay(fig):
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    return ax


def scale_bar(ax, x, y, length=50.0):
    ax.plot([x, x + length], [y, y], color="black", lw=1.3)
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 2, y + 2], color="black", lw=1.3)
    ax.text(x + length / 2, y + 3, f"{length:.0f} mm (verify 100%)", ha="center", va="bottom", fontsize=7)


def make_pdf(path):
    with PdfPages(path) as pdf:
        # ---- 1쪽: 베이스 ----
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        mx = (W - BASE_MM) / 2
        my = (H - BASE_MM) / 2 - 10
        mm_axes(fig, mx, my, BASE_MM, BASE_MM).imshow(marker_img(BASE_ID), cmap="gray",
                                                      aspect="auto", interpolation="nearest")
        ov = overlay(fig)
        ov.text(W / 2, 285, "ArUco - ROBOT BASE (frame reference)", ha="center", fontsize=12, weight="bold")
        ov.text(W / 2, 278, f"DICT_6X6_250 | id={BASE_ID} | size={BASE_MM:.0f}mm  (attach to STATIONARY base)",
                ha="center", fontsize=8)
        ov.text(W / 2, 272, "PRINT AT 100% (no scaling)", ha="center", fontsize=8, color="red")
        scale_bar(ov, mx, my - 12)
        pdf.savefig(fig); plt.close(fig)

        # ---- 2쪽: 추적용 그리드 ----
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        ov = overlay(fig)
        ov.text(W / 2, 287, "ArUco - ARM TRACKING markers", ha="center", fontsize=12, weight="bold")
        ov.text(W / 2, 280, f"DICT_6X6_250 | id 1-12 | size={TRACK_MM:.0f}mm  (1 per link/gripper; cut out)",
                ha="center", fontsize=8)
        ov.text(W / 2, 274, "PRINT AT 100% (no scaling)", ha="center", fontsize=8, color="red")
        cols, rows = 3, 4
        cw = (W - 30) / cols          # 좌우 15mm 여백
        top = 258
        rh = (top - 20) / rows
        for k, mid in enumerate(TRACK_IDS):
            r, ccol = divmod(k, cols)
            cx = 15 + cw * (ccol + 0.5)
            cy = top - rh * (r + 0.5)
            x = cx - TRACK_MM / 2
            y = cy - TRACK_MM / 2 + 3
            mm_axes(fig, x, y, TRACK_MM, TRACK_MM).imshow(marker_img(mid), cmap="gray",
                                                          aspect="auto", interpolation="nearest")
            ov.text(cx, y - 4, f"id {mid}", ha="center", va="top", fontsize=8)
        scale_bar(ov, 20, 12)
        pdf.savefig(fig); plt.close(fig)

    print("saved:", path)


if __name__ == "__main__":
    make_pdf(r"C:\robotic_arm\laptop\calibration\arm_markers.pdf")
