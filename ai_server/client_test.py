"""
warm gRPC 서버 테스트 클라이언트 — 서버가 준비될 때까지 대기 후 점진적 명령 테스트.

테스트 순서(쉬움→어려움):
  1. 직접 관절 (J1 180도)  2. 다른 관절  3. 상황질문(이미지)
  4. 물체 집기(이미지)      5. 없는 물체(역질문)  6. 음성 명령(STT→계획)

실행(EdgeXpert): python client_test.py   (server.py가 50051에서 warm 대기 중이어야)
"""
import time

import grpc
import robot_arm_pb2 as pb
import robot_arm_pb2_grpc as pbg

ch = grpc.insecure_channel("localhost:50051",
                           options=[("grpc.max_send_message_length", 32 * 1024 * 1024)])
stub = pbg.RobotArmAIStub(ch)

# 서버 warm 대기 (모델 로드 ~7분)
print("[client] 서버 준비 대기 …", flush=True)
for i in range(60):
    try:
        h = stub.Health(pb.HealthRequest(), timeout=10)
        if h.models_ready:
            print(f"[client] 준비됨: {h.info}", flush=True); break
    except Exception:
        pass
    time.sleep(15)
else:
    print("[client] 서버 준비 안 됨, 종료"); raise SystemExit

imgL = open("cam_left.png", "rb").read()
imgR = open("cam_right.png", "rb").read()
audio = open("voice1.m4a", "rb").read()


def show(title, req):
    r = stub.Plan(req, timeout=180)
    print("=" * 60)
    print(f"[{title}] ({r.elapsed_s:.1f}s) intent={r.intent}")
    if r.transcript:
        print(f"  STT: {r.transcript}")
    if r.answer:
        print(f"  답변: {r.answer}")
    if r.dsl_json:
        print(f"  DSL(valid={r.valid}): {r.dsl_json}")
        if r.errors:
            print(f"  검증오류: {r.errors}")


show("1.직접관절", pb.PlanRequest(text="J1 모터를 180도로 움직여줘"))
show("2.다른관절", pb.PlanRequest(text="J5 모터를 90도로 돌려줘"))
show("3.상황질문", pb.PlanRequest(text="지금 작업공간에 뭐가 있어?", image_left=imgL, image_right=imgR))
show("4.물체집기", pb.PlanRequest(text="빨간 캔을 집어줘", image_left=imgL, image_right=imgR))
show("5.없는물체", pb.PlanRequest(text="노란색 공을 집어줘", image_left=imgL, image_right=imgR))
show("6.음성명령", pb.PlanRequest(audio=audio, image_left=imgL, image_right=imgR))
print("=" * 60); print("[client] 테스트 완료")
