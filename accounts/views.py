from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, authenticate, get_user_model
from django.http import HttpResponse
from .forms import CustomUserCreationForm, LoginForm  
from .models import OTPCode
from .utils import send_otp_email

# Récupère le modèle utilisateur actif (CustomUser)
User = get_user_model()

# === Inscription ===
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Récupération des données biométriques
            biometric_methods = form.cleaned_data.get('biometric_methods', [])
            camera_image = form.cleaned_data.get('camera_image', '')
            voice_data = form.cleaned_data.get('voice_data', '')

            if 'face' in biometric_methods and camera_image:
                user.face_enrolled = True
                # Si vous stockez l'image, faites-le ici
            if 'voice' in biometric_methods and voice_data:
                user.voice_enrolled = True
                # Stockez voice_data si nécessaire
            user.save()


            
            messages.success(request, 'Inscription réussie ! Vous pouvez vous connecter.')
            return redirect('accounts:login_step1')
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_step1(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Générer un OTP
            otp = OTPCode.create_otp(user)
            send_otp_email(user, otp.code)
            # Stocker l'ID utilisateur en session pour la vérification OTP
            request.session['pending_user_id'] = user.id
            # Rediriger vers le choix de méthode
            return redirect('accounts:choose_method')
        else:
            messages.error(request, "Identifiants incorrects. Veuillez réessayer.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def otp_verify(request):
    # Récupérer l'utilisateur en attente
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, "Session expirée. Veuillez vous reconnecter.")
        return redirect('accounts:login_step1')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")
        return redirect('accounts:login_step1')

    if request.method == 'POST':
        code = request.POST.get('otp_code')
        # Récupérer l'OTP valide pour cet utilisateur
        otp = OTPCode.objects.filter(user=user, is_used=False).order_by('-created_at').first()
        if otp and otp.is_valid() and otp.code == code:
            # Marquer comme utilisé
            otp.is_used = True
            otp.save()
            # Connecter l'utilisateur
            login(request, user)
            # Nettoyer la session de manière sécurisée
            request.session.pop('pending_user_id', None)
            messages.success(request, "Authentification réussie ! Bienvenue.")
            return redirect('accounts:dashboard')  # À adapter selon votre vue d'accueil
        
        else:
            messages.error(request, "Code OTP invalide ou expiré.")
    return render(request, 'otp_verify.html', {'method': 'otp'})

# === Choix de la méthode d'authentification (après login) ===
def choose_method(request):
    methods = ['face', 'voice', 'otp']
    if request.method == 'POST':
        method = request.POST.get('method')
        if method in methods:
            request.session['auth_method'] = method
            if method == 'face':
                return redirect('accounts:face_verify')
            elif method == 'voice':
                return redirect('accounts:voice_verify')
            else:
                return redirect('accounts:otp_verify')
        else:
            messages.error(request, "Veuillez sélectionner une méthode valide.")
    return render(request, 'choose_method.html', {'methods': methods})

# === Vérification faciale ===
def face_verify(request):
    # Ici vous implémenterez la logique de vérification faciale
    return render(request, 'face_verify.html', {'method': 'face'})

# === Vérification vocale ===
def voice_verify(request):
    # Ici vous implémenterez la logique de vérification vocale
    return render(request, 'voice_verify.html', {'method': 'voice'})

# === Enrôlement vocal (exemple) ===
def enroll_voice_word(request):
    # Vue pour enregistrer un mot de passe vocal (si besoin)
    return HttpResponse("Page d'enrôlement vocal (à implémenter)")

def resend_otp(request):
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, "Session expirée.")
        return redirect('accounts:login_step1')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")
        return redirect('accounts:login_step1')
    otp = OTPCode.create_otp(user)
    send_otp_email(user, otp.code)
    messages.success(request, "Un nouveau code OTP a été envoyé.")
    return redirect('accounts:otp_verify')
def dashboard(request):
    if not request.user.is_authenticated:
        messages.warning(request, "Vous devez être connecté.")
        return redirect('accounts:login_step1')
    
    context = {
        'user': request.user,
        'face_enrolled': request.user.face_enrolled,
        'voice_enrolled': request.user.voice_enrolled,
    }
    return render(request, 'dashboard.html', context)