from rest_framework import serializers

from .models import LivenessChallenge


class _ConsentMixin:
    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError(
                "Le consentement explicite est requis pour tout enrôlement biométrique (RGPD art. 9)."
            )
        return value


class EnrollFaceSerializer(_ConsentMixin, serializers.Serializer):
    frame = serializers.CharField(help_text="Image JPEG/PNG encodée en base64.")
    consent = serializers.BooleanField()


class EnrollVoiceSerializer(_ConsentMixin, serializers.Serializer):
    audio = serializers.CharField(help_text="Audio WAV/FLAC encodé en base64.")
    consent = serializers.BooleanField()


class FaceChallengeVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    frames = serializers.ListField(
        child=serializers.CharField(),
        min_length=5,
        max_length=30,
        help_text="Séquence de 5 à 30 frames JPEG encodées en base64, capturées en direct.",
    )


class VoiceChallengeVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    audio = serializers.CharField(help_text="Audio WAV/FLAC encodé en base64.")


# --- Enrôlement guidé (onboarding obligatoire des nouveaux comptes) --------

class FaceGestureCaptureSerializer(serializers.Serializer):
    gesture = serializers.ChoiceField(choices=LivenessChallenge.GESTURES)
    frames = serializers.ListField(
        child=serializers.CharField(),
        min_length=5,
        max_length=30,
    )


class GuidedFaceEnrollSerializer(_ConsentMixin, serializers.Serializer):
    captures = FaceGestureCaptureSerializer(many=True)
    consent = serializers.BooleanField()

    def validate_captures(self, value):
        if len(value) < 3:
            raise serializers.ValidationError(
                "Au moins 3 gestes différents sont requis pour un enrôlement fiable."
            )
        return value


class DigitRecordingSerializer(serializers.Serializer):
    digit = serializers.RegexField(r"^\d$", help_text="Un seul chiffre (0-9).")
    audio = serializers.CharField(help_text="Audio WAV encodé en base64.")


class GuidedVoiceEnrollSerializer(_ConsentMixin, serializers.Serializer):
    digit_recordings = DigitRecordingSerializer(many=True)
    consent = serializers.BooleanField()

    def validate_digit_recordings(self, value):
        if len(value) != 5:
            raise serializers.ValidationError("Exactement 5 chiffres doivent être enregistrés.")
        return value
