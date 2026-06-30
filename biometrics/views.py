import uuid
from datetime import timedelta

import numpy as np
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import AuthAttempt, BiometricProfile, LivenessChallenge
from .serializers import (
    EnrollFaceSerializer,
    EnrollVoiceSerializer,
    FaceChallengeVerifySerializer,
    GuidedFaceEnrollSerializer,
    GuidedVoiceEnrollSerializer,
    VoiceChallengeVerifySerializer,
)
from .services.face_liveness import FaceLivenessVerifier, generate_face_challenge
from .services.face_service import FaceEmbeddingError, extract_face_embedding
from .services.matching import FACE_MATCH_THRESHOLD, VOICE_MATCH_THRESHOLD, cosine_similarity
from .services.voice_liveness import generate_voice_challenge, replay_spoof_heuristic, verify_spoken_challenge
from .services.voice_service import VoiceEmbeddingError, extract_voice_embedding
from .utils import decode_base64_audio, decode_base64_frame

CHALLENGE_TTL_SECONDS = 30


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


# ---------------------------------------------------------------------------
# Enrôlement (capture unique, hors flux de connexion)
# ---------------------------------------------------------------------------

class EnrollFaceView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-enroll"

    def post(self, request):
        serializer = EnrollFaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        frame = decode_base64_frame(serializer.validated_data["frame"])
        try:
            embedding = extract_face_embedding(frame)
        except FaceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del frame  # on ne garde jamais l'image brute plus longtemps que nécessaire

        profile, _ = BiometricProfile.objects.get_or_create(
            user=request.user, defaults={"consent_given_at": timezone.now()}
        )
        profile.face_embedding = embedding.tolist()
        profile.face_enrolled_at = timezone.now()
        profile.save(update_fields=["face_embedding", "face_enrolled_at", "updated_at"])

        return Response({"detail": "Visage enrôlé avec succès."}, status=status.HTTP_201_CREATED)


