import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from pgvector.django import VectorField


class BiometricProfile(models.Model):
    """
    Ne stocke QUE des embeddings (vecteurs numériques), jamais l'image du visage
    ni l'enregistrement audio brut. Un embedding n'est pas réversible vers
    l'image/voix d'origine, mais reste une donnée biométrique au sens RGPD
    (article 9) : accès strictement limité, jamais exposée via l'API/admin
    autrement qu'en lecture interne pour le calcul de similarité.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="biometric_profile"
    )

    # ArcFace (DeepFace) -> 512 dimensions
    face_embedding = VectorField(dimensions=512, null=True, blank=True)
    # ECAPA-TDNN (SpeechBrain, spkrec-ecapa-voxceleb) -> 192 dimensions
    voice_embedding = VectorField(dimensions=192, null=True, blank=True)

    face_enrolled_at = models.DateTimeField(null=True, blank=True)
    voice_enrolled_at = models.DateTimeField(null=True, blank=True)

    consent_given_at = models.DateTimeField()
    consent_withdrawn_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BiometricProfile<{self.user_id}>"


class LivenessChallenge(models.Model):
    """
    Challenge anti-deepfake généré côté serveur : aléatoire, à usage unique,
    expirant rapidement. C'est ce mécanisme qui empêche le rejeu d'une vidéo
    ou d'un audio pré-enregistré/deepfake : l'attaquant ne peut pas connaître
    à l'avance le geste ou la séquence de chiffres qui sera demandée.
    """

    class Modality(models.TextChoices):
        FACE = "face", "Face"
        VOICE = "voice", "Voice"

    GESTURES = ["BLINK_TWICE", "TURN_HEAD_LEFT", "TURN_HEAD_RIGHT", "SMILE", "NOD"]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liveness_challenges"
    )
    modality = models.CharField(max_length=10, choices=Modality.choices)
    # "TURN_HEAD_LEFT" pour le visage, ou "482913" (chiffres) pour la voix
    challenge_value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)

    def is_valid(self) -> bool:
        return (not self.consumed) and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.modality}:{self.challenge_value} ({'consommé' if self.consumed else 'actif'})"


class AuthAttempt(models.Model):
    """
    Journal d'audit des tentatives d'authentification biométrique.
    Indispensable pour : détecter les abus/attaques par essais répétés,
    justifier les seuils de décision auprès d'un DPO, et respecter le
    principe de traçabilité du RGPD. Ne contient aucune donnée brute,
    uniquement le résultat et le score de similarité.
    """

    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED_MATCH = "failed_match", "Failed match"
        FAILED_LIVENESS = "failed_liveness", "Failed liveness"
        FAILED_CHALLENGE = "failed_challenge", "Failed challenge"
        ERROR = "error", "Error"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_attempts")
    modality = models.CharField(max_length=10)
    result = models.CharField(max_length=20, choices=Result.choices)
    similarity_score = models.FloatField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} - {self.modality} - {self.result}"
