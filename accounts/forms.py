# accounts/forms.py
import base64
import os
import urllib.request
import numpy as np
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    biometric_methods = forms.MultipleChoiceField(
        choices=[('face', 'Reconnaissance faciale'), ('voice', 'Reconnaissance vocale')],
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    camera_image = forms.CharField(required=False, widget=forms.HiddenInput)
    voice_data = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def _get_face_cascade(self):
        """Charge le classifieur Haar pour la détection de visage.
           Importe OpenCV dynamiquement pour éviter les problèmes au démarrage.
        """
        try:
            import cv2
        except ImportError as e:
            raise ValidationError("OpenCV n'est pas installé. Veuillez l'installer pour la reconnaissance faciale.") from e

        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if not os.path.exists(cascade_path):
            # Télécharger le fichier si absent
            url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
            temp_path = os.path.join(os.path.dirname(__file__), 'haarcascade_frontalface_default.xml')
            try:
                urllib.request.urlretrieve(url, temp_path)
                cascade_path = temp_path
            except Exception as e:
                raise ValidationError("Impossible de télécharger le classifieur de visage.") from e

        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            raise ValidationError("Le classifieur de visage n'a pas pu être chargé.")
        return cascade

    def clean_camera_image(self):
        image_data = self.cleaned_data.get('camera_image')
        if not image_data:
            return image_data

        # Import dynamique d'OpenCV
        try:
            import cv2
        except ImportError:
            # Si OpenCV n'est pas installé, on accepte l'image sans validation
            # (on pourrait aussi lever une erreur)
            return image_data

        # Décoder l'image
        try:
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            img_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            raise ValidationError("Format d'image invalide.") from e

        # Détection de visage
        try:
            cascade = self._get_face_cascade()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        except Exception as e:
            raise ValidationError(f"Erreur lors de la détection de visage : {e}") from e

        if len(faces) == 0:
            raise ValidationError("Aucun visage détecté dans l'image. Veuillez recommencer la capture.")
        if len(faces) > 1:
            raise ValidationError("Plusieurs visages détectés. Veuillez ne capturer qu'un seul visage.")

        return image_data

    def clean(self):
        cleaned_data = super().clean()
        methods = cleaned_data.get('biometric_methods', [])
        if 'face' in methods and not cleaned_data.get('camera_image'):
            self.add_error('camera_image', 'Vous devez capturer une photo pour la reconnaissance faciale.')
            self.add_error(None, 'La photo faciale est requise si vous sélectionnez cette méthode.')
        if 'voice' in methods and not cleaned_data.get('voice_data'):
            self.add_error('voice_data', 'Vous devez enregistrer un échantillon vocal pour la reconnaissance vocale.')
            self.add_error(None, 'L\'enregistrement vocal est requis si vous sélectionnez cette méthode.')
        return cleaned_data


class LoginForm(AuthenticationForm):
    """Formulaire de connexion standard."""
    pass