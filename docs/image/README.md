# docs/image — 문서용 사진

문서에서 참조하는 사진/캡처를 모은 곳. (GIF 제외 — 정지 이미지만)

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

## 아직 없음 (있으면 더 좋음)

| 파일명 | 내용 | 쓰일 곳 |
|--------|------|---------|
| `real-arm.jpg` | **실물 6-DOF 로봇팔 전체** 사진 | 루트 README 대표컷, arm3d_simulator |
| `stereo-rig.jpg` | 두 카메라 고정 셋업 | setup_procedure |
| `charuco-board.jpg` | 인쇄한 ChArUco 보드 | coordinate_3d_pipeline |
| `sim-control-real.jpg` | 실물+3D 동시 자세 한 컷(연동 데모) | arm3d_simulator |

---

> 새 사진을 넣은 뒤 알려주면 해당 문서에 `![설명](../../docs/image/파일명)`(루트 README는 `docs/image/파일명`)으로 연결한다.
> 권장: 가로 1200~1600px, JPG(사진)/PNG(UI 캡처), 한 장 ~1MB 이하.
