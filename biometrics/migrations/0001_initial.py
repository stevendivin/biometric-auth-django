import uuid

import django.db.models.deletion
import pgvector.django
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Active l'extension "vector" sur la base PostgreSQL (équivalent de
        # `CREATE EXTENSION IF NOT EXISTS vector;`). Nécessite que le rôle
        # PostgreSQL utilisé ait le droit CREATE EXTENSION.
        pgvector.django.VectorExtension(),
        migrations.CreateModel(
            name="BiometricProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("face_embedding", pgvector.django.VectorField(blank=True, dimensions=512, null=True)),
                ("voice_embedding", pgvector.django.VectorField(blank=True, dimensions=192, null=True)),
                ("face_enrolled_at", models.DateTimeField(blank=True, null=True)),
                ("voice_enrolled_at", models.DateTimeField(blank=True, null=True)),
                ("consent_given_at", models.DateTimeField()),
                ("consent_withdrawn_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="biometric_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LivenessChallenge",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("modality", models.CharField(choices=[("face", "Face"), ("voice", "Voice")], max_length=10)),
                ("challenge_value", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("consumed", models.BooleanField(default=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liveness_challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AuthAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("modality", models.CharField(max_length=10)),
                (
                    "result",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("failed_match", "Failed match"),
                            ("failed_liveness", "Failed liveness"),
                            ("failed_challenge", "Failed challenge"),
                            ("error", "Error"),
                        ],
                        max_length=20,
                    ),
                ),
                ("similarity_score", models.FloatField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
