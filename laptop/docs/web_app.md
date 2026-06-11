# 노트북 웹앱 (Django) — 기능 명세

> 노트북 제어 허브의 **웹 UI**. 비전·캘리브레이션·로봇 제어를 브라우저에서 다룬다.
> 프로젝트 `config`, 앱 `armvision`. `python manage.py runserver` → http://127.0.0.1:8000/
> 상단 네비게이션으로 4개 페이지 이동.

---

## 페이지 구성 (4개)

### 1 · 카메라 · 탐지  `/`
- 외장 스테레오 카메라 2대(index 2=좌, 1=우) **MJPEG 실시간** 표시, 화면 중앙 **십자선**.
- **객체 탐지 토글** — YOLO-World(GPU). 박스 + 중심점 + **객체 id(`class_n`, 좌→우)**.
- **2D 좌표표**(카메라별, 1초 갱신): 객체 id · 신뢰도 · 중심(u,v).
- **3D 좌표표**: 캘리브레이션 완료 시 **자동 활성** — 좌·우 매칭·삼각측량한 (X,Y,Z) mm.

### 2 · 캘리브레이션 위저드  `/setup/`
6단계 인터랙티브. **카메라 먼저 고정·보정 → 로봇 설치**( ①②③ → 로봇 → ④⑤⑥ ).
1. **ChArUco 촬영** — 양 카메라 코너 오버레이 + 캡처(좌·우 동시) + 실시간 코너 수. ✅ 동작
2. **카메라 캘리브레이션** — 내부 K·왜곡 + 스테레오 R·T 산출, 결과 표시. ✅ 동작
3. **3D 검증** — 보드 30mm 복원 오차/스케일. ✅ 동작
4. **로봇 배치 & 베이스 마커** — 골격(마커 부착 후 구현)
5. **카메라→로봇 변환 T** — 골격
6. **관절 위치 & 작업공간** — 골격
- 절차 상세: [setup_procedure.md](setup_procedure.md), 파이프라인: [coordinate_3d_pipeline.md](coordinate_3d_pipeline.md)

### 3 · 자연어 제어  `/control/`
- 한국어 명령으로 로봇팔 구동하는 화면. **현재 골격(채팅 UI)만.**
- AI 서버(Whisper·Gemma) 완료 후 **노트북·아두이노·AI 서버 통합 단계**에서 gRPC 클라이언트 + DSL 실행기와 연결.

### 4 · 3D 제어  `/arm3d/`
- **Three.js** 3D 로봇팔(DH 치수 기반 단순 도형, C-브래킷 코봇 근사). 마우스 **360° 회전·줌**.
- **관절(검은 서보 드럼) 클릭 → 우측 패널** → 슬라이더로 각도 조절 → 3D 관절 회전(90°=중립).
- **현재 3D-only.** 실물 연동(ArduinoBridge)·STL 메시 교체는 예정.

---

## 주요 엔드포인트

| 경로 | 용도 |
|------|------|
| `/video_feed/?cam=&detect=&charuco=` | MJPEG 스트림 (탐지/ChArUco 오버레이) |
| `/detections/?cam=` | 카메라별 2D 탐지 JSON |
| `/positions3d/` | 좌·우 매칭·삼각측량 3D JSON |
| `/setup/capture/` · `/setup/run_calibration/` · `/setup/run_validation/` · `/setup/state/` · `/setup/charuco_status/` | 위저드 백엔드 |

---

## 모듈

| 파일 | 역할 |
|------|------|
| `armvision/camera.py` | 카메라 공유 스레드 + MJPEG + 십자선 |
| `armvision/detector.py` | YOLO-World 탐지 + 객체 id |
| `armvision/charuco.py` | ChArUco 검출/오버레이 |
| `armvision/stereo3d.py` | 좌·우 매칭 + 삼각측량 3D (지연 로딩) |
| `armvision/views.py`, `templates/` | 페이지·엔드포인트 |
| `calibration/calibrate_stereo.py`, `validate_triangulation.py` | 캘리브레이션·검증 |
| `calibration/make_targets.py`, `make_arm_markers.py` | 인쇄용 ChArUco/ArUco PDF |

---

## 예정 (구현 대기)

- **ArduinoBridge** (`communication/`): 시리얼 연결 유지 + **각도→펄스 변환**(관절별 실측, [../../arduino/docs/servo_calibration.md](../../arduino/docs/servo_calibration.md)) + 명령 전송. → 4페이지 슬라이더가 **실물도** 구동.
- **3D 메시 교체**: 로봇 STL/STEP 입수 시 `STLLoader`로 사실적 모델.
- **3페이지 통합**: gRPC 클라이언트 + DSL 검증/실행기.
