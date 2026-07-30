# accounts/models.py
import random
import string
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone



class CustomUser(AbstractUser):
    # Champs biométriques
    biometric_methods = models.JSONField(default=list, blank=True)  # Stocke les méthodes sélectionnées
    face_enrolled_at = models.DateTimeField(null=True, blank=True)
    voice_enrolled_at = models.DateTimeField(null=True, blank=True)
    camera_image = models.TextField(blank=True, null=True)  # Encodée en base64
    voice_data = models.TextField(blank=True, null=True)    # Encodée en base64

    def __str__(self):
        return self.username
    
class OTPCode(models.Model):
    """
    Modèle pour stocker les codes OTP (One-Time Password) utilisés
    pour la vérification à deux facteurs.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Référence au modèle utilisateur actif
        on_delete=models.CASCADE,
        related_name='otp_codes'
    )
    code = models.CharField(max_length=6)  # Code à 6 chiffres
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        """
        Vérifie si le code est toujours valide (non utilisé et non expiré).
        """
        return not self.is_used and timezone.now() < self.expires_at

    @staticmethod
    def generate_code():
        """
        Génère un code OTP aléatoire à 6 chiffres.
        """
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def create_otp(user, expiry_minutes=5):
        """
        Crée un nouvel OTP pour l'utilisateur donné.
        Invalide tous les OTP précédents non utilisés pour le même utilisateur.
        """
        # Invalider les anciens OTP non utilisés
        OTPCode.objects.filter(user=user, is_used=False).update(is_used=True)

        # Générer un nouveau code
        code = OTPCode.generate_code()
        expires_at = timezone.now() + timezone.timedelta(minutes=expiry_minutes)

        # Créer et sauvegarder le nouveau OTP
        otp = OTPCode.objects.create(
            user=user,
            code=code,
            expires_at=expires_at
        )
        return otp

    def __str__(self):
        return f"OTP pour {self.user.username} - {self.code} (valide jusqu'à {self.expires_at})"