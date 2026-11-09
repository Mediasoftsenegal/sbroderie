"""
Authentification applicative reproduisant le comportement du PHP d'origine.

L'application PHP stockait les mots de passe EN CLAIR dans la table `user`
et comparait directement en SQL. Pour rester 100 % compatible avec la base
existante, on reproduit ce comportement (comparaison directe), tout en
supportant en plus les mots de passe hachés (préfixe reconnu par Django) si
vous décidez de les migrer plus tard.

La session Django conserve les mêmes clés que la session PHP :
  conn, nom, id_societe, societe, id_profil
"""
from functools import wraps
import unicodedata

from django.conf import settings
from django.contrib.auth.hashers import check_password, is_password_usable
from django.shortcuts import redirect

from .models import Profil, User

# Correspondance profil -> page d'accueil (comme le switch PHP de access.php)
PROFIL_HOME = {
    1: "dashboard",     # Administrateur
    2: "dashboard",     # Gérant
    3: "caisse",        # Caissier
    4: "finance",       # Comptable
    5: "marquage",      # Marquage
    6: "facturation",   # Invité (consultation des factures uniquement)
    7: "dashboard",     # Commercial
}

# Rôle canonique déduit du NOM du profil (robuste aux id auto-incrémentés).
# La clé est le nom mis en minuscules et sans accents.
ROLE_PAR_NOM = {
    "admin": 1, "administrateur": 1,
    "gerant": 2,
    "caisse": 3, "caissier": 3, "caissiere": 3,
    "comptable": 4, "comptabilite": 4, "finance": 4,
    "marquage": 5,
    "invite": 6, "guest": 6,
    "commercial": 7,
}


def _sans_accents(txt):
    txt = (txt or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", txt)
                   if unicodedata.category(c) != "Mn")


def role_canonique(user):
    """Retourne le rôle (1..7) à partir du NOM du profil de l'utilisateur.

    Ainsi « Invité » = 6 et « Commercial » = 7 même si leur id_profil en base
    n'est pas 6/7. Si le nom n'est pas reconnu, on retombe sur l'id_profil brut.
    """
    try:
        p = Profil.objects.filter(id_profil=user.id_profil).first()
        if p and p.nomprofil:
            role = ROLE_PAR_NOM.get(_sans_accents(p.nomprofil))
            if role:
                return role
    except Exception:
        pass
    try:
        return int(user.id_profil)
    except (TypeError, ValueError):
        return user.id_profil


def verifier_mot_de_passe(saisi, stocke):
    """Compare le mot de passe saisi au mot de passe stocké.

    - Si le stockage ressemble à un hash Django, on vérifie via check_password.
    - Sinon (cas historique en clair), on compare directement.
    """
    if stocke is None:
        return False
    try:
        if is_password_usable(stocke) and "$" in stocke:
            return check_password(saisi, stocke)
    except Exception:
        pass
    return saisi == stocke


def authentifier(login, password):
    """Retourne l'objet User si les identifiants sont valides, sinon None."""
    for u in User.objects.filter(login=login):
        if verifier_mot_de_passe(password, u.password):
            return u
    return None


def ouvrir_session(request, user):
    request.session["conn"] = "oui"
    request.session["nom"] = user.login
    request.session["id_user"] = user.id_user
    try:
        request.session["id_societe"] = int(user.id_societe)
    except (TypeError, ValueError):
        request.session["id_societe"] = user.id_societe
    # On stocke le rôle canonique (déduit du nom du profil) pour que les
    # contrôles d'accès fonctionnent quels que soient les id en base.
    request.session["id_profil"] = role_canonique(user)
    request.session["societe"] = "SD0" if request.session["id_societe"] == 1 else "SP0"


def est_connecte(request):
    return request.session.get("conn") == "oui"


def est_superuser(request):
    """Vrai si l'utilisateur connecté est le compte superuser dédié.

    Le superuser est identifié par son login (SUPERUSER_LOGIN dans les
    settings). C'est le seul autorisé à régulariser des factures.
    """
    login = getattr(settings, "SUPERUSER_LOGIN", "Mous")
    return est_connecte(request) and request.session.get("nom") == login


def login_requis(view):
    """Décorateur : exige une session ouverte, sinon redirige vers la connexion."""
    @wraps(view)
    def _wrap(request, *args, **kwargs):
        if not est_connecte(request):
            return redirect("index")
        return view(request, *args, **kwargs)
    return _wrap


def superuser_requis(view):
    """Décorateur : réserve la vue au compte superuser dédié.

    Un utilisateur connecté mais non superuser est renvoyé vers sa page
    d'accueil ; un visiteur non connecté vers la page de connexion.
    """
    @wraps(view)
    def _wrap(request, *args, **kwargs):
        if not est_connecte(request):
            return redirect("index")
        if not est_superuser(request):
            home = PROFIL_HOME.get(request.session.get("id_profil"), "index")
            return redirect(home)
        return view(request, *args, **kwargs)
    return _wrap


def profils_autorises(*profils):
    """Décorateur : restreint l'accès à certains profils (ids)."""
    def deco(view):
        @wraps(view)
        def _wrap(request, *args, **kwargs):
            if not est_connecte(request):
                return redirect("index")
            if profils and request.session.get("id_profil") not in profils:
                # Profil connecté mais non autorisé -> renvoi vers sa page d'accueil
                home = PROFIL_HOME.get(request.session.get("id_profil"), "index")
                return redirect(home)
            return view(request, *args, **kwargs)
        return _wrap
    return deco
