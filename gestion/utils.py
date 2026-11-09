"""Fonctions utilitaires : formatage monétaire et conversion chiffres -> lettres."""


def format_fcfa(valeur):
    """Formate un nombre à la manière de number_format($v,0,'',' ') du PHP.

    Ex : 1250000 -> "1 250 000"
    """
    try:
        n = int(round(float(valeur or 0)))
    except (TypeError, ValueError):
        n = 0
    return f"{n:,}".replace(",", " ")


def chiffre_en_lettre(nombre):
    """Convertit un entier en toutes lettres (français), comme ChiffreEnLettre.php.

    Utilise la librairie num2words si disponible, sinon un repli minimal.
    """
    try:
        n = int(round(float(nombre or 0)))
    except (TypeError, ValueError):
        n = 0
    try:
        from num2words import num2words
        return num2words(n, lang="fr")
    except Exception:
        return _fallback_lettres(n)


_UNITES = [
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit",
    "neuf", "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
    "dix-sept", "dix-huit", "dix-neuf",
]
_DIZAINES = {
    20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
    60: "soixante", 70: "soixante", 80: "quatre-vingt", 90: "quatre-vingt",
}


def _deux_chiffres(n):
    if n < 20:
        return _UNITES[n]
    d, u = divmod(n, 10)
    if d in (7, 9):
        base = _DIZAINES[d * 10]
        return f"{base}-{_UNITES[10 + u]}"
    base = _DIZAINES[d * 10]
    if u == 0:
        return base + ("s" if d == 8 else "")
    if u == 1 and d != 8:
        return f"{base} et un"
    return f"{base}-{_UNITES[u]}"


def _trois_chiffres(n):
    c, reste = divmod(n, 100)
    parts = []
    if c == 1:
        parts.append("cent")
    elif c > 1:
        parts.append(f"{_UNITES[c]} cent" + ("s" if reste == 0 else ""))
    if reste:
        parts.append(_deux_chiffres(reste))
    return " ".join(parts)


def _fallback_lettres(n):
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + _fallback_lettres(-n)
    parts = []
    millions, reste = divmod(n, 1_000_000)
    if millions:
        m = _trois_chiffres(millions)
        parts.append(f"{m} million" + ("s" if millions > 1 else ""))
    milliers, reste2 = divmod(reste, 1000)
    if milliers:
        if milliers == 1:
            parts.append("mille")
        else:
            parts.append(f"{_trois_chiffres(milliers)} mille")
    if reste2:
        parts.append(_trois_chiffres(reste2))
    return " ".join(parts).strip()
