"""
Calcul de similarité entre embeddings et helpers pgvector.

Note de design : pour une VÉRIFICATION 1:1 (l'utilisateur prétend être X,
on compare juste à l'embedding de X), comparer deux vecteurs en Python est
suffisant et évite un aller-retour SQL. pgvector devient réellement utile
pour une IDENTIFICATION 1:N (retrouver qui est la personne parmi tous les
profils) : c'est ce que fait `find_closest_face_match` ci-dessous via
l'opérateur de distance cosinus indexé de pgvector.
"""

import numpy as np
from pgvector.django import CosineDistance

# Seuils à calibrer empiriquement (courbes FAR/FRR) sur un jeu de validation
# représentatif avant toute mise en production. Les valeurs ci-dessous sont
# des points de départ raisonnables pour ArcFace / ECAPA-TDNN, pas des
# garanties de sécurité.
FACE_MATCH_THRESHOLD = 0.68
VOICE_MATCH_THRESHOLD = 0.55


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_closest_face_match(embedding, queryset, max_distance: float = 0.32):
    """
    Recherche 1:N via pgvector (distance cosinus indexée). Utile uniquement
    si vous proposez un mode "connexion sans identifiant, juste le visage".
    Pour le flux MFA implémenté dans ce projet (vérification 1:1), cette
    fonction n'est pas appelée mais est fournie pour montrer l'usage correct
    de pgvector.
    """
    match = (
        queryset.exclude(face_embedding__isnull=True)
        .annotate(distance=CosineDistance("face_embedding", embedding))
        .order_by("distance")
        .first()
    )
    if match and match.distance <= max_distance:
        return match, 1 - match.distance
    return None, None
