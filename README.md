# Auth Biométrique — Django

Système d'authentification multi-facteurs (mot de passe + visage + voix + OTP email) construit avec Django. **Aucun Docker requis** : la base de données est hébergée sur [Supabase](https://supabase.com) (Postgres managé avec `pgvector` déjà activé), donc l'installation locale se limite à un environnement virtuel Python classique.

## Stack

| Composant | Choix | Pourquoi |
|---|---|---|
| Backend | Django 5 + DRF | |
| Base de données | Supabase (Postgres + pgvector) | Pas de Postgres/Docker à installer en local |
| Visage | DeepFace (modèle ArcFace) | S'installe via `pip` seul, pas de compilation CMake/dlib |
| Anti-spoofing visage | MediaPipe (landmarks + clignement) | Vérification côté client en temps réel |
| Voix | SpeechBrain (ECAPA-TDNN) | Embeddings de locuteur robustes, pip-installable |
| OTP | Email SMTP | Solution de repli si l'utilisateur n'a activé aucune biométrie |

## Installation (sans Docker)

```bash
git clone https://github.com/<ton-compte>/biometric-auth-django.git
cd biometric-auth-django

python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# → remplis SECRET_KEY, DATABASE_URL (Supabase), EMAIL_*, RECAPTCHA_*
```

### Créer le projet Supabase (2 minutes)
1. [supabase.com](https://supabase.com) → New Project.
2. Settings → Database → Connection string → mode **URI** → colle-la dans `DATABASE_URL` du `.env`.
3. `pgvector` est déjà activé par défaut, aucune extension à installer.

### Lancer le projet
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
→ http://127.0.0.1:8000/

## Structure du projet

```
biometric-auth-django/
├── config/                 # settings, urls, wsgi/asgi
├── accounts/
│   ├── models.py           # CustomUser (email, embeddings visage/voix)
│   ├── views.py            # inscription, login, vérifications, dashboard
│   ├── forms.py
│   ├── urls.py
│   ├── biometrics/
│   │   ├── face.py         # DeepFace : embedding + comparaison cosinus
│   │   ├── voice.py        # SpeechBrain : embedding + comparaison cosinus
│   │   └── liveness.py     # Eye Aspect Ratio (anti-photo statique)
│   ├── templates/accounts/ # inscription, login, capture visage/voix, OTP
│   └── static/accounts/    # JS webcam/micro, CSS
├── requirements.txt
└── .env.example
```

## Flux d'authentification

1. **Inscription** (`/register/`) : email + mot de passe, puis choix des méthodes biométriques à activer.
   - *Visage* : capture webcam → `DeepFace.represent()` → vecteur 512-d stocké.
   - *Voix* : 3 mots aléatoires à prononcer → `SpeechBrain` → un vecteur 192-d par mot.
2. **Connexion, étape 1** (`/login/`) : email + mot de passe.
3. **Connexion, étape 2** (`/choose-method/`) : choix parmi les méthodes enregistrées + OTP toujours disponible en secours.
4. **Vérification** :
   - Visage : nouvelle capture → similarité cosinus avec le vecteur stocké (seuil `FACE_MATCH_THRESHOLD`, réglable dans `.env`).
   - Voix : 3 mots aléatoires parmi ceux enregistrés, comparaison embedding par embedding.
   - OTP : code à 6 chiffres envoyé par email, valable 5 minutes.

## Notes de sécurité (à lire avant tout déploiement réel)

- Le seuil de correspondance (`FACE_MATCH_THRESHOLD` / `VOICE_MATCH_THRESHOLD`) doit être calibré avec de vraies données de test — les valeurs par défaut sont des points de départ raisonnables, pas des garanties.
- La détection de vivacité (`liveness.py`) est un garde-fou basique (ratio d'ouverture des yeux), pas un système anti-spoofing complet. Pour une mise en production, envisager un modèle de liveness passif dédié.
- Les embeddings sont actuellement stockés en `JSONField` pour rester compatibles SQLite en dev. En production sur Supabase, migrer vers une vraie colonne `vector` (pgvector) et faire les recherches de similarité en SQL pour de meilleures performances à grande échelle.
- Ne jamais committer `.env` (déjà exclu via `.gitignore`).

## Pousser sur GitHub

```bash
git init
git add .
git commit -m "Initial commit: auth biométrique Django (visage + voix + OTP)"
git branch -M main
git remote add origin https://github.com/<ton-compte>/biometric-auth-django.git
git push -u origin main
```

## Prochaines étapes suggérées

- Ajouter Google Authenticator (TOTP) via `pyotp` comme méthode supplémentaire.
- Rate-limiting sur les tentatives de vérification biométrique (django-ratelimit).
- Tests automatisés (`accounts/tests.py` est prêt à recevoir des tests pytest-django).
