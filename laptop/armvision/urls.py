from django.urls import path

from . import views

app_name = "armvision"

urlpatterns = [
    # 페이지
    path("", views.index, name="index"),
    path("setup/", views.setup, name="setup"),
    path("control/", views.control, name="control"),
    path("arm3d/", views.arm3d, name="arm3d"),
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
]
