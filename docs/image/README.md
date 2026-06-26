# docs/image — 문서용 사진

문서에서 참조하는 사진/캡처/GIF를 모은 곳. (GIF는 GitHub에서 자동 재생 — 데모용)

## 현재 보유 (문서에 연결됨)

| 파일 | 내용 | 연결된 문서 |
|------|------|-------------|
| `reference-design.png` ✅ | 참조 설계도 (J1~J6, 링크 치수, arm span 350mm) | 루트 README, arm3d_simulator |
| `sim-assembled-1.png` ✅ | 3D 6관절 조립 완료 (시안 고정선) — 대표컷 | 루트 README, arm3d_simulator |
| `sim-assembled-2.png` ✅ | 〃 다른 각도 | arm3d_simulator |
| `sim-face-mate.png` ✅ | 결합: 원통(주황/초록) 선택 | arm3d_simulator |
| `sim-control.png` ✅ | 제어 모드 전체 UI (관절 슬라이더+연동) | arm3d_simulator |
| `webapp-detect.png` ✅ | 1페이지 YOLO 탐지 + 2D/3D 좌표표 | web_app |
| `calib-result.png` ✅ | 2페이지 ChArUco 코너 검출(양 카메라) | coordinate_3d_pipeline |
| `hardware-wiring.png` ✅ | Mega+PCA9685+ToF+서보+전원 배선도 | arduino/docs |
| `real-arm.jpg` ✅ | **실물 6-DOF 로봇팔**(링크별 ArUco 마커) | 루트 README, arm3d_simulator, aruco_markers |
| `charuco-board.png` ✅ | 인쇄용 ChArUco 보드(DICT_5X5_100, 6×8) | coordinate_3d_pipeline, setup_procedure |
| `stereo-rig.png` ✅ | 좌·우 카메라가 본 로봇팔(스테레오 셋업) | setup_procedure |
| `aruco-detect.png` ✅ | ArUco 포즈 검출(위치 mm·회전 deg) | aruco_markers |
| `setup-transform.png` ✅ | 2페이지 4~6단계(베이스·변환 T·마커 측정) | setup_procedure |
| `vlm-chat.png` ✅ | 자연어 제어 VLM 장면 이해 채팅 | ai_integration |
| `jaw-box.png` ✅ | 그리퍼 TCP·jaw 박스·접근축 정의 | grasp_ik_method |
| `joint-sweep.png` ✅ | 관절 스윕 마커 분포(콜드스타트) | coldstart_procedure |
| `grasp-sim.gif` 🎞️ | 4페이지 AI 파지 시뮬(잡기·들기·놓기) | grasp_place_runtime |
| `mlp-training.gif` 🎞️ | 5페이지 MLP 학습 과정(손실·정확도) | grasp_learning_mlp |

## 아직 없음 (있으면 더 좋음)

| 파일명 | 내용 | 쓰일 곳 |
|--------|------|---------|
| `sim-control-real.jpg` | 실물+3D 동시 자세 한 컷(연동 데모) | arm3d_simulator |

---

> 새 사진을 넣은 뒤 알려주면 해당 문서에 `![설명](../../docs/image/파일명)`(루트 README는 `docs/image/파일명`)으로 연결한다.
> 권장: 가로 1200~1600px, JPG(사진)/PNG(UI 캡처), 한 장 ~1MB 이하.
