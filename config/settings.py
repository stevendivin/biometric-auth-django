"""
Django settings for the biometric-auth-django project.
Deliberately Docker-free: config comes from a .env file (python-dotenv)
and the database is a hosted Supabase Postgres instance (pgvector built in).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_recaptcha",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.recaptcha_keys",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database: Supabase Postgres (pgvector extension is pre-enabled on Supabase) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    import urllib.parse as up

    up.uses_netloc.append("postgres")
    url = up.urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or 5432,
        }
    }
else:
    # Fallback for quick local testing without Supabase configured yet
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "accounts" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login_step1"
LOGIN_REDIRECT_URL = "accounts:dashboard"

# --- Email (OTP fallback) ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- reCAPTCHA ---
RECAPTCHA_PUBLIC_KEY = os.environ.get("RECAPTCHA_PUBLIC_KEY", "")
RECAPTCHA_PRIVATE_KEY = os.environ.get("RECAPTCHA_PRIVATE_KEY", "")

# --- Biometric thresholds (see accounts/biometrics/) ---
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", 0.68))
VOICE_MATCH_THRESHOLD = float(os.environ.get("VOICE_MATCH_THRESHOLD", 0.75))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
