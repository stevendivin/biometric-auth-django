"""
Lightweight liveness check: the primary challenge (blink / head-turn) runs
client-side with MediaPipe Face Landmarker (see static/accounts/js/face-capture.js)
so the user gets instant feedback without a round-trip per frame.

This module offers an optional server-side sanity check on the final
snapshot, computing the Eye Aspect Ratio (EAR) to make sure the submitted
frame isn't a static, wide-open-eyes photo replay. It is a deterrent, not a
full anti-spoofing system — see README "Security notes" for what a
production deployment should add (e.g. a dedicated passive-liveness model).
"""
import numpy as np

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def eye_aspect_ratio(landmarks, eye_indices) -> float:
    pts = np.array([[landmarks[i].x, landmarks[i].y] for i in eye_indices])
    vertical = np.linalg.norm(pts[1] - pts[5]) + np.linalg.norm(pts[2] - pts[4])
    horizontal = np.linalg.norm(pts[0] - pts[3])
    return vertical / (2.0 * horizontal)


def looks_like_a_live_frame(landmarks) -> bool:
    """Very loose sanity check — rejects only obviously-flat/inserted images."""
    ear = (eye_aspect_ratio(landmarks, LEFT_EYE) + eye_aspect_ratio(landmarks, RIGHT_EYE)) / 2
    return 0.10 < ear < 0.45
