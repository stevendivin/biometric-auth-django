import random
import string
from datetime import timedelta

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.contrib.auth.views import LogoutView

from .forms import RegisterForm, LoginForm
from .models import CustomUser
from .biometrics import face as face_bio
from .biometrics import voice as voice_bio

OTP_VALIDITY = timedelta(minutes=5)
VOICE_WORDLIST = [
    "arbre", "nuage", "rivière", "montagne", "soleil", "orange", "violet",
    "guitare", "fenêtre", "papillon", "voyage", "lumière", "tempête", "jardin", "silence",
]


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()

            # Face enrollment (optional, image posted as base64 handled via JS -> hidden field)
            face_image = request.POST.get("face_image_data")
            if "face" in user.biometric_methods and face_image:
                embedding = face_bio.get_face_embedding(face_image)
                if embedding is None:
                    messages.error(request, "Aucun visage détecté sur l'image. Réessayez.")
                    user.delete()
                    return render(request, "accounts/register.html", {"form": form})
                user.face_embedding = embedding
                user.face_enrolled_at = timezone.now()

            # Voice enrollment happens via a separate AJAX flow (see enroll_voice_word
            # below) that stores progress in the session; we just persist it here.
            if "voice" in user.biometric_methods:
                voice_data = request.session.get("voice_enrollment")
                if not voice_data or len(voice_data.get("embeddings", [])) < 3:
                    messages.error(request, "Enrôlement vocal incomplet. Recommencez.")
                    user.delete()
                    return render(request, "accounts/register.html", {"form": form})
                user.voice_phrases = voice_data["phrases"]
                user.voice_embeddings = voice_data["embeddings"]
                user.voice_enrolled_at = timezone.now()
                del request.session["voice_enrollment"]

            user.save()
            messages.success(request, "Compte créé. Vous pouvez vous connecter.")
            return redirect("accounts:login_step1")
    else:
        form = RegisterForm()

    voice_words = random.sample(VOICE_WORDLIST, 3)
    return render(request, "accounts/register.html", {"form": form, "voice_words": voice_words})


def enroll_voice_word(request):
    """AJAX endpoint hit once per spoken word during registration."""
    if request.method != "POST":
        return _json(400, {"error": "POST requis"})

    word = request.POST.get("word")
    audio_file = request.FILES.get("audio")
    if not word or not audio_file:
        return _json(400, {"error": "mot ou audio manquant"})

    embedding = voice_bio.get_voice_embedding(audio_file.read())

    progress = request.session.get("voice_enrollment", {"phrases": [], "embeddings": []})
    progress["phrases"].append(word)
    progress["embeddings"].append(embedding)
    request.session["voice_enrollment"] = progress
    request.session.modified = True

    return _json(200, {"status": "ok", "count": len(progress["embeddings"])})


def login_step1(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                user = CustomUser.objects.get(email=form.cleaned_data["email"])
            except CustomUser.DoesNotExist:
                messages.error(request, "Identifiants invalides.")
                return render(request, "accounts/login.html", {"form": form})

            if not user.check_password(form.cleaned_data["password"]):
                messages.error(request, "Identifiants invalides.")
                return render(request, "accounts/login.html", {"form": form})

            request.session["preauth_user_id"] = user.id
            return redirect("accounts:choose_method")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form})


def choose_method(request):
    user_id = request.session.get("preauth_user_id")
    if not user_id:
        return redirect("accounts:login_step1")
    user = get_object_or_404(CustomUser, id=user_id)

    available = list(user.biometric_methods) + ["otp"]
    if request.method == "POST":
        method = request.POST.get("method")
        if method not in available:
            messages.error(request, "Méthode invalide.")
        else:
            request.session["auth_method"] = method
            if method == "face":
                return redirect("accounts:face_verify")
            if method == "voice":
                return redirect("accounts:voice_verify")
            return redirect("accounts:send_otp")
    return render(request, "accounts/choose_method.html", {"methods": available})


def face_verify(request):
    user_id = request.session.get("preauth_user_id")
    if not user_id:
        return redirect("accounts:login_step1")
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == "POST":
        image_data = request.POST.get("face_image_data")
        candidate = face_bio.get_face_embedding(image_data)
        if candidate is None:
            return _json(200, {"match": False, "error": "Aucun visage détecté"})

        is_match, score = face_bio.match_face(candidate, user.face_embedding)
        if is_match:
            auth_login(request, user)
            del request.session["preauth_user_id"]
        return _json(200, {"match": is_match, "score": round(score, 3)})

    return render(request, "accounts/face_capture.html")


def voice_verify(request):
    user_id = request.session.get("preauth_user_id")
    if not user_id:
        return redirect("accounts:login_step1")
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == "GET":
        challenge_words = random.sample(user.voice_phrases, min(3, len(user.voice_phrases)))
        request.session["voice_challenge"] = {"words": challenge_words, "index": 0, "attempts": 0}
        return render(request, "accounts/voice_capture.html", {"word": challenge_words[0]})

    # POST: one spoken word per request
    challenge = request.session.get("voice_challenge")
    if not challenge:
        return _json(400, {"error": "session expirée"})

    audio_file = request.FILES.get("audio")
    candidate = voice_bio.get_voice_embedding(audio_file.read())
    is_match, score = voice_bio.match_voice(candidate, user.voice_embeddings)

    if not is_match:
        challenge["attempts"] += 1
        request.session.modified = True
        if challenge["attempts"] >= 3:
            del request.session["voice_challenge"]
            return _json(200, {"status": "failed"})
        return _json(200, {"status": "retry", "attempts_left": 3 - challenge["attempts"]})

    challenge["index"] += 1
    if challenge["index"] >= len(challenge["words"]):
        auth_login(request, user)
        del request.session["preauth_user_id"]
        del request.session["voice_challenge"]
        return _json(200, {"status": "success"})

    request.session.modified = True
    return _json(200, {"status": "next", "word": challenge["words"][challenge["index"]]})


def send_otp(request):
    user_id = request.session.get("preauth_user_id")
    if not user_id:
        return redirect("accounts:login_step1")
    user = get_object_or_404(CustomUser, id=user_id)

    code = "".join(random.choices(string.digits, k=6))
    request.session["otp"] = {"code": code, "expires": (timezone.now() + OTP_VALIDITY).isoformat()}

    send_mail(
        subject="Votre code de connexion",
        message=f"Votre code à usage unique est : {code} (valable 5 minutes).",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
    )
    return redirect("accounts:verify_otp")


def verify_otp(request):
    user_id = request.session.get("preauth_user_id")
    if not user_id:
        return redirect("accounts:login_step1")

    if request.method == "POST":
        submitted = request.POST.get("code", "")
        otp = request.session.get("otp")
        if not otp or timezone.now().isoformat() > otp["expires"]:
            messages.error(request, "Code expiré. Renvoyez-en un.")
        elif submitted == otp["code"]:
            user = get_object_or_404(CustomUser, id=user_id)
            auth_login(request, user)
            del request.session["preauth_user_id"]
            del request.session["otp"]
            return redirect("accounts:dashboard")
        else:
            messages.error(request, "Code incorrect.")
    return render(request, "accounts/otp_verify.html")


def resend_otp(request):
    return send_otp(request)


@login_required
def dashboard(request):
    return render(request, "accounts/dashboard.html", {"user": request.user})


class CustomLogoutView(LogoutView):
    next_page = "accounts:login_step1"


def _json(status, payload):
    from django.http import JsonResponse

    return JsonResponse(payload, status=status)
