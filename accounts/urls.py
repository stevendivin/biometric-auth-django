from django.urls import path
from . import views
from django.views.generic import RedirectView
app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_step1, name='login_step1'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('choose-method/', views.choose_method, name='choose_method'),
    path('face-verify/', views.face_verify, name='face_verify'),
    path('voice-verify/', views.voice_verify, name='voice_verify'),
    path('otp-verify/', views.otp_verify, name='otp_verify'),
    path('', RedirectView.as_view(url='choose-method/', permanent=False), name='home'),
    path('enroll-voice-word/', views.enroll_voice_word, name='enroll_voice_word'),
]