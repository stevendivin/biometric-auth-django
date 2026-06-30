from django.urls import path

from .views_web import DashboardView, EnrollWizardView, SignUpView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("enroll/", EnrollWizardView.as_view(), name="enroll"),
]
