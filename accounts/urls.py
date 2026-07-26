from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("enroll-voice-word/", views.enroll_voice_word, name="enroll_voice_word"),

    path("login/", views.login_step1, name="login_step1"),
    path("choose-method/", views.choose_method, name="choose_method"),

    path("face-verify/", views.face_verify, name="face_verify"),
    path("voice-verify/", views.voice_verify, name="voice_verify"),

    path("send-otp/", views.send_otp, name="send_otp"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("", views.login_step1, name="home"),
]
