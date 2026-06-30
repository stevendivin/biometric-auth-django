"""
Extraction d'embedding vocal via SpeechBrain (ECAPA-TDNN pré-entraîné sur
VoxCeleb). Le modèle est chargé une seule fois (singleton) car son chargement
est lourd ; en production, déclenchez `tasks.warmup_models` au démarrage des
workers Celery pour éviter la latence de premier appel sur l'utilisateur.
"""

import numpy as np
import torch
from speechbrain.inference.speaker import EncoderClassifier

_classifier = None


def get_classifier() -> EncoderClassifier:
    global _classifier
    if _classifier is None:
        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="/tmp/speechbrain_ecapa",
        )
    return _classifier


class VoiceEmbeddingError(Exception):
    pass


def extract_voice_embedding(waveform: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    `waveform` est un signal mono en mémoire (déjà ré-échantillonné à 16kHz
    par `biometrics.utils.decode_base64_audio`). Il n'est jamais écrit sur
    disque ; seul l'embedding retourné est destiné à être persisté.
    """
    if sample_rate != 16000:
        raise VoiceEmbeddingError("Le signal doit être ré-échantillonné à 16kHz avant extraction.")

    if waveform.size < sample_rate * 0.5:
        raise VoiceEmbeddingError("Signal audio trop court pour une extraction fiable (< 0.5s).")

    classifier = get_classifier()
    tensor = torch.from_numpy(waveform).float().unsqueeze(0)
    with torch.no_grad():
        embedding = classifier.encode_batch(tensor)
    return embedding.squeeze().cpu().numpy().astype(np.float32)
