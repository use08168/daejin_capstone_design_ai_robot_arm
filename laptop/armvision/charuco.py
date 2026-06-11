"""
ChArUco 보드 정의 + 검출/오버레이.

파라미터는 인쇄한 PDF(calibration/make_targets.py)와 **반드시 동일**해야 한다.
"""
import cv2

# --- 인쇄 PDF와 동일한 값 ---
DICT = cv2.aruco.DICT_5X5_100
COLS, ROWS = 6, 8            # squaresX, squaresY
SQUARE_M = 0.030            # 30 mm
MARKER_M = 0.023            # 23 mm

dictionary = cv2.aruco.getPredefinedDictionary(DICT)
board = cv2.aruco.CharucoBoard((COLS, ROWS), SQUARE_M, MARKER_M, dictionary)
_detector = cv2.aruco.CharucoDetector(board)

# 최대 코너 수(=내부 코너) — 충분/부족 판단 기준
MAX_CORNERS = (COLS - 1) * (ROWS - 1)   # 5*7 = 35
MIN_GOOD = 12                            # 이 이상이면 캡처 권장


def detect(frame):
    """(charuco_corners, charuco_ids, marker_corners, marker_ids)."""
    return _detector.detectBoard(frame)


def count(frame) -> int:
    cc, _, _, _ = _detector.detectBoard(frame)
    return 0 if cc is None else len(cc)


def annotate(frame):
    """검출 결과를 그린 프레임과 코너 수 반환 → (frame, n)."""
    out = frame.copy()
    cc, ci, mc, mi = _detector.detectBoard(frame)
    if mi is not None and len(mi) > 0:
        cv2.aruco.drawDetectedMarkers(out, mc, mi)
    n = 0
    if cc is not None and len(cc) > 0:
        cv2.aruco.drawDetectedCornersCharuco(out, cc, ci, (0, 255, 0))
        n = len(cc)
    color = (0, 255, 0) if n >= MIN_GOOD else (0, 165, 255)
    cv2.putText(out, f"charuco corners: {n}/{MAX_CORNERS}", (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    return out, n
