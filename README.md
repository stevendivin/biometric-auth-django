# Authentification biométrique (visage + voix) — Django / DRF / PostgreSQL+pgvector

## Installation locale (sans Docker)

### 1. Python

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Installation longue la première fois (torch, tensorflow, mediapipe ≈ 1-2 Go). Normal.

### 2. PostgreSQL + pgvector

Il faut un PostgreSQL local avec l'extension `vector` disponible. Deux options :

**Option A — le plus simple (recommandé sur Windows) : base gratuite hébergée**
Crée un projet gratuit sur [Supabase](https://supabase.com) ou [Neon](https://neon.tech) (les deux ont `pgvector` préinstallé). Récupère les identifiants de connexion (host, port, user, password, dbname) et mets-les dans `.env`.

**Option B — PostgreSQL local**
Installe PostgreSQL (https://www.postgresql.org/download/windows/), puis l'extension pgvector :
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
(nécessite que pgvector soit compilé/installé sur ta machine — sur Windows c'est plus pénible que via une base hébergée, d'où l'option A).

### 3. Configuration

```bash
cp .env.example .env
```

Édite `.env` :
```
DJANGO_SECRET_KEY=une-chaine-aleatoire-longue
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_HOST=...        # localhost, ou l'host fourni par Supabase/Neon
POSTGRES_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 4. Migrations + utilisateur

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Lancer le serveur

```bash
python manage.py runserver
```

Ouvre **http://localhost:8000/** dans le navigateur → page de connexion → connecte-toi avec le superuser créé → tableau de bord avec caméra et micro.

## Interface web

`http://localhost:8000/` :
- **Page de connexion** avec lien "Créer un compte" en bas.
- **Inscription** (`/signup/`) : nom d'utilisateur, mot de passe, confirmation. Connecte automatiquement et enchaîne sur l'enrôlement.
- **Enrôlement obligatoire** (`/enroll/`) : tant qu'il n'est pas terminé, **toutes les autres pages redirigent automatiquement ici** (middleware `RequireBiometricEnrollmentMiddleware`). Trois étapes :
  1. **Consentement** explicite (case à cocher obligatoire).
  2. **Visage** : 5 gestes demandés un par un (tourner à gauche, à droite, cligner des yeux, sourire, hocher la tête), chacun avec un compte à rebours de préparation puis une capture en rafale. Si la validation serveur échoue sur un geste, toute la séquence est à refaire (anti-deepfake actif dès l'enrôlement, pas seulement à la connexion).
  3. **Voix** : 5 chiffres affichés un par un, chacun avec un compte à rebours puis un enregistrement court. Échec sur un chiffre → toute la séquence vocale est à refaire.
  4. Une fois les deux terminés → redirection automatique vers le tableau de bord.
- **Tableau de bord** (`/`) : test libre de la vérification (visage avec geste aléatoire, voix avec chiffres aléatoires) une fois enrôlé.

Le tout passe par les mêmes endpoints DRF que documentés plus bas — les pages web sont des clients de test/onboarding au-dessus de l'API.

## Celery (optionnel pour tester l'interface)

Celery n'est utilisé ici que pour la tâche de nettoyage périodique des challenges expirés (`cleanup_expired_challenges`). **Ce n'est pas requis pour tester l'enrôlement/vérification** via l'interface web — tu peux ignorer Celery/Redis en développement. Si tu veux quand même le lancer (nécessite Redis local) :

```bash
celery -A config worker -l info --concurrency=1
celery -A config beat -l info
```

## Endpoints API (utilisés par l'interface web)

| Méthode | URL | Description |
|---|---|---|
| POST | `/api/biometrics/enroll/face/` | Enrôle le visage en une capture (frame + consent) |
| POST | `/api/biometrics/enroll/voice/` | Enrôle la voix en une capture (audio + consent) |
| POST | `/api/biometrics/enroll/face/guided/` | Enrôlement guidé : séquence de gestes vérifiés un par un (utilisé par `/enroll/`) |
| POST | `/api/biometrics/enroll/voice/guided/` | Enrôlement guidé : 5 chiffres vérifiés un par un (utilisé par `/enroll/`) |
| POST | `/api/biometrics/challenge/face/start/` | Démarre un challenge facial (renvoie un geste) |
| POST | `/api/biometrics/challenge/face/verify/` | Vérifie le visage (challenge_id + frames) |
| POST | `/api/biometrics/challenge/voice/start/` | Démarre un challenge vocal (renvoie des chiffres) |
| POST | `/api/biometrics/challenge/voice/verify/` | Vérifie la voix (challenge_id + audio) |

Authentification : session Django (utilisée par l'interface web) ou Token DRF via `POST /api/auth/token/`.

## Mécanismes anti-deepfake

**Visage** (`services/face_liveness.py`) :
- **Passif** : chaque frame passe par le modèle anti-spoofing intégré à DeepFace (MiniFASNet), qui détecte photo imprimée, écran de téléphone (moiré, reflets), masque.
- **Actif** : un geste est tiré aléatoirement côté serveur (cligner 2 fois, tourner la tête, sourire, hocher la tête) et doit être exécuté en direct dans les 30 secondes. Vérifié via les landmarks MediaPipe Face Mesh.

**Voix** (`services/voice_liveness.py`) :
- **Challenge prononcé** : 6 chiffres aléatoires à dire à voix haute, vérifiés par un ASR léger (faster-whisper).
- **Heuristique anti-synthèse** : analyse spectrale basique pour repérer des indices de voix de synthèse/rejouée — base de départ, pas un modèle entraîné dédié (voir limites dans le code).

## Pourquoi la biométrie est un 2ᵉ facteur ici, pas le seul

Tous les endpoints exigent `IsAuthenticated` : la biométrie élève une session déjà authentifiée par mot de passe, elle ne la remplace pas.

## Stockage des embeddings

`pgvector` a besoin du vecteur en clair pour calculer une distance cosinus indexée côté SQL. Les embeddings sont donc stockés en clair dans la colonne pgvector ; la protection repose sur le chiffrement au repos de PostgreSQL et un contrôle d'accès strict (jamais exposés en lecture via l'admin, voir `BiometricProfileAdmin`). Aucune image ni audio brut n'est jamais écrit sur disque : tout est traité en mémoire côté serveur, et les variables sont supprimées explicitement après extraction (`del frame`, `del waveform`).

## Calibration des seuils

`FACE_MATCH_THRESHOLD` (0.68) et `VOICE_MATCH_THRESHOLD` (0.55) dans `services/matching.py` sont des points de départ, pas des garanties. À calibrer sur tes propres données avant toute mise en production.

## Stack

Django 5 · DRF · PostgreSQL + pgvector · Celery + Redis (optionnel en dev) · DeepFace (ArcFace + MiniFASNet) · MediaPipe Face Mesh · SpeechBrain (ECAPA-TDNN) · faster-whisper · librosa
