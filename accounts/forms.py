from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class RegisterForm(UserCreationForm):
    biometric_methods = forms.MultipleChoiceField(
        choices=CustomUser.BIOMETRIC_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Méthodes biométriques à activer",
    )

    class Meta:
        model = CustomUser
        fields = ["username", "email", "password1", "password2", "biometric_methods"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.biometric_methods = self.cleaned_data.get("biometric_methods", [])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
