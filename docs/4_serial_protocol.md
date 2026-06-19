# USB Serial 프로토콜 명세 — 노트북 ↔ Arduino

> **공통 합의 문서.** 노트북(Python `struct`)과 Arduino(C++ `struct`)가 동일한 바이트 레이아웃을 공유한다.
> 양쪽 구조체 정의가 어긋나면 통신 전체가 깨지므로, 변경 시 반드시 이 문서를 먼저 갱신한다.

---

## 1. 개요

| 항목 | 값 |
|------|-----|
| 물리 계층 | USB Serial (CDC) |
| Baudrate | 115200 |
| 패킷 크기 | 35 bytes (양방향 동일) |
| 무결성 | CRC-16-CCITT (poly 0x1021, init 0xFFFF) |
| 엔디안 | little-endian |
| 시작 마커 | `0xAA` |
| 송신 주기 | 노트북→Arduino: 명령 시 / Arduino→노트북: 10Hz (ToF) |

---

## 2. 패킷 구조

### 2.1 노트북 → Arduino (Command Packet, 35 bytes)

```c
struct CommandPacket {
    uint8_t  header;           // 0xAA
    uint8_t  command_type;     // 0x01=joint, 0x02=gripper, 0x03=emergency
    uint32_t timestamp_ms;
    float    joint_angles[6];  // 6 × 4 bytes
    uint8_t  gripper_state;    // 0=open, 1=close
    uint16_t crc16;
};
```

### 2.2 Arduino → 노트북 (Sensor Packet, 35 bytes)

```c
struct SensorPacket {
    uint8_t  header;           // 0xAA
    uint8_t  packet_type;      // 0x01=sensor, 0x02=ack, 0x03=error
    uint32_t timestamp_ms;
    uint16_t tof_distance_mm;
    float    joint_angles[6];  // 현재 자세 피드백
    uint8_t  gripper_state;
    uint8_t  emergency_button;
    uint16_t crc16;
};
```

> 두 구조체 모두 35 bytes로 맞춘다. Python `struct` 포맷: `'<BBI6fBBH'` (Sensor 기준).
> C++ 측은 `#pragma pack(1)` 또는 수동 직렬화로 패딩을 제거해야 35 bytes가 보장된다.

---

## 3. 명령/패킷 타입 코드

| command_type | 의미 |
|--------------|------|
| 0x01 | joint 각도 명령 |
| 0x02 | gripper 개폐 |
| 0x03 | emergency (즉시 동결) |

| packet_type | 의미 |
|-------------|------|
| 0x01 | sensor (정기 보고) |
| 0x02 | ack (명령 수신 확인) |
| 0x03 | error |

| tof 특수값 | 의미 |
|-----------|------|
| 0xFFFE | ToF 측정 실패 |

---

## 4. CRC-16-CCITT

```c
uint16_t computeCRC16(uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
            else crc <<= 1;
        }
    }
    return crc;
}
```

- CRC는 **마지막 2바이트(crc16 필드)를 제외한** 전체 바이트에 대해 계산한다.
- 수신 측은 CRC 불일치 시 패킷을 폐기하고 error 처리한다.

---

## 5. 단위·규약

- 관절 각도: **degree** (`float`)
- 거리: **mm** (`uint16`)
- 타임스탬프: `millis()` 기반 ms (`uint32`) — 노트북 epoch와 별개이며 상대 시간 용도

---

## 6. 안전 관련

- `command_type=0x03` (emergency) 수신 시 Arduino는 현재 PWM을 **동결(freeze)**한다 — 0으로 만들지 않는다(중력 낙하 방지).
- `emergency_button` 필드는 하드웨어 비상 버튼 상태. 노트북은 매 sensor 패킷에서 이를 확인한다.

---

## 7. TODO (구현 단계)

- [ ] `arduino/include/packet_protocol.h` 와 `laptop/src/communication/packet_codec.py` 동기 작성
- [ ] 패킷 손실/재동기화 정책 (header 재탐색) 구현
- [ ] ack 타임아웃 및 재전송 정책 확정
