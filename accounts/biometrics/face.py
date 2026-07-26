"""
Face embedding + matching, backed by DeepFace (ArcFace model).

DeepFace is chosen over `face_recognition`/dlib specifically because it
installs with plain `pip install deepface` — no CMake/C++ build toolchain,
which matters for a Docker-free setup on a teammate's laptop.
"""
import numpy as np
from django.conf import settings


def get_face_embedding(image_path_or_array):
    """
    Returns a 512-d ArcFace embedding (list of floats) for the given image,
    or None if no face was detected.
    """
    from deepface import DeepFace  # imported lazily: heavy, TF-based

    try:
        result = DeepFace.represent(
            img_path=image_path_or_array,
            model_name="ArcFace",
            enforce_detection=True,
            detector_backend="mediapipe",
        )
        return result[0]["embedding"]
    except ValueError:
        # DeepFace raises ValueError when no face is found in the image
        return None


def cosine_similarity(vec_a, vec_b) -> float:
    a, b = np.array(vec_a), np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def match_face(candidate_embedding, stored_embedding) -> tuple[bool, float]:
    """Returns (is_match, similarity_score)."""
    similarity = cosine_similarity(candidate_embedding, stored_embedding)
    return similarity >= settings.FACE_MATCH_THRESHOLD, similarity
