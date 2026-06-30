"""
Anti-deepfake vocal à deux couches :

1. CHALLENGE ALÉATOIRE PRONONCÉ : le serveur génère une séquence de 6
   chiffres aléatoires que l'utilisateur doit prononcer en direct. Un ASR
   léger (faster-whisper) vérifie que les chiffres réellement prononcés
   correspondent au challenge. Cela élimine d'emblée le simple REJEU d'un
   enregistrement audio préexistant, et complique significativement
   l'usage d'un deepfake vocal "statique" (il faudrait un clonage vocal
   capable de prononcer en temps réel une séquence imprévisible).

2. HEURISTIQUE DE DÉTECTION DE SYNTHÈSE/REJEU (passive) : analyse
   spectrale simple cherchant des indices de voix synthétique ou rejouée
   (platitude spectrale anormale, absence de micro-variations naturelles).

Limite IMPORTANTE et honnête : ce n'est PAS un modèle anti-spoofing entraîné
(type AASIST/RawNet2 sur le corpus ASVspoof). C'est une heuristique de base.
Pour un système à enjeux réels, remplacez `replay_spoof_heuristic` par un
modèle dédié entraîné sur ASVspoof, et ne laissez jamais la voix comme seul
facteur pour une action sensible.
"""

import random

import librosa
import numpy as np
from faster_whisper import WhisperModel

_asr_model = None


def get_asr_model() -> WhisperModel:
    global _asr_model
    if _asr_model is None:
        _asr_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _asr_model


def generate_voice_challenge() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def verify_spoken_challenge(waveform: np.ndarray, sample_rate: int, expected_digits: str) -> bool:
    model = get_asr_model()
    segments, _ = model.transcribe(waveform, language="fr", vad_filter=True)
    spoken_digits = "".join(c for seg in segments for c in seg.text if c.isdigit())
    return spoken_digits == expected_digits


def replay_spoof_heuristic(waveform: np.ndarray, sample_rate: int) -> dict:
    flatness = librosa.feature.spectral_flatness(y=waveform)[0]
    flatness_mean = float(np.mean(flatness)) if flatness.size else 0.0

    rms = librosa.feature.rms(y=waveform)[0]
    silence_ratio = float(np.mean(rms < 0.01)) if rms.size else 1.0

    jitter = float(np.std(np.diff(waveform.astype(np.float32)))) if waveform.size > 1 else 0.0

    # Seuils empiriques de base, à recalibrer sur vos propres enregistrements
    # (voix réelles vs TTS vs rejeu) avant toute mise en production.
    suspicious = flatness_mean > 0.45 or jitter < 1e-4

    return {
        "spectral_flatness": flatness_mean,
        "silence_ratio": silence_ratio,
        "jitter": jitter,
        "suspicious_synthetic": suspicious,
    }
