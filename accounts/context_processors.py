from django.conf import settings


def recaptcha_keys(request):
    return {"RECAPTCHA_PUBLIC_KEY": settings.RECAPTCHA_PUBLIC_KEY}
