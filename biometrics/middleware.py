from django.shortcuts import redirect

from .models import BiometricProfile

# Préfixes jamais bloqués : pages de compte, admin, fichiers statiques, API
# (les appels API de l'assistant d'enrôlement doivent pouvoir s'exécuter
# pendant que l'utilisateur est justement en train de s'enrôler).
EXEMPT_PREFIXES = ("/admin", "/api/", "/static/", "/accounts/", "/signup/", "/enroll/")


class RequireBiometricEnrollmentMiddleware:
    """
    Rend l'enrôlement biométrique (visage + voix) obligatoire pour tout
    nouveau compte avant d'accéder au reste de l'application.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(EXEMPT_PREFIXES):
            try:
                profile = request.user.biometric_profile
            except BiometricProfile.DoesNotExist:
                profile = None

            fully_enrolled = bool(profile and profile.face_enrolled_at and profile.voice_enrolled_at)
            if not fully_enrolled:
                return redirect("enroll")

        return self.get_response(request)
