from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Extends Django's user with biometric enrollment data.

    Embeddings are stored as JSONField (list of floats) so the project runs
    on plain SQLite during development. In production on Supabase, swap this
    for a native `vector` column (pgvector) and use cosine-distance queries
    directly in SQL for fast nearest-neighbour lookups — see README.md.
    """

    BIOMETRIC_CHOICES = [
        ("face", "Reconnaissance faciale"),
        ("voice", "Reconnaissance vocale"),
    ]

    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    biometric_methods = models.JSONField(default=list, blank=True)

    # --- Face ---
    face_embedding = models.JSONField(null=True, blank=True)  # 512-d ArcFace vector
    face_enrolled_at = models.DateTimeField(null=True, blank=True)

    # --- Voice ---
    voice_phrases = models.JSONField(default=list, blank=True)     # words spoken during enrollment
    voice_embeddings = models.JSONField(default=list, blank=True)  # one ECAPA-TDNN vector per phrase
    voice_enrolled_at = models.DateTimeField(null=True, blank=True)

    def has_method(self, method: str) -> bool:
        return method in (self.biometric_methods or [])

    def __str__(self):
        return self.email
