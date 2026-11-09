"""Expose les informations de session aux templates (comme $_SESSION en PHP)."""

from django.conf import settings


def utilisateur(request):
    s = request.session
    return {
        "session_nom": s.get("nom"),
        "session_profil": s.get("id_profil"),
        "session_societe": s.get("societe"),
        "session_id_societe": s.get("id_societe"),
        "est_connecte": s.get("conn") == "oui",
        "session_superuser": (
            s.get("conn") == "oui"
            and s.get("nom") == getattr(settings, "SUPERUSER_LOGIN", "Mous")
        ),
    }
