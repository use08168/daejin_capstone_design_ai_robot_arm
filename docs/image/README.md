# docs/image — 문서용 사진

문서에서 참조하는 사진/캡처를 여기에 모은다. **아래 파일명 그대로** 저장하면, 각 문서의 "📷 사진 자리"에 연결할 수 있다. (GIF는 제외 — 정지 이미지만)

## A. 핵심 (있으면 가장 좋음)

| 파일명 | 무엇을 담나 | 쓰이는 곳 |
|--------|-------------|-----------|
| `real-arm.jpg` | **실물 6-DOF 로봇팔 전체** 사진 (가능하면 정면) | 루트 README 대표컷, arm3d_simulator |
| `reference-design.jpg` | **참조 설계도/목표 형상** (조립의 기준이 된 그림·도면) | arm3d_simulator, architecture |
| `sim-assembled.jpg` | **3D 6관절 조립 완료** 화면 (고정 연결선 보이면 더 좋음) | arm3d_simulator 대표컷 |
| `charuco-detect.jpg` | **ChArUco 코너 검출** 화면 (좌·우 카메라, 초록 코너) | coordinate_3d_pipeline |

## B. 기능 설명

| 파일명 | 무엇을 담나 | 쓰이는 곳 |
|--------|-------------|-----------|
| `sim-face-mate.jpg` | 결합 모드에서 **원통/평면 선택**(초록·주황 하이라이트) | arm3d_simulator §결합 |
| `sim-control.jpg` | **제어 모드 패널** (관절 슬라이더 + 연동 토글) | arm3d_simulator §제어, web_app |
| `webapp-detect.jpg` | 1페이지 **YOLO 탐지 박스 + 3D 좌표표** | web_app, object_detection_model |
| `calib-result.jpg` | 2페이지 **캘리브레이션 결과**(재투영오차/베이스라인) | setup_procedure, web_app |

## C. 있으면 좋음 (보조)

| 파일명 | 무엇을 담나 | 쓰이는 곳 |
|--------|-------------|-----------|
| `hardware-wiring.jpg` | Arduino Mega + PCA9685 + 전원 **배선** | arduino/docs |
| `stereo-rig.jpg` | **두 카메라 고정 셋업**(작업면을 비스듬히 내려다봄) | setup_procedure |
| `charuco-board.jpg` | **인쇄한 ChArUco 보드** | coordinate_3d_pipeline |
| `sim-control-real.jpg` | **실물 + 3D 동시 자세** 한 컷 (연동 데모 스틸) | arm3d_simulator §제어 |

---

> 사진을 넣은 뒤 알려주시면, 각 문서의 `> 📷 사진 자리:` 줄을 실제 이미지 링크로 연결합니다.
> (예: arm3d_simulator.md 에서는 `![6관절 조립](../../docs/image/sim-assembled.jpg)`)
> 권장: 가로 폭 1200~1600px, JPG(사진)·PNG(UI 캡처), 한 장당 ~1MB 이하.
