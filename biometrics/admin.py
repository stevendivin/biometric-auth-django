from django.contrib import admin

from .models import AuthAttempt, BiometricProfile, LivenessChallenge


@admin.register(BiometricProfile)
class BiometricProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "face_enrolled_at", "voice_enrolled_at", "consent_given_at")
    # Les embeddings ne sont jamais éditables depuis l'admin : seule la
    # pipeline d'enrôlement officielle (avec anti-spoofing) doit les écrire.
    readonly_fields = ("id", "face_embedding", "voice_embedding", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(LivenessChallenge)
class LivenessChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "modality", "challenge_value", "consumed", "expires_at")
    list_filter = ("modality", "consumed")
    readonly_fields = ("id", "created_at")


@admin.register(AuthAttempt)
class AuthAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "modality", "result", "similarity_score", "created_at")
    list_filter = ("modality", "result")
    readonly_fields = [f.name for f in AuthAttempt._meta.fields]

    def has_add_permission(self, request):
        return False  # journal en lecture seule, jamais créé manuellement
