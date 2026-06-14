"""
노트북 → AI 서버(EdgeXpert) gRPC 클라이언트.

warm 상주 서버(server.py, 50051)에 명령(텍스트/음성+이미지)을 보내고 의도·DSL을 받는다.
3페이지(자연어 제어)가 이 모듈을 통해 AI 서버와 통신한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))   # robot_arm_pb2 절대 import 가능하게
import grpc
import robot_arm_pb2 as pb
import robot_arm_pb2_grpc as pbg

AI_SERVER = os.environ.get("AI_SERVER", "100.64.39.90:50051")
_OPTS = [("grpc.max_send_message_length", 32 * 1024 * 1024),
         ("grpc.max_receive_message_length", 32 * 1024 * 1024)]


def _stub():
    return pbg.RobotArmAIStub(grpc.insecure_channel(AI_SERVER, options=_OPTS))


def health(timeout=5):
    try:
        h = _stub().Health(pb.HealthRequest(), timeout=timeout)
        return {"ready": bool(h.models_ready), "info": h.info, "server": AI_SERVER}
    except Exception as e:
        return {"ready": False, "error": str(e), "server": AI_SERVER}


def plan(text="", audio=b"", img_left=b"", img_right=b"", detections_json="", timeout=180):
    """명령 → AI 서버 → {intent, transcript, answer, dsl_json, valid, errors, elapsed_s}."""
    req = pb.PlanRequest(text=text, audio=audio, image_left=img_left,
                         image_right=img_right, detections_json=detections_json)
    r = _stub().Plan(req, timeout=timeout)
    return {"intent": r.intent, "transcript": r.transcript, "answer": r.answer,
            "dsl_json": r.dsl_json, "valid": r.valid, "errors": r.errors,
            "elapsed_s": round(r.elapsed_s, 1)}
