# arduino/ — 펌웨어 (Hardware Executor)

> **3계층 중 Layer 1 — "실제 실행".**
> 노트북이 보낸 명령을 받아 PWM을 생성해 서보를 구동하고, 센서값을 보고한다.
> **판단·계산은 하지 않는다** (의미 추론=AI 서버, 결정적 계산=노트북).

전체 구조에서 이 폴더의 위치 → [공통 docs/1_architecture.md](../docs/1_architecture.md)

---

## 이 폴더가 하는 일

- 노트북 명령 수신 → **PCA9685로 PWM 생성** → 서보(J1~J6 + 그리퍼) 구동
- **VL53L0X ToF**로 거리 측정(그립 정밀 제어용, 입고 후)
- 센서·상태 보고, 비상 동결

PlatformIO 프로젝트(Arduino Mega 2560). 보드/포트/통신·PWM 매핑 등 상세 → **[docs/README.md](docs/README.md)**.

---

## 현재 상태

- 하드웨어 1차 검증 완료. **서보 J1~J6 펄스 캘리브레이션 완료** → [docs/1_servo_calibration.md](docs/1_servo_calibration.md).
- 현재 펌웨어는 사람이 읽는 **ASCII 시리얼 명령**(`u <ch> <us>` 펄스 직접 등)으로 동작 → 노트북 4페이지 연동이 이 명령을 그대로 사용(펌웨어 무수정).
- **목표(예정):** 이진 CommandPacket + CRC-16 프로토콜([../docs/4_serial_protocol.md](../docs/4_serial_protocol.md)).

---

## 더 자세히 → [docs/](docs/README.md)

| 문서 | 내용 |
|------|------|
| [docs/README.md](docs/README.md) | 펌웨어 기능 명세 (하드웨어·PWM 매핑·업로드 절차) |
| [docs/1_servo_calibration.md](docs/1_servo_calibration.md) | 관절별 0°/180° 펄스 실측값 |
