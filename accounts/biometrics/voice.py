"""
Voice embedding + matching, backed by SpeechBrain's pretrained
ECAPA-TDNN speaker-verification model.
"""
import io
import numpy as np
from django.conf import settings
from pydub import AudioSegment

_classifier = None  # lazy singleton, model is ~80MB and slow to load


def _get_classifier():
    global _classifier
    if _classifier is None:
        from speechbrain.inference.speaker import EncoderClassifier

        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb",
        )
    return _classifier


def webm_bytes_to_wav_tensor(audio_bytes: bytes):
    """Browser MediaRecorder produces webm/opus; SpeechBrain needs 16kHz mono wav."""
    import torch

    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
    return torch.tensor(samples).unsqueeze(0)


def get_voice_embedding(audio_bytes: bytes):
    """Returns a 192-d ECAPA-TDNN embedding (list of floats) for a spoken phrase."""
    classifier = _get_classifier()
    waveform = webm_bytes_to_wav_tensor(audio_bytes)
    embedding = classifier.encode_batch(waveform)
    return embedding.squeeze().detach().numpy().tolist()


def cosine_similarity(vec_a, vec_b) -> float:
    a, b = np.array(vec_a), np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def match_voice(candidate_embedding, stored_embeddings: list) -> tuple[bool, float]:
    """Compares against every enrolled phrase embedding, keeps the best score."""
    best = max(cosine_similarity(candidate_embedding, e) for e in stored_embeddings)
    return best >= settings.VOICE_MATCH_THRESHOLD, best
