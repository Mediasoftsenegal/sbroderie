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

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