class EnrollVoiceView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-enroll"

    def post(self, request):
        serializer = EnrollVoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        waveform, sample_rate = decode_base64_audio(serializer.validated_data["audio"])
        try:
            embedding = extract_voice_embedding(waveform, sample_rate)
        except VoiceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del waveform

        profile, _ = BiometricProfile.objects.get_or_create(
            user=request.user, defaults={"consent_given_at": timezone.now()}
        )
        profile.voice_embedding = embedding.tolist()
        profile.voice_enrolled_at = timezone.now()
        profile.save(update_fields=["voice_embedding", "voice_enrolled_at", "updated_at"])

        return Response({"detail": "Voix enrôlée avec succès."}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Authentification faciale : challenge anti-deepfake puis vérification
# ---------------------------------------------------------------------------

class FaceChallengeStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-verify"

    def post(self, request):
        gesture = generate_face_challenge()
        challenge = LivenessChallenge.objects.create(
            id=uuid.uuid4(),
            user=request.user,
            modality=LivenessChallenge.Modality.FACE,
            challenge_value=gesture,
            expires_at=timezone.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        )
        return Response(
            {"challenge_id": challenge.id, "gesture": gesture, "ttl_seconds": CHALLENGE_TTL_SECONDS}
        )


class FaceChallengeVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-verify"

    def post(self, request):
        serializer = FaceChallengeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        challenge = LivenessChallenge.objects.filter(
            id=serializer.validated_data["challenge_id"], user=request.user, modality="face"
        ).first()
        if not challenge or not challenge.is_valid():
            return Response({"detail": "Challenge invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.biometric_profile
        except BiometricProfile.DoesNotExist:
            return Response({"detail": "Aucun profil biométrique enrôlé."}, status=status.HTTP_400_BAD_REQUEST)
        if profile.face_embedding is None:
            return Response({"detail": "Visage non enrôlé."}, status=status.HTTP_400_BAD_REQUEST)

        frames = [decode_base64_frame(f) for f in serializer.validated_data["frames"]]

        liveness_result = FaceLivenessVerifier().verify(frames, challenge.challenge_value)

        challenge.consumed = True
        challenge.save(update_fields=["consumed"])

        if not liveness_result["liveness_ok"]:
            AuthAttempt.objects.create(
                user=request.user, modality="face", result=AuthAttempt.Result.FAILED_LIVENESS,
                ip_address=_client_ip(request),
            )
            return Response(
                {"detail": "Échec du test anti-deepfake (liveness).", **liveness_result},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            live_embedding = extract_face_embedding(frames[-1])
        except FaceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del frames

        stored_embedding = np.array(profile.face_embedding, dtype=np.float32)
        score = cosine_similarity(live_embedding, stored_embedding)
        matched = score >= FACE_MATCH_THRESHOLD

        AuthAttempt.objects.create(
            user=request.user,
            modality="face",
            result=AuthAttempt.Result.SUCCESS if matched else AuthAttempt.Result.FAILED_MATCH,
            similarity_score=score,
            ip_address=_client_ip(request),
        )

        if not matched:
            return Response({"detail": "Visage non reconnu.", "score": score}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"detail": "Authentification faciale réussie.", "score": score, **liveness_result})


# ---------------------------------------------------------------------------
# Authentification vocale : challenge anti-deepfake puis vérification
# ---------------------------------------------------------------------------

class VoiceChallengeStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-verify"

    def post(self, request):
        digits = generate_voice_challenge()
        challenge = LivenessChallenge.objects.create(
            id=uuid.uuid4(),
            user=request.user,
            modality=LivenessChallenge.Modality.VOICE,
            challenge_value=digits,
            expires_at=timezone.now() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        )
        return Response(
            {"challenge_id": challenge.id, "say_these_digits": digits, "ttl_seconds": CHALLENGE_TTL_SECONDS}
        )


class VoiceChallengeVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-verify"

    def post(self, request):
        serializer = VoiceChallengeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        challenge = LivenessChallenge.objects.filter(
            id=serializer.validated_data["challenge_id"], user=request.user, modality="voice"
        ).first()
        if not challenge or not challenge.is_valid():
            return Response({"detail": "Challenge invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.biometric_profile
        except BiometricProfile.DoesNotExist:
            return Response({"detail": "Aucun profil biométrique enrôlé."}, status=status.HTTP_400_BAD_REQUEST)
        if profile.voice_embedding is None:
            return Response({"detail": "Voix non enrôlée."}, status=status.HTTP_400_BAD_REQUEST)

        waveform, sample_rate = decode_base64_audio(serializer.validated_data["audio"])

        challenge.consumed = True
        challenge.save(update_fields=["consumed"])

        if not verify_spoken_challenge(waveform, sample_rate, challenge.challenge_value):
            AuthAttempt.objects.create(
                user=request.user, modality="voice", result=AuthAttempt.Result.FAILED_CHALLENGE,
                ip_address=_client_ip(request),
            )
            return Response(
                {"detail": "Les chiffres prononcés ne correspondent pas au challenge demandé."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        spoof_check = replay_spoof_heuristic(waveform, sample_rate)
        if spoof_check["suspicious_synthetic"]:
            AuthAttempt.objects.create(
                user=request.user, modality="voice", result=AuthAttempt.Result.FAILED_LIVENESS,
                ip_address=_client_ip(request),
            )
            return Response(
                {"detail": "Signal vocal suspect (possible voix synthétique ou rejouée).", **spoof_check},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            live_embedding = extract_voice_embedding(waveform, sample_rate)
        except VoiceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del waveform

        stored_embedding = np.array(profile.voice_embedding, dtype=np.float32)
        score = cosine_similarity(live_embedding, stored_embedding)
        matched = score >= VOICE_MATCH_THRESHOLD

        AuthAttempt.objects.create(
            user=request.user,
            modality="voice",
            result=AuthAttempt.Result.SUCCESS if matched else AuthAttempt.Result.FAILED_MATCH,
            similarity_score=score,
            ip_address=_client_ip(request),
        )

        if not matched:
            return Response({"detail": "Voix non reconnue.", "score": score}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"detail": "Authentification vocale réussie.", "score": score, **spoof_check})


# ---------------------------------------------------------------------------
# Enrôlement guidé (onboarding obligatoire des nouveaux comptes) :
# visage = séquence de plusieurs gestes vérifiés un par un, voix = 5 chiffres
# prononcés un par un. Plus exigeant que l'enrôlement simple ci-dessus :
# l'anti-deepfake (liveness active + vérification ASR) s'applique dès
# l'enrôlement, pas seulement à la vérification ultérieure.
# ---------------------------------------------------------------------------

class GuidedFaceEnrollView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-enroll-guided"

    def post(self, request):
        serializer = GuidedFaceEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verifier = FaceLivenessVerifier()
        last_good_frame = None

        for capture in serializer.validated_data["captures"]:
            frames = [decode_base64_frame(f) for f in capture["frames"]]
            result = verifier.verify(frames, capture["gesture"])
            if not result["liveness_ok"]:
                return Response(
                    {
                        "detail": f"Geste '{capture['gesture']}' non validé. Recommencez ce geste.",
                        "failed_gesture": capture["gesture"],
                        **result,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            last_good_frame = frames[-1]

        try:
            embedding = extract_face_embedding(last_good_frame)
        except FaceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del last_good_frame

        profile, _ = BiometricProfile.objects.get_or_create(
            user=request.user, defaults={"consent_given_at": timezone.now()}
        )
        profile.face_embedding = embedding.tolist()
        profile.face_enrolled_at = timezone.now()
        profile.save(update_fields=["face_embedding", "face_enrolled_at", "updated_at"])

        return Response(
            {"detail": "Visage enrôlé avec succès (tous les gestes validés)."},
            status=status.HTTP_201_CREATED,
        )


class GuidedVoiceEnrollView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "biometric-enroll-guided"

    def post(self, request):
        serializer = GuidedVoiceEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        waveforms = []
        for rec in serializer.validated_data["digit_recordings"]:
            waveform, sample_rate = decode_base64_audio(rec["audio"])
            if not verify_spoken_challenge(waveform, sample_rate, rec["digit"]):
                return Response(
                    {
                        "detail": f"Le chiffre '{rec['digit']}' n'a pas été reconnu. Recommencez ce chiffre.",
                        "failed_digit": rec["digit"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            waveforms.append(waveform)

        combined = np.concatenate(waveforms)
        try:
            embedding = extract_voice_embedding(combined, 16000)
        except VoiceEmbeddingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            del waveforms, combined

        profile, _ = BiometricProfile.objects.get_or_create(
            user=request.user, defaults={"consent_given_at": timezone.now()}
        )
        profile.voice_embedding = embedding.tolist()
        profile.voice_enrolled_at = timezone.now()
        profile.save(update_fields=["voice_embedding", "voice_enrolled_at", "updated_at"])

        return Response(
            {"detail": "Voix enrôlée avec succès (5 chiffres vérifiés)."},
            status=status.HTTP_201_CREATED,
        )
