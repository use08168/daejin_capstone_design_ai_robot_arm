"""
인쇄용 캘리브레이션 타깃 PDF 생성 (A4, 2페이지).

1쪽: ChArUco 보드 (카메라 내부/스테레오 캘리브레이션용)
2쪽: 단일 ArUco 마커 (로봇 베이스 부착, 카메라-로봇 변환용)

중요: 반드시 **100% 배율("실제 크기")로 인쇄**해야 mm 치수가 맞는다.
인쇄 후 50mm 스케일 선을 자로 재서 배율을 확인할 것.
"""
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# ---- A4 ----
W, H = 210.0, 297.0  # mm

# ---- ChArUco 파라미터 (캘리브레이션 코드와 동일하게 사용할 것) ----
CH_DICT = cv2.aruco.DICT_5X5_100
CH_COLS, CH_ROWS = 6, 8           # squaresX, squaresY
CH_SQUARE_MM = 30.0               # 정사각형 한 변
CH_MARKER_MM = 23.0               # 마커 한 변 (< square)
CH_W_MM = CH_COLS * CH_SQUARE_MM  # 180
CH_H_MM = CH_ROWS * CH_SQUARE_MM  # 240

# ---- 베이스 ArUco 파라미터 ----
BASE_DICT = cv2.aruco.DICT_6X6_250
BASE_ID = 0
BASE_MM = 120.0


def mm_axes(fig, x, y, w, h):
    """mm 사각형(좌하단 기준)에 이미지용 axes 생성."""
    ax = fig.add_axes([x / W, y / H, w / W, h / H])
    ax.axis("off")
    return ax


def overlay(fig):
    """mm 좌표로 선/텍스트를 그릴 전체 투명 axes."""
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.axis("off")
    return ax


def scale_bar(ax, x, y, length=50.0):
    ax.plot([x, x + length], [y, y], color="black", lw=1.5)
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 2, y + 2], color="black", lw=1.5)
    ax.text(x + length / 2, y + 3, f"{length:.0f} mm  (measure to verify 100% print)",
            ha="center", va="bottom", fontsize=7)


def make_pdf(path):
    dictC = cv2.aruco.getPredefinedDictionary(CH_DICT)
    board = cv2.aruco.CharucoBoard((CH_COLS, CH_ROWS),
                                   CH_SQUARE_MM / 1000.0, CH_MARKER_MM / 1000.0, dictC)
    charuco_img = board.generateImage((1800, 2400), marginSize=0, borderBits=1)

    dictM = cv2.aruco.getPredefinedDictionary(BASE_DICT)
    marker_img = cv2.aruco.generateImageMarker(dictM, BASE_ID, 1200)

    with PdfPages(path) as pdf:
        # ---- 1쪽: ChArUco ----
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        bx = (W - CH_W_MM) / 2.0
        by = 8.0
        ax = mm_axes(fig, bx, by, CH_W_MM, CH_H_MM)
        ax.imshow(charuco_img, cmap="gray", aspect="auto", interpolation="nearest")
        ov = overlay(fig)
        ov.text(W / 2, 290, "ChArUco board - camera calibration", ha="center", fontsize=11, weight="bold")
        ov.text(W / 2, 283,
                f"DICT_5X5_100 | squaresX={CH_COLS} squaresY={CH_ROWS} | "
                f"square={CH_SQUARE_MM:.1f}mm marker={CH_MARKER_MM:.1f}mm",
                ha="center", fontsize=8)
        ov.text(W / 2, 277, "PRINT AT 100% (Actual size / no scaling)", ha="center", fontsize=8, color="red")
        scale_bar(ov, bx, 256)
        pdf.savefig(fig); plt.close(fig)

        # ---- 2쪽: 베이스 ArUco ----
        fig = plt.figure(figsize=(W / 25.4, H / 25.4))
        mx = (W - BASE_MM) / 2.0
        my = (H - BASE_MM) / 2.0 - 10
        ax = mm_axes(fig, mx, my, BASE_MM, BASE_MM)
        ax.imshow(marker_img, cmap="gray", aspect="auto", interpolation="nearest")
        ov = overlay(fig)
        ov.text(W / 2, 285, "ArUco marker - robot base", ha="center", fontsize=11, weight="bold")
        ov.text(W / 2, 278,
                f"DICT_6X6_250 | id={BASE_ID} | size={BASE_MM:.0f}mm  (attach to robot base)",
                ha="center", fontsize=8)
        ov.text(W / 2, 272, "PRINT AT 100% (Actual size / no scaling)", ha="center", fontsize=8, color="red")
        scale_bar(ov, mx, my - 12)
        pdf.savefig(fig); plt.close(fig)

    print("saved:", path)


if __name__ == "__main__":
    make_pdf(r"C:\robotic_arm\laptop\calibration\calibration_targets.pdf")
