from django.urls import path

from . import views

app_name = "biometrics"

urlpatterns = [
    path("enroll/face/", views.EnrollFaceView.as_view(), name="enroll-face"),
    path("enroll/voice/", views.EnrollVoiceView.as_view(), name="enroll-voice"),
    path("enroll/face/guided/", views.GuidedFaceEnrollView.as_view(), name="enroll-face-guided"),
    path("enroll/voice/guided/", views.GuidedVoiceEnrollView.as_view(), name="enroll-voice-guided"),
    path("challenge/face/start/", views.FaceChallengeStartView.as_view(), name="face-challenge-start"),
    path("challenge/face/verify/", views.FaceChallengeVerifyView.as_view(), name="face-challenge-verify"),
    path("challenge/voice/start/", views.VoiceChallengeStartView.as_view(), name="voice-challenge-start"),
    path("challenge/voice/verify/", views.VoiceChallengeVerifyView.as_view(), name="voice-challenge-verify"),
]
