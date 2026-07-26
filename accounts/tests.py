from django.test import TestCase
from django.urls import reverse
from .models import CustomUser


class RegistrationFlowTests(TestCase):
    def test_register_page_loads(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)

    def test_user_can_register_without_biometrics(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "a-very-strong-pass-123",
            "password2": "a-very-strong-pass-123",
        })
        self.assertTrue(CustomUser.objects.filter(email="test@example.com").exists())
