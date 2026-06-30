"""
Extraction d'embedding facial (ArcFace via DeepFace) avec anti-spoofing
passif intégré.

L'extraction se fait en deux étapes :
  1. DeepFace.extract_faces(..., anti_spoofing=True) détecte le visage ET
     évalue s'il s'agit d'une vraie personne ou d'une présentation frauduleuse
     (photo imprimée, écran de téléphone, masque) via un modèle CNN dédié
     (MiniFASNet / Silent-Face-Anti-Spoofing).
  2. Si le visage est jugé réel, on calcule l'embedding ArcFace 512-d sur le
     visage déjà extrait/aligné (detector_backend="skip" pour ne pas refaire
     une détection).

Cette étape ne suffit PAS seule contre un deepfake vidéo joué sur un écran
(d'où le challenge actif dans face_liveness.py qui doit être combiné à cette
fonction lors de l'authentification).
"""

import numpy as np
from deepface import DeepFace


class FaceEmbeddingError(Exception):
    pass


def extract_face_embedding(frame_bgr: np.ndarray) -> np.ndarray:
    try:
        faces = DeepFace.extract_faces(
            img_path=frame_bgr,
            detector_backend="mediapipe",
            anti_spoofing=True,
            enforce_detection=True,
        )
    except ValueError as exc:
        raise FaceEmbeddingError(f"Aucun visage exploitable détecté : {exc}") from exc

    if not faces:
        raise FaceEmbeddingError("Aucun visage détecté dans l'image.")

    face_data = faces[0]
    if not face_data.get("is_real", True):
        raise FaceEmbeddingError(
            "Spoofing détecté lors de l'extraction (photo, écran ou masque)."
        )

    # `face_data["face"]` est un array RGB normalisé [0, 1] renvoyé par DeepFace.
    aligned_face = (face_data["face"] * 255).astype("uint8")

    result = DeepFace.represent(
        img_path=aligned_face,
        model_name="ArcFace",
        detector_backend="skip",
        enforce_detection=False,
    )
    if not result:
        raise FaceEmbeddingError("Extraction d'embedding vide.")

    return np.array(result[0]["embedding"], dtype=np.float32)
