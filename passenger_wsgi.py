"""
Point d'entrée Passenger pour cPanel (Setup Python App).

cPanel/Passenger recherche la variable `application` dans ce fichier.
Le module de settings est fixé, puis l'application WSGI de Django est exposée.
"""
import os
import sys

# Dossier courant dans le chemin d'import
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sbroderie.settings")

# Secrets de production (ex. DB_PASSWORD) : fichier HORS du dossier web, sur le
# serveur uniquement, format CLE=valeur. Les variables déjà définies gardent la priorité.
ENV_FILE = os.path.expanduser("~/.sbroderie_env")
if os.path.isfile(ENV_FILE):
    with open(ENV_FILE, encoding="utf-8") as _f:
        for _ligne in _f:
            _ligne = _ligne.strip()
            if _ligne and not _ligne.startswith("#") and "=" in _ligne:
                _cle, _val = _ligne.split("=", 1)
                os.environ.setdefault(_cle.strip(), _val)

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
