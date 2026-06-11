"""
YOLO-World 오픈 보캐뷸러리 객체 탐지.

COCO 80클래스에 묶이지 않고, **찾을 물체 이름(텍스트)을 지정**하면 그것을 탐지한다.
→ 캔/커터칼/멀티탭처럼 COCO에 없는 물체도 프롬프트로 잡을 수 있다.

설계상 노트북은 "어디에 물체가 있는지"만 찾고(=여기), "그게 뭔지"의 최종 판단은
AI 서버(Gemma VLM)가 한다. 그래서 분류 정확도보다 **탐지 커버리지**가 중요.

- 모델은 최초 1회만 로드(지연 로딩) + set_classes 로 프롬프트 주입.
- 두 카메라 스레드가 같은 모델을 공유하므로 추론은 lock 으로 직렬화(스레드 안전).
- GPU(CUDA) 자동 사용.
"""
import threading
from collections import defaultdict

import cv2

# 찾을 물체 목록(프롬프트) — 자유롭게 추가/삭제 가능. 자연어 명사구 OK.
PROMPT_CLASSES = [
    "spray bottle", "bottle", "can", "cup",
    "cutter knife", "knife", "scissors", "pen", "marker",
    "power strip", "book", "box", "remote control",
    "hand",
]

_MODEL_NAME = "yolov8m-worldv2.pt"   # 균형(GPU ~19ms). 커버리지 더 필요하면 x 로.
_DEFAULT_CONF = 0.10                  # 오픈보캐뷸러리는 점수가 낮게 나와 임계값을 낮게.

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        from ultralytics import YOLOWorld
        m = YOLOWorld(_MODEL_NAME)
        m.set_classes(PROMPT_CLASSES)
        _model = m
    return _model


def _assign_ids(items):
    """같은 클래스끼리 화면 왼쪽→오른쪽 순으로 1,2,3… → id = 'class_n'."""
    groups = defaultdict(list)
    for it in items:
        groups[it["class"]].append(it)
    for cls, lst in groups.items():
        lst.sort(key=lambda i: i["center"][0])
        for n, it in enumerate(lst, 1):
            it["id"] = f"{cls}_{n}"


def _detect(frame, conf):
    model = get_model()
    with _lock:
        results = model.predict(frame, conf=conf, verbose=False, device=0)
    r = results[0]
    names = r.names
    items = []
    for box in r.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        items.append({
            "class": names[int(box.cls[0])],
            "conf": float(box.conf[0]),
            "bbox": [x1, y1, x2, y2],
            "center": [(x1 + x2) / 2, (y1 + y2) / 2],
        })
    _assign_ids(items)
    return r, items


def annotate(frame, conf: float = _DEFAULT_CONF):
    """박스 + 중심점 + 객체 id(class_n)가 그려진 BGR 프레임 반환."""
    r, items = _detect(frame, conf)
    out = r.plot()  # 박스 + 클래스/신뢰도 라벨
    for it in items:
        cx, cy = int(it["center"][0]), int(it["center"][1])
        cv2.circle(out, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(out, it["id"], (cx + 6, cy - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    return out


def detections(frame, conf: float = _DEFAULT_CONF):
    """탐지 리스트: [{class, id, conf, bbox(xyxy), center}]. id = class_n (좌→우)."""
    _, items = _detect(frame, conf)
    return items
