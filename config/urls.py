from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/biometrics/", include("biometrics.urls")),
    path("api/auth/", include("rest_framework.urls")),
    path("api/auth/token/", obtain_auth_token, name="api-token-auth"),
    path("", include("biometrics.urls_web")),
]
