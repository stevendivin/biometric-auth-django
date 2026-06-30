"""
Décodage des payloads base64 envoyés par le client, entièrement EN MÉMOIRE.

Règle de sécurité centrale du projet : ni l'image, ni l'audio brut ne doivent
jamais être écrits sur disque ou en base de données. Une fois l'embedding
extrait, les variables contenant les données brutes sont supprimées
explicitement (`del`) dans les vues pour limiter leur durée de vie en mémoire.
"""

import base64
import io

import cv2
import librosa
import numpy as np
import soundfile as sf

TARGET_SAMPLE_RATE = 16000  # attendu par SpeechBrain (ECAPA) et faster-whisper


def decode_base64_frame(b64_str: str) -> np.ndarray:
    """Décode une image JPEG/PNG encodée en base64 vers un array BGR (OpenCV)."""
    try:
        data = base64.b64decode(b64_str, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Encodage base64 invalide pour l'image.") from exc

    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Image illisible ou corrompue.")
    return frame


def decode_base64_audio(b64_str: str, target_sr: int = TARGET_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """
    Décode un fichier audio (WAV/FLAC/OGG) encodé en base64, le convertit en
    mono et le ré-échantillonne à `target_sr` si nécessaire.
    """
    try:
        data = base64.b64decode(b64_str, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("Encodage base64 invalide pour l'audio.") from exc

    waveform, sample_rate = sf.read(io.BytesIO(data), dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)

    if sample_rate != target_sr:
        waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=target_sr)
        sample_rate = target_sr

    return waveform, sample_rate
