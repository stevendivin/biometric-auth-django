from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "biometric_methods", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Biométrie", {"fields": ("biometric_methods", "face_enrolled_at", "voice_enrolled_at")}),
    )
