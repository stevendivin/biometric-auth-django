from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .models import BiometricProfile


class SignUpView(CreateView):
    """Création de compte : nom d'utilisateur + mot de passe + confirmation."""

    form_class = UserCreationForm
    template_name = "biometrics/signup.html"
    success_url = reverse_lazy("enroll")

    def form_valid(self, form):
        response = super().form_valid(form)
        # Connecte automatiquement le nouvel utilisateur pour qu'il puisse
        # enchaîner directement sur l'enrôlement biométrique obligatoire.
        login(self.request, self.object)
        return response


class EnrollWizardView(LoginRequiredMixin, TemplateView):
    """Assistant d'enrôlement biométrique obligatoire (visage puis voix)."""

    template_name = "biometrics/enroll.html"
    login_url = "login"

    def get(self, request, *args, **kwargs):
        try:
            profile = request.user.biometric_profile
        except BiometricProfile.DoesNotExist:
            profile = None

        if profile and profile.face_enrolled_at and profile.voice_enrolled_at:
            return redirect("dashboard")
        return super().get(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "biometrics/dashboard.html"
    login_url = "login"
