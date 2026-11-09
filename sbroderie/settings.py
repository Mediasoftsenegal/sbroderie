"""
Configuration Django - Sénégal Broderie Moderne (portage de l'application PHP).

Les paramètres sensibles (base de données, clé secrète) sont lus depuis des
variables d'environnement afin de faciliter le déploiement sur cPanel.
Des valeurs par défaut identiques à l'application PHP d'origine sont fournies.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


# --- Sécurité ---------------------------------------------------------------
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "changez-moi-en-production-cle-secrete-sbroderie-0123456789abcdef",
)

DEBUG = env("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes", "on")

# En production, renseignez votre domaine cPanel (séparés par des virgules)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Requis par Django >= 4 pour les formulaires POST derrière un domaine
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in env("DJANGO_CSRF_TRUSTED", "").split(",")
    if o.strip()
]


# --- Applications -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "gestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sert les fichiers statiques (CSS/JS/images) directement depuis
    # l'application, en local comme sur cPanel, sans configuration Apache.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Messages sans contrib.auth : on garde le middleware messages mais on stocke en session
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
INSTALLED_APPS.insert(0, "django.contrib.messages")

ROOT_URLCONF = "sbroderie.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "gestion" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "gestion.context_processors.utilisateur",
            ],
        },
    },
]

WSGI_APPLICATION = "sbroderie.wsgi.application"


# --- Base de données --------------------------------------------------------
# Mêmes paramètres de connexion que l'application PHP d'origine.
# À surcharger via variables d'environnement sur cPanel.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "mediapla_sb"),
        "USER": env("DB_USER", "mediapla"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8",
            # Filet de sécurité : mode SQL sans ONLY_FULL_GROUP_BY (l'appli,
            # héritée du PHP, utilise des GROUP BY à l'ancienne). Les requêtes
            # ont aussi été rendues compatibles, ceci couvre les cas résiduels.
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
        },
    }
}


# --- Sessions ---------------------------------------------------------------
# Stockées côté fichier pour ne PAS créer de table dans la base existante.
SESSION_ENGINE = "django.contrib.sessions.backends.file"
SESSION_FILE_PATH = env("SESSION_DIR", str(BASE_DIR / "tmp_sessions"))
os.makedirs(SESSION_FILE_PATH, exist_ok=True)
SESSION_COOKIE_NAME = "sbroderie_session"


# --- Internationalisation ---------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Dakar"
USE_I18N = True
USE_TZ = False


# --- Fichiers statiques -----------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise : sert les fichiers statiques sans dépendre de DEBUG ni d'Apache.
# USE_FINDERS permet de les servir directement depuis le dossier `static/`
# même sans avoir lancé `collectstatic` (pratique en développement local).
WHITENOISE_USE_FINDERS = True
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ---------------------------------------------------------------------------
# Superuser applicatif (compte dédié)
# ---------------------------------------------------------------------------
# Le login désigné ici est le SEUL autorisé à accéder à la fenêtre de
# régularisation des factures non soldées. Surchargable par variable
# d'environnement SUPERUSER_LOGIN. Le compte doit exister dans la table `user`.
SUPERUSER_LOGIN = env("SUPERUSER_LOGIN", "Mous")

# Coordonnées de la société (utilisées sur les factures PDF)
SOCIETE = {
    "nom": "SENEGAL BRODERIE MODERNE (S.B.M)",
    "adresse1": "2, Place de l'Indépendance - Dakar",
    "adresse2": "N°29, Domaine Industriel - Sodida      Sea Plaza",
    "bp": "BP: 3392      Dakar",
    "tel": "Tél:+221 33 869 0068   Fax:+221 33 824 8050",
}

# ---------------------------------------------------------------------------
# Migrations désactivées : tous les modèles sont en managed=False et mappent
# des tables EXISTANTES. Django ne doit jamais créer ni modifier de tables.
# -> Ne lancez PAS `makemigrations` ni `migrate` pour ce projet.
# ---------------------------------------------------------------------------
MIGRATION_MODULES = {"gestion": None}




