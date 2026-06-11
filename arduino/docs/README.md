# Arduino Mega 2560 (펌웨어) — 기능 명세

> **역할: "실제 실행".** 노트북의 명령을 받아 PWM을 생성하고, 센서값을 보고한다.
> 판단·계산은 하지 않는다 (의미 추론=AI 서버, 결정적 계산=노트북).
> 통신 명세: [Serial 프로토콜](../../docs/serial_protocol.md)

---

## 1. 하드웨어 / 환경

| 항목 | 값 |
|------|-----|
| 보드 | Arduino Mega 2560 |
| 프레임워크 | PlatformIO + Arduino |
| 언어 | C++ |
| PWM 드라이버 | PCA9685 (16ch, I2C, 12bit, addr 0x40) |
| ToF 센서 | VL53L0X (I2C, addr 0x29) |
| Baudrate | 115200 |

### 액추에이터

| 관절 | 서보 | 토크(kg·cm) |
|------|------|------------|
| J1 base / J2 shoulder | DS3235 Pro | 35 |
| J3 elbow / J4 pitch | DS3218 Pro | 20 |
| J5 roll / J6 gripper_rot / gripper | MG90S | 2.2 |

**전원 주의:** 서보 전원은 SMPS(Meanwell LRS-150-5, 5V 150W)에서 직접 공급한다.
**PCA9685 PCB 트레이스로 서보 전류를 통과시키지 않는다** (트레이스 한계 3~5A vs 잠재 부하 16.5A).

---

## 2. 기능 책임

1. **명령 수신** — 노트북 Command Packet 수신, CRC 검증.
2. **PWM 생성** — 관절 각도 → PCA9685 12bit 값 → 서보 구동.
3. **그리퍼 제어** — open/close.
4. **ToF 측정** — VL53L0X로 거리(mm) 측정 (High Accuracy mode).
5. **센서 보고** — Sensor Packet으로 ToF·현재 각도·그리퍼·비상버튼 상태를 10Hz 송신.
6. **비상 동결** — emergency 명령 수신 시 현재 PWM 동결 (0으로 만들지 않음).

---

## 3. 메인 루프 개요

```
loop():
  1. Serial에 패킷 도착 시 → CRC 검증 → command_type 분기
       0x01 joint    → setJointAngles()
       0x02 gripper  → setGripper()
       0x03 emergency→ freeze()
     → sendAck()
  2. 10Hz마다 SensorPacket 송신 (ToF + 현재 각도 + 비상버튼)
```

> **현황(2026-06):** 위 이진 CommandPacket 구조는 **최종 목표**다. 현재 캘리브레이션·검증에 쓰는
> 테스트 펌웨어(`src/main.cpp`)는 사람이 읽기 쉬운 **ASCII 시리얼 명령**(`u <ch> <us>` 펄스 직접,
> `a <ch> <deg>`, `s`/`w` 스윕 등)으로 동작하며, 노트북에서 펄스를 보내 서보를 구동한다. 추후 이진
> 패킷 프로토콜로 교체 예정. (각도→펄스 변환은 노트북이 담당 → [servo_calibration.md](servo_calibration.md))

---

## 4. PWM 매핑

```
PWM_μs    = 1500 + (θ_deg / 90) * 500
PCA_value = int(PWM_μs * 4096 / 20000)
```
> **주의:** 위 균일 공식은 원래 설계값이다. 실제 매핑은 관절별 실측 0°/180° 펄스폭([servo_calibration.md](servo_calibration.md))을 사용하며 가동범위는 **0~180°**다. 서보가 **끝 스톱 없는 마그네틱(절대위치) 엔코더형**이라 소프트웨어 관절 한계가 필수다.

규약 세부는 [conventions.md](../../docs/conventions.md) 참조.

---

## 5. 예정 코드 구조 (구현 단계)

```
arduino/
├── platformio.ini
├── include/
│   ├── packet_protocol.h    # 노트북 packet_codec.py 와 동기
│   └── pin_config.h
├── src/
│   ├── main.cpp
│   ├── servo_control.cpp    # PCA9685 + 서보
│   ├── tof_sensor.cpp       # VL53L0X
│   ├── packet_handler.cpp   # Serial 패킷
│   └── crc16.cpp
└── lib/
```

라이브러리: `Adafruit PWM Servo Driver`, `pololu/VL53L0X`.

---

## 6. 업로드 절차 (중요)

```
1. 모든 쉴드 제거 (D0/D1 핀 간섭 방지)
2. pio run --target upload
3. 쉴드 재장착
4. pio device monitor 로 확인
```

---

## 7. 단독 검증 항목

- [ ] PCA9685 PWM 출력 + 서보 단순 구동 확인
- [ ] (ToF 센서 입고 후) VL53L0X I2C 측정 확인
- [ ] (전선 입고 후) 노트북 ↔ Arduino Serial 패킷 송수신 + CRC 검증
- [ ] 비상 동결 동작 확인
