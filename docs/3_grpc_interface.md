# gRPC 인터페이스 명세 — AI 서버 ↔ 노트북

> **공통 합의 문서.** AI 서버(EdgeXpert)와 노트북은 이 명세를 단일 진실 공급원(single source of truth)으로 삼는다.
> proto 원본은 향후 `shared/proto/robot_arm.proto`에 두고, 양측이 동일 파일에서 코드를 생성한다.

---

## 1. 개요

| 항목 | 값 |
|------|-----|
| 프로토콜 | gRPC + Protobuf (proto3) |
| 기본 포트 | 50051 |
| 직렬화 | Protocol Buffers |
| 연결 형태 | 노트북 = 클라이언트, AI 서버 = 서버 |

---

## 2. 서비스 정의

```protobuf
syntax = "proto3";

service RobotArmAI {
  // 단방향 요청-응답: 음성+비전 → JSON DSL
  rpc PlanGrasp(GraspPlanRequest) returns (GraspPlanResponse);

  // 양방향 스트림: 노트북 상태 보고(50Hz) + AI 서버 알림
  rpc StreamSafetyAlert(stream LaptopStatus) returns (stream SafetyAlert);

  // 연결 확인 (3초 주기)
  rpc Heartbeat(HeartbeatRequest) returns (HeartbeatResponse);
}
```

---

## 3. 메시지 정의

```protobuf
message GraspPlanRequest {
  bytes audio_data = 1;          // WAV
  string audio_format = 2;
  bytes camera1_frame = 3;       // JPEG
  bytes camera2_frame = 4;       // JPEG
  repeated DetectedObject detections = 5;  // 노트북 YOLO-World 결과
  RobotState current_state = 6;
  int64 timestamp_ms = 7;
}

message DetectedObject {
  int32 id = 1;
  string class_name = 2;
  Bbox bbox_cam1 = 3;
  Bbox bbox_cam2 = 4;
  Point3D position_3d_mm = 5;    // 노트북 삼각측량 결과
}

message Bbox   { float x = 1; float y = 2; float w = 3; float h = 4; }
message Point3D { float x_mm = 1; float y_mm = 2; float z_mm = 3; }

message RobotState {
  repeated float joint_angles_deg = 1;  // 6개
  bool gripper_closed = 2;
}

message GraspPlanResponse {
  string dsl_script = 1;         // JSON 인코딩된 DSL (5_dsl_spec.md 참조)
  float confidence = 2;
  int32 inference_time_ms = 3;
  string reasoning = 4;          // Chain-of-Thought
}

message LaptopStatus {
  float tof_distance_mm = 1;
  RobotState state = 2;
  int64 timestamp_ms = 3;
}

message SafetyAlert {
  string reason = 1;
  int64 timestamp_ms = 2;
}
```

---

## 4. 메시지 흐름

| RPC | 방향 | 설명 |
|-----|------|------|
| `PlanGrasp` | 노트북 → AI 서버 → 노트북 | 음성+카메라+탐지 결과 전송 → JSON DSL 수신 |
| `StreamSafetyAlert` | 양방향 스트림 | 노트북이 50Hz로 상태 보고, AI 서버는 필요 시 알림 |
| `Heartbeat` | 노트북 ↔ AI 서버 | 3초 주기. **3초 무응답 시 노트북이 독립적으로 비상 정지** |

---

## 5. 책임 경계 (중요)

- **삼각측량은 노트북이 수행한다.** AI 서버에는 이미 3D 좌표(`position_3d_mm`)가 채워진 `DetectedObject`가 전달된다. AI 서버는 좌표를 다시 계산하지 않는다.
- **AI 서버가 반환하는 DSL은 좌표가 아니라 객체 ID 기반 명령이다.** (`target: "cup_2"`) 실제 좌표 해석·IK는 노트북 책임.
- **DSL 검증은 노트북이 수행한다.** AI 서버 출력은 신뢰하지 않고 화이트리스트/파라미터/시퀀스 검증을 거친다 → [5_dsl_spec.md](5_dsl_spec.md).

---

## 6. 단위·규약

- 모든 길이: **mm**
- 모든 각도: **degree** (proto 필드명에 `_deg` 명시)
- 타임스탬프: **Unix epoch milliseconds** (`int64`)
- 좌표계 정의는 [6_conventions.md](6_conventions.md) 참조.

---

## 7. TODO (구현 단계)

- [ ] `shared/proto/robot_arm.proto` 작성 및 양측 코드 생성 스크립트 정비
- [ ] 타임아웃/재시도 정책 확정 (현재 안: timeout 10s, heartbeat 3s)
- [ ] 대용량 프레임 전송 시 압축/스트리밍 여부 검토
