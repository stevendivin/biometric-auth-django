# accounts/utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_otp_email(user, otp_code):
    """
    Envoie un email contenant le code OTP à l'utilisateur.
    """
    subject = "Votre code de vérification OTP"
    message = (
        f"Bonjour {user.username},\n\n"
        f"Votre code OTP est : {otp_code}\n"
        f"Il est valable 5 minutes.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
        f"Cordialement,\nL'équipe de sécurité."
    )
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list)