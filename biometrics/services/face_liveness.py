"""
Anti-deepfake facial à deux couches, combinées lors de chaque authentification :

1. LIVENESS PASSIVE : sur chaque frame de la séquence, DeepFace.extract_faces
   avec anti_spoofing=True fait tourner un modèle CNN dédié (MiniFASNet) qui
   détecte les artefacts typiques d'une présentation frauduleuse (photo
   imprimée, écran de smartphone/tablette rejouant une vidéo, masque).
   La plupart des "attaques deepfake" en pratique consistent à rejouer une
   vidéo truquée devant la caméra : cette étape les attrape déjà en grande
   partie (moiré, reflets, texture d'écran).

2. CHALLENGE ACTIF (le vrai verrou anti-deepfake) : le serveur tire un geste
   aléatoire (cligner des yeux deux fois, tourner la tête, sourire, hocher la
   tête) que l'utilisateur doit exécuter EN DIRECT dans une fenêtre de temps
   courte. On vérifie via les landmarks MediaPipe Face Mesh que le geste
   demandé a réellement été exécuté. Un deepfake pré-généré ne peut pas
   réagir à une instruction tirée au hasard après coup ; il faudrait une
   génération deepfake interactive en temps réel, un niveau d'attaque
   nettement plus coûteux qu'un simple rejeu de vidéo.

Limite honnête : ce système ne protège pas contre un deepfake *génératif et
interactif en temps réel* piloté par un attaquant sophistiqué. Pour des
usages à très haut risque, la biométrie ne doit rester qu'un facteur parmi
d'autres (cf. recommandation MFA), jamais le facteur unique.
"""

import random
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from deepface import DeepFace
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.core.base_options import BaseOptions

# La nouvelle API MediaPipe "Tasks" (FaceLandmarker) remplace l'ancienne
# mp.solutions.face_mesh, supprimée dans les versions récentes de mediapipe
# et qui causait un conflit de version protobuf avec tensorflow (deepface).
# Le modèle est téléchargé une seule fois et mis en cache localement.
_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
_MODEL_PATH = Path.home() / ".cache" / "biometric_auth_models" / "face_landmarker.task"

_landmarker = None


def _ensure_model_downloaded() -> Path:
    if not _MODEL_PATH.exists():
        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    return _MODEL_PATH


def get_face_landmarker() -> mp_vision.FaceLandmarker:
    global _landmarker
    if _landmarker is None:
        model_path = _ensure_model_downloaded()
        options = mp_vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=1,
        )
        _landmarker = mp_vision.FaceLandmarker.create_from_options(options)
    return _landmarker

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH_LEFT, MOUTH_RIGHT = 61, 291
MOUTH_TOP, MOUTH_BOTTOM = 13, 14
NOSE_TIP = 1
LEFT_CHEEK, RIGHT_CHEEK = 234, 454


def generate_face_challenge() -> str:
    return random.choice(["BLINK_TWICE", "TURN_HEAD_LEFT", "TURN_HEAD_RIGHT", "SMILE", "NOD"])


def _eye_aspect_ratio(landmarks, eye_idx, w, h) -> float:
    pts = np.array([(landmarks[i].x * w, landmarks[i].y * h) for i in eye_idx])
    vert1 = np.linalg.norm(pts[1] - pts[5])
    vert2 = np.linalg.norm(pts[2] - pts[4])
    horiz = np.linalg.norm(pts[0] - pts[3])
    return (vert1 + vert2) / (2.0 * horiz)


def _head_yaw(landmarks, w, h) -> float:
    """Approxime l'angle de rotation horizontale de la tête (positif = vers la droite)."""
    nose = np.array([landmarks[NOSE_TIP].x * w, landmarks[NOSE_TIP].y * h])
    left = np.array([landmarks[LEFT_CHEEK].x * w, landmarks[LEFT_CHEEK].y * h])
    right = np.array([landmarks[RIGHT_CHEEK].x * w, landmarks[RIGHT_CHEEK].y * h])
    center = (left + right) / 2
    face_width = np.linalg.norm(right - left)
    if face_width == 0:
        return 0.0
    return float((nose[0] - center[0]) / face_width)


