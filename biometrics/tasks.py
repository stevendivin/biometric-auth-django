from celery import shared_task
from django.utils import timezone

from .models import LivenessChallenge


@shared_task
def cleanup_expired_challenges():
    """Purge périodique des challenges expirés (exécutée par Celery beat)."""
    deleted, _ = LivenessChallenge.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted


@shared_task
def warmup_models():
    """
    À appeler au démarrage d'un worker Celery pour précharger DeepFace
    (ArcFace + MiniFASNet) et SpeechBrain (ECAPA-TDNN) en mémoire et éviter
    une latence de plusieurs secondes sur la première requête utilisateur.
    """
    from .services.voice_service import get_classifier

    get_classifier()
