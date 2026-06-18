from django.urls import path

from . import views

app_name = "armvision"

urlpatterns = [
    # 페이지
    path("", views.index, name="index"),
    path("setup/", views.setup, name="setup"),
    path("control/", views.control, name="control"),
    path("arm3d/", views.arm3d, name="arm3d"),
    path("cad/list/", views.cad_list, name="cad_list"),
    path("cad/<str:name>", views.cad_file, name="cad_file"),
    path("arm3d/load/", views.arm3d_load, name="arm3d_load"),
    path("arm3d/save/", views.arm3d_save, name="arm3d_save"),
    # 실물 로봇팔 연동
    path("arm/status/", views.arm_status, name="arm_status"),
    path("arm/connect/", views.arm_connect, name="arm_connect"),
    path("arm/disconnect/", views.arm_disconnect, name="arm_disconnect"),
    path("arm/move/", views.arm_move, name="arm_move"),
    # 카메라 선택
    path("cameras/", views.cameras_list, name="cameras_list"),
    path("cameras/config/", views.cameras_config, name="cameras_config"),
    # 스트림
    path("video_feed/", views.video_feed, name="video_feed"),
    # 탐지 / 3D
    path("detections/", views.detections_json, name="detections"),
    path("positions3d/", views.positions3d_json, name="positions3d"),
    # 위저드 백엔드
    path("setup/state/", views.setup_state, name="setup_state"),
    path("setup/capture/", views.capture_pair, name="capture_pair"),
    path("setup/charuco_status/", views.calibrate_status, name="calibrate_status"),
    path("setup/run_calibration/", views.run_calibration, name="run_calibration"),
    path("setup/run_validation/", views.run_validation, name="run_validation"),
    path("setup/reset/", views.reset_calibration, name="reset_calibration"),
    path("setup/marker_status/", views.marker_status, name="marker_status"),
    path("setup/compute_transform/", views.compute_transform, name="compute_transform"),
    path("setup/measure_markers/", views.measure_markers, name="measure_markers"),
    path("setup/coldstart_save/", views.coldstart_save, name="coldstart_save"),
    # AI 서버(EdgeXpert) 연동 — 3페이지
    path("ai/health/", views.ai_health, name="ai_health"),
    path("ai/plan/", views.ai_plan, name="ai_plan"),
    path("arm/exec_joint/", views.arm_exec_joint, name="arm_exec_joint"),
    path("arm/gripper/", views.arm_gripper, name="arm_gripper"),
    path("arm/joints/", views.arm_joints, name="arm_joints"),
    path("arm/set_angle/", views.arm_set_angle, name="arm_set_angle"),
    path("arm/home/", views.arm_home, name="arm_home"),
    # Teach-and-repeat (관절각 기록·재생 집기) — 5페이지
    path("teach/", views.teach, name="teach"),
    path("arm/teach/list/", views.teach_list, name="teach_list"),
    path("arm/teach/record/", views.teach_record, name="teach_record"),
    path("arm/teach/delete/", views.teach_delete, name="teach_delete"),
    path("arm/teach/clear/", views.teach_clear, name="teach_clear"),
    path("arm/teach/reorder/", views.teach_reorder, name="teach_reorder"),
    path("arm/teach/goto/", views.teach_goto, name="teach_goto"),
    path("arm/teach/play/", views.teach_play, name="teach_play"),
]