def _smile_ratio(landmarks, w, h) -> float:
    """Ratio largeur/hauteur de bouche : augmente nettement lors d'un sourire."""
    left = np.array([landmarks[MOUTH_LEFT].x * w, landmarks[MOUTH_LEFT].y * h])
    right = np.array([landmarks[MOUTH_RIGHT].x * w, landmarks[MOUTH_RIGHT].y * h])
    top = np.array([landmarks[MOUTH_TOP].x * w, landmarks[MOUTH_TOP].y * h])
    bottom = np.array([landmarks[MOUTH_BOTTOM].x * w, landmarks[MOUTH_BOTTOM].y * h])
    mouth_width = np.linalg.norm(right - left)
    mouth_height = np.linalg.norm(top - bottom)
    return mouth_width / max(mouth_height, 1e-6)


class FaceLivenessVerifier:
    def __init__(self, ear_blink_threshold: float = 0.21, yaw_threshold: float = 0.18):
        self.ear_blink_threshold = ear_blink_threshold
        self.yaw_threshold = yaw_threshold

    def _passive_antispoofing(self, frame_bgr: np.ndarray) -> tuple[bool, float]:
        try:
            faces = DeepFace.extract_faces(
                img_path=frame_bgr,
                detector_backend="mediapipe",
                anti_spoofing=True,
                enforce_detection=True,
            )
        except ValueError:
            return False, 0.0
        if not faces:
            return False, 0.0
        face = faces[0]
        return bool(face.get("is_real", False)), float(face.get("antispoof_score", 0.0))

    def _active_challenge(self, frames_bgr: list[np.ndarray], challenge: str) -> bool:
        ear_values, yaw_values, smile_values = [], [], []
        landmarker = get_face_landmarker()

        for frame in frames_bgr:
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
            if not result.face_landmarks:
                continue
            lm = result.face_landmarks[0]
            ear_values.append(
                (_eye_aspect_ratio(lm, LEFT_EYE, w, h) + _eye_aspect_ratio(lm, RIGHT_EYE, w, h)) / 2
            )
            yaw_values.append(_head_yaw(lm, w, h))
            smile_values.append(_smile_ratio(lm, w, h))

        # Pas assez de frames avec un visage exploitable -> on refuse par prudence
        if len(ear_values) < 3:
            return False

        if challenge == "BLINK_TWICE":
            blinks = sum(
                1
                for i in range(1, len(ear_values))
                if ear_values[i] < self.ear_blink_threshold <= ear_values[i - 1]
            )
            return blinks >= 2

        if challenge == "TURN_HEAD_LEFT":
            return min(yaw_values) < -self.yaw_threshold

        if challenge == "TURN_HEAD_RIGHT":
            return max(yaw_values) > self.yaw_threshold

        if challenge == "NOD":
            return (max(yaw_values) - min(yaw_values)) > 0.05

        if challenge == "SMILE":
            # Seuil approximatif basé sur la variation par rapport à la première
            # frame (prise comme référence "neutre"). À calibrer empiriquement ;
            # un classifieur dédié sur les landmarks serait plus robuste en prod.
            return (max(smile_values) - smile_values[0]) > 0.6

        return False

    def verify(self, frames_bgr: list[np.ndarray], challenge: str) -> dict:
        antispoof_results = [self._passive_antispoofing(f) for f in frames_bgr]
        real_votes = sum(1 for is_real, _ in antispoof_results if is_real)
        passive_ok = real_votes >= (len(frames_bgr) // 2 + 1)  # majorité des frames jugées réelles

        active_ok = self._active_challenge(frames_bgr, challenge)

        scores = [s for _, s in antispoof_results]
        return {
            "passive_liveness_ok": passive_ok,
            "active_challenge_ok": active_ok,
            "liveness_ok": passive_ok and active_ok,
            "avg_antispoof_score": float(np.mean(scores)) if scores else 0.0,
        }
