# laptop/ — 제어 허브 (Control Hub)

> **3계층 중 Layer 2 — "어떻게 할지"를 번역하는 노트북.**
> 위(AI 서버)의 의미 명령을 받아 **비전·좌표·운동학**을 계산하고, 아래(Arduino)가 실행할 **모터 명령**으로 바꾼다.
> 동시에 로봇 **STL 부품으로 3D 디지털 트윈**을 만들어 시뮬레이션하고 실물과 연동한다.

전체 구조에서 이 폴더의 위치 → [공통 docs/architecture.md](../docs/architecture.md)

---

## 이 폴더가 하는 일

| 기능 | 상태 | 핵심 |
|------|:----:|------|
| 스테레오 **객체 탐지** | ✅ | YOLO-World(GPU, 오픈 보캐뷸러리) |
| **3D 좌표 복원** | ✅ | ChArUco 스테레오 캘리브레이션 + 삼각측량 (보드 30mm를 0.32mm 오차로 복원) |
| **3D 시뮬레이터 + 실물 연동** | ✅ | STL 면대면 조립 → 6관절 리깅 → 슬라이더가 3D+실물 서보 동시 구동 |
| 카메라→로봇 변환, IK, 안전, AI 연동 | ⬜ | 이후 단계 |

브라우저 UI는 Django 웹앱(4페이지). 자세한 동작은 [docs/web_app.md](docs/web_app.md).

---

## 폴더 구조

| 경로 | 역할 |
|------|------|
| `armvision/` | Django 앱 — 카메라·탐지·캘리브레이션·3D 시뮬·시리얼 브리지 + 템플릿(페이지) |
| `calibration/` | 캘리브레이션·검증 스크립트 + 인쇄용 타깃(ChArUco/ArUco) 생성기 |
| `cad/` | 로봇 STL 부품 18개 + 조립 결과 `assembly.json` |
| `config/` | Django 프로젝트 설정 |
| `docs/` | **기능 명세 (이 폴더의 상세 문서)** ↓ |
| `manage.py`, `requirements.txt`, `weights/` | 실행 진입점 · 의존성 · 모델 가중치(gitignore) |

### armvision/ 주요 모듈
`camera.py`(카메라 스레드·좌/우 선택) · `detector.py`(YOLO-World) · `charuco.py`(ChArUco) ·
`stereo3d.py`(삼각측량) · `arduino_bridge.py`(시리얼) · `views.py`/`urls.py`/`templates/`(페이지·API)

---

## 빠른 시작

```bash
pip install -r requirements.txt        # django, ultralytics, opencv-contrib, pyserial, pygrabber, torch …
python manage.py runserver             # http://127.0.0.1:8000/  (실물 연동 시 --noreload 권장)
```
> GPU(torch+CUDA)는 환경에 맞는 휠로 설치. 모델 가중치 `yolov8m-worldv2.pt`는 최초 실행 시 자동 다운로드.

---

## 더 자세히 → [docs/](docs/README.md)

| 문서 | 내용 |
|------|------|
| [docs/README.md](docs/README.md) | **기능 명세 허브** (계층 책임·코드 구조) |
| [web_app.md](docs/web_app.md) | 4페이지 웹 UI + 엔드포인트 |
| [arm3d_simulator.md](docs/arm3d_simulator.md) | **STL 3D 시뮬레이터 + 실물 연동** (모델링·조립·제어) |
| [coordinate_3d_pipeline.md](docs/coordinate_3d_pipeline.md) | ChArUco 캘리브레이션 + 삼각측량 3D |
| [object_detection_model.md](docs/object_detection_model.md) | YOLO-World 선정 근거 |
| [aruco_markers.md](docs/aruco_markers.md) | 로봇 마커 스킴 |
| [setup_procedure.md](docs/setup_procedure.md) | 초기 셋업 6단계 절차 |
