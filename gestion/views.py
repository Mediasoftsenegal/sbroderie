"""
Vues Django reproduisant les fonctionnalités des pages PHP d'origine.

Conventions :
- Les requêtes simples utilisent l'ORM Django.
- Les requêtes d'agrégat complexes (SUM/GROUP BY) utilisent du SQL brut
  paramétré, comme le faisait le code PHP (mais en sécurisé).
- Le panier est stocké en session : request.session["panier"] = {codep: qty}.
"""
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import auth
from .auth import login_requis, profils_autorises, superuser_requis
from .models import (
    Client, Depense, DetailFacture, DetailFactureArchive, Factures,
    FacturesArchive, Marquage, Mesure, Modele, Produit, Profil, Tailleur,
    Tarification, User,
)
from .pdf import generer_facture_pdf
from .utils import format_fcfa


# ---------------------------------------------------------------------------
# Helpers SQL
# ---------------------------------------------------------------------------
def dictfetchall(cursor):
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def sql(query, params=None):
    with connection.cursor() as cur:
        cur.execute(query, params or [])
        if cur.description:
            return dictfetchall(cur)
        return []


# Champs de mesure (nom technique, libellé affiché)
CHAMPS_MESURE = [
    ("longueur", "Longueur"), ("longueurgrandboubou", "Longueur Grand Boubou"),
    ("epaule", "Épaule"), ("cou", "Cou"), ("manche", "Manche"),
    ("hanche", "Hanche"), ("tourbras", "Tour bras"), ("poignet", "Poignet"),
    ("longueurpantalon", "Longueur pantalon"), ("tourfess", "Tour fesses"),
    ("cuisse", "Cuisse"), ("bas", "Bas"), ("poitrine", "Poitrine"),
    ("tourmanche", "Tour manche"), ("ceinture", "Ceinture"),
]


# ===========================================================================
# AUTHENTIFICATION
# ===========================================================================
def index(request):
    if auth.est_connecte(request):
        return redirect(auth.PROFIL_HOME.get(request.session.get("id_profil"), "clients"))
    return render(request, "gestion/login.html")


def access(request):
    """Traite le formulaire de connexion (équivalent access.php)."""
    if request.method == "POST":
        login = request.POST.get("login", "")
        password = request.POST.get("password", "")
        user = auth.authentifier(login, password)
        if user:
            auth.ouvrir_session(request, user)
            role = request.session.get("id_profil")
            return redirect(auth.PROFIL_HOME.get(role, "clients"))
        return render(request, "gestion/login.html",
                      {"erreur": "Votre login ou mot de passe n'est pas valide !"})
    return redirect("index")


def deconnexion(request):
    request.session.flush()
    return redirect("index")


# ===========================================================================
# CLIENTS & MESURES
# ===========================================================================
@profils_autorises(1, 2, 7)
def clients(request):
    liste = list(Client.objects.all().order_by("-id_client"))
    nb_hommes = sum(1 for c in liste if (c.genre or "").lower().startswith("h"))
    nb_femmes = sum(1 for c in liste if (c.genre or "").lower().startswith("f"))
    avec_mesure = Mesure.objects.values_list("id_client", flat=True).distinct().count()
    return render(request, "gestion/clients/liste.html", {
        "clients": liste,
        "nb_total": len(liste),
        "nb_hommes": nb_hommes,
        "nb_femmes": nb_femmes,
        "avec_mesure": avec_mesure,
    })


@profils_autorises(1, 2, 7)
def client_insert(request):
    if request.method == "POST" and "bt_client" in request.POST:
        client = Client.objects.create(
            codecli=request.POST.get("codecli"),
            prenom_nom=request.POST.get("prenom_nom"),
            genre=request.POST.get("genre"),
            telephone=request.POST.get("telephone"),
            adresse=request.POST.get("adresse"),
            id_societe=request.POST.get("id_societe") or request.session.get("id_societe", 1),
        )
        return redirect("ajout_mesure", id_client=client.id_client)

    return redirect("clients")


@profils_autorises(1, 2, 7)
def client_modif(request, id_client):
    cli = Client.objects.filter(id_client=id_client).first()
    if request.method == "POST" and "bt_modif_client" in request.POST:
        cli.codecli = request.POST.get("codecli")
        cli.prenom_nom = request.POST.get("prenom_nom")
        cli.genre = request.POST.get("genre")
        cli.telephone = request.POST.get("telephone")
        cli.adresse = request.POST.get("adresse")
        cli.save()
        return redirect("clients")
    return render(request, "gestion/clients/modif.html", {"cli": cli})


@profils_autorises(1, 2, 7)
def client_supp(request, id_client):
    Client.objects.filter(id_client=id_client).delete()
    return redirect("clients")


@profils_autorises(1, 2, 7)
def mesures(request):
    rows = sql(
        "SELECT m.*, c.prenom_nom FROM mesure m "
        "INNER JOIN client c ON m.id_client = c.id_client ORDER BY m.id_mesure DESC"
    )
    return render(request, "gestion/clients/mesures.html", {"mesures": rows})


@profils_autorises(1, 2, 7)
def ajout_mesure(request, id_client=None):
    """Formulaire de saisie de mesure (nouveau client ou client existant)."""
    cli = None
    if id_client:
        cli = Client.objects.filter(id_client=id_client).first()
    else:
        # après insertion d'un client : dernier client créé
        cli = Client.objects.order_by("-id_client").first()
    return render(request, "gestion/clients/ajout_mesure.html",
                  {"cli": cli, "champs": [(n, lib) for n, lib in CHAMPS_MESURE]})


@profils_autorises(1, 2, 7)
def mesure_insert(request):
    if request.method == "POST" and ("bt_mesure" in request.POST or "bt_mesure_1" in request.POST):
        champs = [
            "genre", "telephone", "longueur", "longueurgrandboubou", "epaule",
            "cou", "manche", "longueurpantalon", "tourfess", "cuisse", "bas",
            "poitrine", "tourmanche", "ceinture", "hanche", "tourbras", "poignet",
        ]
        data = {c: request.POST.get(c) for c in champs}
        data["id_client"] = request.POST.get("id_client")
        data["id_societe"] = request.session.get("id_societe", 1)
        Mesure.objects.create(**data)
        return redirect("clients")
    return redirect("clients")


@profils_autorises(1, 2, 7)
def mesure_modif(request, id_mesure):
    mes = Mesure.objects.filter(id_mesure=id_mesure).first()
    if request.method == "POST" and "bt_modif_mesure" in request.POST:
        for c in ["longueur", "longueurgrandboubou", "epaule", "cou", "manche",
                  "longueurpantalon", "tourfess", "cuisse", "bas", "poitrine",
                  "tourmanche", "ceinture", "hanche", "tourbras", "poignet"]:
            setattr(mes, c, request.POST.get(c))
        mes.save()
        return redirect("mesures")
    champs = [(n, lib, getattr(mes, n, "") or "") for n, lib in CHAMPS_MESURE
              if n not in ("genre", "telephone")]
    return render(request, "gestion/clients/modif_mesure.html",
                  {"mes": mes, "champs": champs})


# ===========================================================================
# ARTICLES & MODELES
# ===========================================================================
def _modele_libelle(id_modele):
    m = Modele.objects.filter(codemod=id_modele).first()
    return m.libmod if m else ""


@profils_autorises(1, 2, 7)
def articles(request):
    liste = []
    for p in Produit.objects.all().order_by("-codep"):
        liste.append({"p": p, "libmod": _modele_libelle(p.id_modele)})
    modeles = Modele.objects.all().order_by("libmod")
    nb_pap = sum(1 for a in liste if (a["p"].catp or "").upper() == "PAP")
    nb_tissu = sum(1 for a in liste if (a["p"].catp or "").upper() == "TISSU")
    return render(request, "gestion/articles/liste.html",
                  {"articles": liste, "modeles": modeles,
                   "nb_total": len(liste), "nb_pap": nb_pap, "nb_tissu": nb_tissu,
                   "nb_modeles": modeles.count()})


@profils_autorises(1, 2, 7)
def article_insert(request):
    if request.method == "POST" and "bt_article" in request.POST:
        Produit.objects.create(
            des=request.POST.get("des"),
            pu=request.POST.get("pu") or 0,
            catp=request.POST.get("catp"),
            id_modele=request.POST.get("libmod") or request.POST.get("modele") or None,
            genre=request.POST.get("genre"),
            couleur=request.POST.get("couleur"),
        )
        return redirect("articles")
    return redirect("articles")


@profils_autorises(1, 2, 7)
def article_modif(request, codep):
    prod = Produit.objects.filter(codep=codep).first()
    if request.method == "POST" and ("bt_update_article" in request.POST or "bt_update_articles" in request.POST):
        prod.des = request.POST.get("des")
        prod.pu = request.POST.get("pu") or 0
        prod.catp = request.POST.get("catp")
        prod.id_modele = request.POST.get("modele") or None
        prod.genre = request.POST.get("genre")
        prod.couleur = request.POST.get("couleur")
        prod.save()
        return redirect("articles")
    modeles = Modele.objects.all().order_by("libmod")
    return render(request, "gestion/articles/modif.html", {"prod": prod, "modeles": modeles})


@profils_autorises(1, 2, 7)
def article_supp(request, codep):
    Produit.objects.filter(codep=codep).delete()
    return redirect("articles")


@profils_autorises(1, 2, 7)
def modeles(request):
    liste = Modele.objects.all().order_by("-codemod")
    return render(request, "gestion/articles/modeles.html", {"modeles": liste})


@profils_autorises(1, 2, 7)
def modele_insert(request):
    if request.method == "POST" and "bt_modele" in request.POST:
        Modele.objects.create(libmod=request.POST.get("libmod"))
        return redirect("modeles")
    return redirect("modeles")


# ===========================================================================
# PANIER (4 étapes)  ->  FACTURATION
# ===========================================================================
def _panier(request):
    return request.session.setdefault("panier", {})


def _sauver_panier(request, panier):
    request.session["panier"] = panier
    request.session.modified = True


@profils_autorises(1, 2, 7)
def panier_client(request):
    """Étape 1 : choisir le client + génération du numéro de facture."""
    request.session["panier"] = {}
    derniere = Factures.objects.order_by("-cmpt").first()
    cmpt = (derniere.cmpt or 0) + 1 if derniere else 1
    request.session["cmpt"] = cmpt
    request.session["num_fact"] = f"{request.session.get('societe', 'SD0')}{cmpt}"
    liste = Client.objects.all().order_by("-id_client")
    return render(request, "gestion/panier/client.html",
                  {"clients": liste, "num_fact": request.session["num_fact"]})


@profils_autorises(1, 2, 7)
def panier_produit(request, id_client):
    """Étape 2 : lister les produits à ajouter."""
    cli = Client.objects.filter(id_client=id_client).first()
    panier = _panier(request)
    liste = []
    for p in Produit.objects.all():
        liste.append({"p": p, "libmod": _modele_libelle(p.id_modele)})
    return render(request, "gestion/panier/produit.html", {
        "cli": cli, "produits": liste,
        "count": sum(panier.values()),
        "num_fact": request.session.get("num_fact"),
        "cmpt": request.session.get("cmpt"),
    })


@profils_autorises(1, 2, 7)
def panier_add(request, id_client, codep):
    panier = _panier(request)
    codep = str(codep)
    panier[codep] = panier.get(codep, 0) + 1
    _sauver_panier(request, panier)
    return redirect("panier_produit", id_client=id_client)


@profils_autorises(1, 2, 7)
def panier_del(request, id_client, codep):
    panier = _panier(request)
    panier.pop(str(codep), None)
    _sauver_panier(request, panier)
    return redirect("panier_voir", id_client=id_client)


@profils_autorises(1, 2, 7)
def panier_voir(request, id_client):
    """Étape 3 : consulter le panier."""
    panier = _panier(request)
    lignes = []
    total = 0
    for codep, qty in panier.items():
        p = Produit.objects.filter(codep=codep).first()
        if not p:
            continue
        libmod = _modele_libelle(p.id_modele)
        sous_total = (p.pu or 0) * qty
        total += sous_total
        lignes.append({
            "codep": p.codep,
            "des": f"{p.des}->{libmod}->{p.catp}",
            "pu": p.pu, "qty": qty, "subtot": sous_total,
        })
    return render(request, "gestion/panier/voir.html", {
        "lignes": lignes, "total": total,
        "totqty": sum(panier.values()),
        "id_client": id_client,
        "id_article": ",".join(panier.keys()),
    })


@profils_autorises(1, 2, 7)
def facture_info(request):
    """Étape 4 : récapitulatif avant validation (form GET issu du panier)."""
    id_client = request.GET.get("id_client")
    cli = Client.objects.filter(id_client=id_client).first()
    mes = Mesure.objects.filter(id_client=id_client).first()
    des = request.GET.getlist("des[]") or request.GET.getlist("des")
    prices = request.GET.getlist("price[]") or request.GET.getlist("price")
    qtys = request.GET.getlist("qty[]") or request.GET.getlist("qty")
    subtots = request.GET.getlist("subtot[]") or request.GET.getlist("subtot")
    lignes = []
    for i in range(len(des)):
        lignes.append({
            "des": des[i],
            "price": prices[i] if i < len(prices) else "",
            "qty": qtys[i] if i < len(qtys) else "",
            "subtot": subtots[i] if i < len(subtots) else "",
        })
    datefact = date.today()
    echeance = datefact + timedelta(days=21)
    return render(request, "gestion/panier/facture_info.html", {
        "cli": cli, "mes": mes, "lignes": lignes,
        "totqty": request.GET.get("totqty"),
        "total": request.GET.get("total"),
        "id_article": request.GET.get("id_article"),
        "id_client": id_client,
        "num_fact": request.session.get("num_fact"),
        "cmpt": request.session.get("cmpt"),
        "datefact": datefact.isoformat(),
        "echeance": echeance.isoformat(),
    })


@profils_autorises(1, 2, 7)
def facture_creer(request):
    """Crée la facture : factures + detail_facture + marquage (équivalent facture.php)."""
    g = request.GET
    id_client = g.get("id_client")
    total = float(g.get("total") or 0)
    montpaye = float(g.get("montpaye") or 0)
    remise = float(g.get("remise") or 0)
    remise = max(0, min(remise, total))
    net = total - remise
    etat = 1 if (net - montpaye) <= 0 else 0

    facture = Factures.objects.create(
        id_client=id_client,
        date_facture=date.today(),
        id_societe=1,
        numero_facture=g.get("numero_facture"),
        montant_facture=total,
        remise=remise,
        montpaye=montpaye,
        etat_facture=etat,
        heure_facture=datetime.now().strftime("%H:%M"),
        date_echeance=g.get("date_echeance") or None,
        cmpt=request.session.get("cmpt"),
    )

    des = g.getlist("des[]") or g.getlist("des")
    prices = g.getlist("price[]") or g.getlist("price")
    qtys = g.getlist("qty[]") or g.getlist("qty")
    id_articles = g.get("id_article") or g.get("id_articles") or ""

    DetailFacture.objects.create(
        id_facture=facture.id_facture,
        id_client=id_client,
        article=",".join(des),
        prix_unitaire=",".join(prices),
        nombre=",".join(qtys),
        montant=total,
        id_societe=1,
        id_article=id_articles,
    )

    # La table marquage a plusieurs colonnes NOT NULL sans valeur par défaut
    # (etat, id_*, date_*). En mode SQL strict, il faut toutes les renseigner.
    aujourdhui = date.today()
    for art in [a for a in id_articles.split(",") if a]:
        Marquage.objects.create(
            id_article=art,
            numero_facture=g.get("numero_facture"),
            id_couture=0, date_couture=aujourdhui,
            id_brodeur=0, date_broderie=aujourdhui,
            id_bouton=0, date_bouton=aujourdhui,
            etat=0,
        )

    request.session["panier"] = {}
    return redirect("facture_details", id_facture=facture.id_facture)


@profils_autorises(1, 2, 3, 4, 6, 7)
def facture_details(request, id_facture):
    rows = sql(
        "SELECT df.*, c.prenom_nom, c.telephone, c.codecli, f.numero_facture, "
        "f.date_facture, f.montant_facture, f.remise, f.montpaye, f.date_echeance "
        "FROM detail_facture df "
        "INNER JOIN client c ON df.id_client = c.id_client "
        "INNER JOIN factures f ON df.id_facture = f.id_facture "
        "WHERE df.id_facture = %s", [id_facture])
    detail = rows[0] if rows else None
    wa_possible = bool(detail) and normaliser_numero_wa(detail.get("telephone")) is not None
    return render(request, "gestion/facture/details.html",
                  {"detail": detail, "id_facture": id_facture, "wa_possible": wa_possible})


@profils_autorises(1, 2, 3, 4, 6, 7)
def facture_pdf(request, id_facture):
    contenu = generer_facture_pdf(id_facture)
    if not contenu:
        return HttpResponse("Facture introuvable", status=404)
    resp = HttpResponse(contenu, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="facture_{id_facture}.pdf"'
    return resp


@profils_autorises(1, 2, 3, 4, 6, 7)
def facture_pdf_sans_mesures(request, id_facture):
    """PDF de la facture à remettre au client : bons de confection sans grille de mesures."""
    contenu = generer_facture_pdf(id_facture, avec_mesures=False)
    if not contenu:
        return HttpResponse("Facture introuvable", status=404)
    resp = HttpResponse(contenu, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="facture_{id_facture}_sans_mesures.pdf"'
    return resp


def normaliser_numero_wa(telephone):
    """Numéro sénégalais -> forme internationale sans '+' ni espaces (ex. 221771234567).

    Accepte '77 123 45 67', '+221 77 123 45 67', '00221771234567'.
    Retourne None si le numéro n'est pas exploitable (mobile 7x ou fixe 3x).
    """
    chiffres = re.sub(r"\D", "", telephone or "")
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    if len(chiffres) == 9:
        chiffres = "221" + chiffres
    if len(chiffres) == 12 and chiffres.startswith("221") and chiffres[3] in "37":
        return chiffres
    return None


@profils_autorises(1, 2, 3, 4, 6, 7)
def facture_whatsapp(request, id_facture):
    """Ouvre WhatsApp (wa.me) avec un message pré-rempli : numéro, total, reste à payer.

    Aucun fichier joint (limite de wa.me) : l'utilisateur joint le PDF téléchargé.
    Aucune donnée de mesure dans le message.
    """
    facture = Factures.objects.filter(id_facture=id_facture).first()
    if not facture or not facture.numero_facture:
        return HttpResponse("Facture introuvable", status=404)
    # Même agrégation que la liste : montant total et encaissements cumulés.
    rows = _resume_factures("numero_facture = %s", [facture.numero_facture])
    if not rows:
        return HttpResponse("Facture introuvable", status=404)
    r = rows[0]
    numero_wa = normaliser_numero_wa(r.get("telephone"))
    if not numero_wa:
        messages.error(request, "Ce client n'a pas de numéro de téléphone valide : envoi WhatsApp impossible.")
        return redirect("facture_details", id_facture=id_facture)
    texte = (
        f"Bonjour {r.get('prenom_nom') or ''}, veuillez trouver ci-joint votre facture "
        f"N° {facture.numero_facture} ({settings.SOCIETE['nom']}). "
        f"Montant : {format_fcfa(r['montant_facture'])} F CFA. "
        f"Reste à payer : {format_fcfa(max(r['reliquat'], 0))} F CFA. Merci de votre confiance."
    )
    url = "https://wa.me/" + numero_wa + "?" + urlencode({"text": texte}, quote_via=quote)
    return redirect(url)


# ===========================================================================
# FACTURATION (listes / suivis)
# ===========================================================================
def _resume_factures(cond_sql="", params=None, order="ORDER BY f.id_facture DESC"):
    """Retourne UNE ligne par numéro de facture (compatible ONLY_FULL_GROUP_BY).

    Une facture (numero_facture) peut apparaître sur plusieurs lignes :
      - des acomptes (montant_facture = 0, montpaye = versement), ou
      - des instantanés répétant le même montant_facture avec un montpaye
        cumulé croissant (0, 40000, 90000, ...).

    Le montant facturé ne se somme donc PAS. On retient :
      - montant_total = plus grand montant_facture (le montant de la facture),
      - cumul_paye    = somme des montpaye des lignes d'acompte
                        + le plus grand montpaye des lignes portant le montant.
    On prend la ligne d'origine (MIN(id_facture)) comme représentante.
    Chaque ligne reçoit aussi montpaye (=cumul) et reliquat, pour les gabarits.
    """
    params = list(params or [])
    where = ("WHERE " + cond_sql + " ") if cond_sql else ""
    rows = sql(
        "SELECT f.*, c.prenom_nom, c.telephone, "
        "g.cumul_paye AS cumul_paye, g.montant_total AS montant_total "
        "FROM factures f "
        "JOIN (SELECT numero_facture, MIN(id_facture) AS rid, "
        "             SUM(CASE WHEN COALESCE(montant_facture,0)=0 "
        "                      THEN montpaye ELSE 0 END) "
        "             + MAX(CASE WHEN COALESCE(montant_facture,0)>0 "
        "                        THEN montpaye ELSE 0 END) AS cumul_paye, "
        "             MAX(COALESCE(montant_facture,0)) AS montant_total "
        "      FROM factures " + where + "GROUP BY numero_facture) g "
        "  ON f.id_facture = g.rid "
        "JOIN client c ON f.id_client = c.id_client " + order,
        params)
    for r in rows:
        cumul = _num(r.get("cumul_paye"))
        total = r.get("montant_total")
        if total is None:
            total = r.get("montant_facture")
        total = _num(total)
        remise = _num(r.get("remise"))
        r["montant_facture"] = total
        r["remise"] = remise
        r["cumul_paye"] = cumul
        r["montpaye"] = cumul
        # Reliquat = montant facturé - encaissé - remise.
        r["reliquat"] = total - cumul - remise
    return rows


@profils_autorises(1, 2, 3, 4, 6, 7)
def facturation(request):
    rows = _resume_factures("etat_facture < 2")
    # Filtre sur l'année sélectionnée (année en cours par défaut).
    annee, annees = _contexte_annee(request)
    rows = _filtrer_par_annee(rows, annee)
    # Contrôle d'équilibre : équilibrée si reliquat = 0
    # (montant facturé = montant encaissé + remise), sinon fond orange.
    for r in rows:
        r["equilibre"] = abs(_num(r.get("reliquat"))) < 0.5
    total_facture = sum(_num(f.get("montant_facture")) for f in rows)
    total_encaisse = sum(_num(f.get("cumul_paye")) for f in rows)
    total_remise = sum(_num(f.get("remise")) for f in rows)
    nb_payees = sum(1 for f in rows if (f.get("etat_facture") or 0) == 1)
    nb_impayees = sum(1 for f in rows if (f.get("etat_facture") or 0) != 1)
    return render(request, "gestion/facture/facturation.html", {
        "factures": rows,
        "nb_total": len(rows),
        "annee": annee,
        "annees": annees,
        "total_facture": total_facture,
        "total_encaisse": total_encaisse,
        "total_remise": total_remise,
        "reliquat": total_facture - total_encaisse - total_remise,
        "nb_payees": nb_payees,
        "nb_impayees": nb_impayees,
    })


def _annee_filtre(request):
    """Année sélectionnée (GET/POST 'annee'), l'année en cours par défaut."""
    val = (request.GET.get("annee") or request.POST.get("annee") or "").strip()
    try:
        return int(val)
    except (TypeError, ValueError):
        return date.today().year


def _filtrer_par_annee(rows, annee):
    """Ne conserve que les lignes dont date_facture appartient à `annee`."""
    return [r for r in rows
            if (_asdate(r.get("date_facture")) or date(1900, 1, 1)).year == annee]


def _contexte_annee(request):
    """Retourne (annee_selectionnee, liste_des_annees) pour le sélecteur.

    L'année sélectionnée est toujours présente dans la liste, même sans
    facture pour cette année.
    """
    annee = _annee_filtre(request)
    annees = _annees_factures()
    if annee not in annees:
        annees = sorted(set(annees) | {annee}, reverse=True)
    return annee, annees


def _kpi_factures(rows):
    """Totaux à partir de lignes issues de _resume_factures."""
    facture = sum(_num(r.get("montant_facture")) for r in rows)
    encaisse = sum(_num(r.get("cumul_paye")) for r in rows)
    remise = sum(_num(r.get("remise")) for r in rows)
    payees = sum(1 for r in rows if (r.get("etat_facture") or 0) == 1)
    return {
        "nb": len(rows), "facture": facture, "encaisse": encaisse,
        "remise": remise, "reste": facture - encaisse - remise, "payees": payees,
        "encours": len(rows) - payees,
    }


@profils_autorises(1, 2, 4)
def indicateur(request):
    rows = _resume_factures("etat_facture = 0")
    annee, annees = _contexte_annee(request)
    rows = _filtrer_par_annee(rows, annee)
    # Reliquat = montant - encaissé - remise ; signalement si déséquilibre.
    for r in rows:
        r["equilibre"] = abs(_num(r.get("reliquat"))) < 0.5
    return render(request, "gestion/facture/indicateur.html",
                  {"factures": rows, "kpi": _kpi_factures(rows),
                   "annee": annee, "annees": annees})


@profils_autorises(1, 2, 4)
def etat(request):
    rows = _resume_factures()
    annee, annees = _contexte_annee(request)
    rows = _filtrer_par_annee(rows, annee)
    return render(request, "gestion/facture/etat.html",
                  {"factures": rows, "kpi": _kpi_factures(rows),
                   "annee": annee, "annees": annees})


@profils_autorises(1, 2, 4)
def modif_etat(request, numero_facture):
    rows = sql(
        "SELECT f.*, c.prenom_nom, c.telephone FROM factures f "
        "INNER JOIN client c ON f.id_client = c.id_client "
        "WHERE f.numero_facture = %s", [numero_facture])
    fact = rows[0] if rows else None
    _lignes, _inv, paye, _rel, _idc = _synthese_facture(numero_facture)
    return render(request, "gestion/facture/modif_etat.html",
                  {"fact": fact, "cumul_paye": paye})


# ===========================================================================
# RÉGULARISATION DES FACTURES NON SOLDÉES (superuser uniquement)
# ===========================================================================
@superuser_requis
def regularisation(request):
    """Recherche d'une facture par numéro et régularisation (solde).

    Réservée au compte superuser dédié. Permet d'équilibrer les comptes en
    soldant une facture non soldée (le montant encaissé est aligné sur le
    montant facturé et l'état passe à « Payée »).
    """
    numero = (request.POST.get("numero_facture")
              or request.GET.get("numero_facture") or "").strip()
    fact = None
    introuvable = False
    deja_soldee = False

    lignes = []
    details = []
    if numero:
        lignes, invoice, cumul, reliquat, id_client = _synthese_facture(numero)
        if not lignes:
            introuvable = True
        else:
            cli = sql("SELECT prenom_nom, telephone FROM client WHERE id_client = %s",
                      [id_client])
            info = cli[0] if cli else {}
            fact = {
                "numero_facture": numero,
                "prenom_nom": info.get("prenom_nom"),
                "telephone": info.get("telephone"),
                "montant_total": invoice,
                "cumul_paye": cumul,
                "reliquat": reliquat,
                # État courant = celui de la ligne d'origine (0=En cours,
                # 1=Payée, 2=Annulé).
                "etat_facture": int(lignes[0].get("etat_facture") or 0),
            }
            deja_soldee = reliquat <= 0.5
            # Détails de la facture (lignes d'articles) pour affichage avant
            # suppression éventuelle.
            details = sql(
                "SELECT d.* FROM detail_facture d "
                "JOIN factures f ON d.id_facture = f.id_facture "
                "WHERE f.numero_facture = %s ORDER BY d.id_detail", [numero])

    # --- Onglet « Vérification des montants » (filtrable par année) ----------
    annee = (request.GET.get("annee") or "").strip()
    verif = _verif_montants(annee or None)
    nb_ecarts = sum(1 for v in verif if not v["ok"])

    mois_groups = []
    page_obj = None
    if annee:
        # Année choisie : TOUS les mois (Décembre -> Janvier), même vides,
        # repliés. Pas de pagination.
        an = int(annee)
        for m in range(12, 0, -1):
            facs = sorted((v for v in verif if v["_mois"] == m),
                          key=lambda r: (r["ok"], r["numero_facture"]))
            mois_groups.append({
                "label": f"{MOIS_FR_LONG[m - 1]} {an}",
                "factures": facs,
                "nb": len(facs),
                "ecarts": sum(1 for f in facs if not f["ok"]),
            })
    else:
        # Toutes les années : pagination + regroupement par mois de la page.
        paginator = Paginator(verif, 25)
        page_obj = paginator.get_page(request.GET.get("page"))
        courant = None
        for r in page_obj:
            if courant is None or courant["label"] != r["mois_label"]:
                courant = {"label": r["mois_label"], "factures": [],
                           "nb": 0, "ecarts": 0}
                mois_groups.append(courant)
            courant["factures"].append(r)
            courant["nb"] += 1
            if not r["ok"]:
                courant["ecarts"] += 1

    # --- Onglet « Archivage » (superuser) ------------------------------------
    tab = request.GET.get("tab", "")
    try:
        annee_arch = int(request.GET.get("annee_arch") or date.today().year)
    except (TypeError, ValueError):
        annee_arch = date.today().year
    # Aperçu (nombre de factures soldées archivables) calculé seulement quand
    # l'onglet Archivage est ouvert, car c'est une opération plus lourde.
    arch_nb = len(_numeros_soldes_annee(annee_arch)) if tab == "arch" else None

    return render(request, "gestion/facture/regularisation.html", {
        "numero_facture": numero,
        "fact": fact,
        "lignes": lignes,
        "details": details,
        "introuvable": introuvable,
        "deja_soldee": deja_soldee,
        "mois_groups": mois_groups,
        "page_obj": page_obj,
        "nb_verif": len(verif),
        "nb_ecarts": nb_ecarts,
        "annees": _annees_factures(),
        "annee": annee,
        "tab": tab,
        "annee_arch": annee_arch,
        "arch_nb": arch_nb,
        "archives": _archives_par_annee(),
    })


def _synthese_facture(numero):
    """Synthèse d'un numéro de facture payé éventuellement en plusieurs fois.

    Le montant facturé ne se somme PAS : une facture peut apparaître sur
    plusieurs lignes (acomptes, ou instantanés répétant le même montant).
    On retient donc :
      - montant facturé  = plus grand montant_facture (le montant de la facture),
      - cumul encaissé   = somme des montpaye des lignes d'acompte
                           (montant_facture = 0) + le plus grand montpaye des
                           lignes portant le montant (cas des cumuls successifs).

    Retourne (lignes, montant_facture, cumul_encaisse, reliquat, id_client).
    """
    lignes = sql(
        "SELECT id_facture, id_client, date_facture, heure_facture, "
        "       montant_facture, montpaye, etat_facture "
        "FROM factures WHERE numero_facture = %s ORDER BY id_facture",
        [numero])
    invoice = 0.0
    cumul_acomptes = 0.0     # lignes d'acompte (montant_facture = 0)
    cumul_snapshots = 0.0    # lignes portant le montant (on garde le max)
    id_client = None
    for l in lignes:
        mf = _num(l.get("montant_facture"))
        mp = _num(l.get("montpaye"))
        l["montant_facture"] = mf
        l["montpaye"] = mp
        if id_client is None:
            id_client = l.get("id_client")
        if mf > 0:
            invoice = max(invoice, mf)
            cumul_snapshots = max(cumul_snapshots, mp)
        else:
            cumul_acomptes += mp
    cumul = cumul_acomptes + cumul_snapshots
    return lignes, invoice, cumul, invoice - cumul, id_client


def _annees_factures():
    """Liste des années présentes dans les factures (plus récente d'abord).

    L'extraction se fait côté Python (via _asdate) pour être robuste quel que
    soit le type/format de date_facture et le sql_mode MySQL (les fonctions
    SQL comme YEAR() et la comparaison à '0000-00-00' pouvant se comporter
    différemment selon la configuration du serveur).
    """
    rows = sql("SELECT DISTINCT date_facture FROM factures "
               "WHERE date_facture IS NOT NULL")
    annees = set()
    for r in rows:
        d = _asdate(r.get("date_facture"))
        if d and d.year > 1900:
            annees.add(d.year)
    return sorted(annees, reverse=True)


def _verif_montants(annee=None):
    """Compare, pour chaque facture, le montant global de la facture avec la
    somme des montants de ses détails.

    Si `annee` est fournie, ne garde que les factures de cette année, sinon
    toutes les années. Les écarts sont placés en tête de liste.
    """
    rows = sql(
        "SELECT f.id_facture, f.numero_facture, f.date_facture, "
        "       f.montant_facture, c.prenom_nom, "
        "       COALESCE(d.total_details, 0) AS total_details "
        "FROM factures f "
        "JOIN client c ON f.id_client = c.id_client "
        "LEFT JOIN (SELECT id_facture, SUM(montant) AS total_details "
        "           FROM detail_facture GROUP BY id_facture) d "
        "  ON d.id_facture = f.id_facture "
        "WHERE f.montant_facture > 0 "
        "ORDER BY f.numero_facture")
    annee = int(annee) if annee else None
    resultat = []
    for r in rows:
        # Année / mois pour le regroupement décroissant (filtrage côté Python).
        d = _asdate(r.get("date_facture"))
        r["_annee"] = d.year if d else 0
        r["_mois"] = d.month if d else 0
        if annee and r["_annee"] != annee:
            continue
        mf = _num(r.get("montant_facture"))
        td = _num(r.get("total_details"))
        r["montant_facture"] = mf
        r["total_details"] = td
        r["ecart"] = mf - td
        r["ok"] = abs(r["ecart"]) < 0.5
        r["mois_label"] = (f"{MOIS_FR_LONG[d.month - 1]} {d.year}" if d else "Sans date")
        resultat.append(r)
    rows = resultat
    # Tri : mois décroissant (Décembre -> Janvier), puis écarts en tête du mois,
    # puis par numéro de facture.
    rows.sort(key=lambda r: (-r["_annee"], -r["_mois"], r["ok"], r["numero_facture"]))
    return rows


@superuser_requis
def regularisation_corriger(request):
    """Aligne le montant d'une facture sur la somme de ses détails."""
    if request.method != "POST":
        return redirect(f"{reverse('regularisation')}?tab=verif")

    id_facture = request.POST.get("id_facture")
    annee = (request.POST.get("annee") or "").strip()
    if id_facture:
        agg = sql("SELECT SUM(montant) AS total FROM detail_facture "
                  "WHERE id_facture = %s", [id_facture])
        total = _num(agg[0].get("total")) if agg else 0
        Factures.objects.filter(id_facture=id_facture).update(montant_facture=total)
    suffixe = f"&annee={annee}" if annee else ""
    return redirect(f"{reverse('regularisation')}?tab=verif&corr=1{suffixe}")


@superuser_requis
def regularisation_supprimer(request):
    """Supprime définitivement une facture ET ses détails (superuser)."""
    if request.method != "POST":
        return redirect("regularisation")
    numero = (request.POST.get("numero_facture") or "").strip()
    if numero:
        ids = [r["id_facture"] for r in
               sql("SELECT id_facture FROM factures WHERE numero_facture = %s", [numero])]
        if ids:
            DetailFacture.objects.filter(id_facture__in=ids).delete()
        Factures.objects.filter(numero_facture=numero).delete()
    return redirect(f"{reverse('regularisation')}?supprime={numero}")


@superuser_requis
def regularisation_etat(request):
    """Change l'état d'une facture (0=En cours, 1=Payée, 2=Annulé)."""
    if request.method != "POST":
        return redirect("regularisation")
    numero = (request.POST.get("numero_facture") or "").strip()
    try:
        etat = int(request.POST.get("etat"))
    except (TypeError, ValueError):
        etat = None
    if numero and etat in (0, 1, 2):
        Factures.objects.filter(numero_facture=numero).update(etat_facture=etat)
    return redirect(f"{reverse('regularisation')}?numero_facture={numero}&etatok=1")


# ---------------------------------------------------------------------------
# ARCHIVAGE des factures soldées (superuser)
# ---------------------------------------------------------------------------
def _chunks(seq, taille):
    for i in range(0, len(seq), taille):
        yield seq[i:i + taille]


def _numeros_soldes_annee(annee):
    """Numéros de facture soldés (reliquat <= 0) dont la facture d'origine
    est datée de l'année `annee`."""
    rows = _filtrer_par_annee(_resume_factures(), annee)
    return [r["numero_facture"] for r in rows if _num(r.get("reliquat")) <= 0.5]


def _archives_par_annee():
    """Récapitulatif des factures déjà archivées, par année (ou [] si la table
    d'archive n'existe pas encore)."""
    try:
        return sql("SELECT annee_archive AS an, COUNT(*) AS nb, "
                   "       SUM(montant_facture) AS montant "
                   "FROM factures_archive GROUP BY annee_archive "
                   "ORDER BY an DESC")
    except Exception:
        return []


@superuser_requis
def regularisation_archiver(request):
    """Déplace les factures soldées d'une année vers les tables d'archive."""
    if request.method != "POST":
        return redirect(f"{reverse('regularisation')}?tab=arch")
    try:
        annee = int(request.POST.get("annee_arch"))
    except (TypeError, ValueError):
        return redirect(f"{reverse('regularisation')}?tab=arch")

    numeros = _numeros_soldes_annee(annee)
    today = date.today().isoformat()
    n = 0
    try:
        with transaction.atomic():
            for lot in _chunks(numeros, 300):
                ph = ",".join(["%s"] * len(lot))
                ids = [r["id_facture"] for r in
                       sql(f"SELECT id_facture FROM factures WHERE numero_facture IN ({ph})", lot)]
                sql(
                    "INSERT INTO factures_archive (id_facture,id_client,date_facture,"
                    "id_societe,numero_facture,montant_facture,montpaye,etat_facture,"
                    "heure_facture,date_echeance,cmpt,remise,payepar,commentaire,"
                    "date_archivage,annee_archive) "
                    "SELECT id_facture,id_client,date_facture,id_societe,numero_facture,"
                    "montant_facture,montpaye,etat_facture,heure_facture,date_echeance,"
                    "cmpt,remise,payepar,commentaire,%s,%s "
                    f"FROM factures WHERE numero_facture IN ({ph})",
                    [today, annee] + lot)
                if ids:
                    ph2 = ",".join(["%s"] * len(ids))
                    sql(
                        "INSERT INTO detail_facture_archive (id_detail,id_facture,"
                        "id_client,article,prix_unitaire,nombre,montant,id_societe,"
                        "id_article,date_archivage,annee_archive) "
                        "SELECT id_detail,id_facture,id_client,article,prix_unitaire,"
                        "nombre,montant,id_societe,id_article,%s,%s "
                        f"FROM detail_facture WHERE id_facture IN ({ph2})",
                        [today, annee] + ids)
                    sql(f"DELETE FROM detail_facture WHERE id_facture IN ({ph2})", ids)
                sql(f"DELETE FROM factures WHERE numero_facture IN ({ph})", lot)
                n += len(lot)
    except Exception:
        # Table d'archive absente ou erreur SQL : rien n'est supprimé (rollback).
        return redirect(f"{reverse('regularisation')}?tab=arch&archerr=1")

    return redirect(f"{reverse('regularisation')}?tab=arch&archive={n}&an={annee}")


@superuser_requis
def regularisation_archives(request):
    """Consultation des factures archivées (filtrable par année)."""
    annee = (request.GET.get("annee") or "").strip()
    try:
        qs = FacturesArchive.objects.all().order_by("-date_facture")
        if annee:
            qs = qs.filter(annee_archive=annee)
        factures = list(qs[:2000])
        annees = sorted({a for a in FacturesArchive.objects
                         .values_list("annee_archive", flat=True) if a}, reverse=True)
    except Exception:
        factures, annees = [], []
    total = sum(_num(f.montant_facture) for f in factures)
    encaisse = sum(_num(f.montpaye) for f in factures)
    return render(request, "gestion/facture/archives.html", {
        "factures": factures, "annees": annees, "annee": annee,
        "total": total, "encaisse": encaisse, "nb": len(factures),
    })


@superuser_requis
def regularisation_valider(request):
    """Solde une facture non soldée pour équilibrer les comptes.

    Ajoute une ligne de régularisation dont le montant encaissé couvre le
    reliquat (traçabilité de l'ajustement), puis passe toutes les lignes du
    numéro de facture à l'état « Payée » (etat_facture = 1).
    """
    if request.method != "POST":
        return redirect("regularisation")

    numero = (request.POST.get("numero_facture") or "").strip()
    if not numero:
        return redirect("regularisation")

    lignes, invoice, cumul, reliquat, id_client = _synthese_facture(numero)
    if not lignes:
        return redirect(f"{reverse('regularisation')}?numero_facture={numero}")

    if reliquat > 0:
        # Ligne de régularisation : trace l'ajustement comme un encaissement
        # (montant_facture = 0, montpaye = reliquat) -> Σ encaissé = Σ facturé.
        Factures.objects.create(
            id_client=id_client,
            date_facture=date.today(),
            id_societe=1,
            numero_facture=numero,
            montant_facture=0,
            montpaye=reliquat,
            etat_facture=1,
            heure_facture=datetime.now().strftime("%H:%M:%S"),
            date_echeance=date.today(),
        )

    # Toutes les lignes du numéro passent à l'état « Payée ».
    Factures.objects.filter(numero_facture=numero).update(etat_facture=1)

    return redirect(f"{reverse('regularisation')}?numero_facture={numero}&ok=1")


@profils_autorises(1, 2, 4)
def rvsemaine(request):
    rows = []
    debut = request.POST.get("datedeb") or request.GET.get("datedeb")
    fin = request.POST.get("datefin") or request.GET.get("datefin")
    if debut and fin:
        rows = _resume_factures(
            "date_echeance BETWEEN %s AND %s", [debut, fin],
            order="ORDER BY f.date_echeance ASC")
    return render(request, "gestion/facture/rvsemaine.html",
                  {"factures": rows, "datedeb": debut, "datefin": fin})


@profils_autorises(1, 2, 4)
def mensuel(request):
    rows = _resume_factures(order="ORDER BY f.numero_facture DESC")
    # L'état mensuel porte sur l'année sélectionnée (année en cours par défaut).
    annee, annees = _contexte_annee(request)
    rows = _filtrer_par_annee(rows, annee)
    # Même contrôle qu'en facturation : équilibrée si reliquat = 0
    # (montant = encaissé + remise), sinon signalée en orange.
    for r in rows:
        r["equilibre"] = abs(_num(r.get("reliquat"))) < 0.5
    kpi = _kpi_factures(rows)
    # Totaux cohérents avec l'agrégation par numéro (pas de somme brute des
    # lignes, qui double-compterait les factures payées en plusieurs fois).
    total = {"montfact": kpi["facture"], "montpaye": kpi["encaisse"],
             "remise": kpi["remise"], "reste": kpi["reste"]}
    return render(request, "gestion/facture/mensuel.html",
                  {"factures": rows, "total": total, "kpi": kpi,
                   "annee_courante": annee, "annee": annee, "annees": annees})


# ===========================================================================
# CAISSE
# ===========================================================================
@profils_autorises(1, 3, 7)
def caisse(request):
    today = date.today().isoformat()
    lignes = sql("SELECT * FROM factures WHERE date_facture = %s", [today])
    somme = sql("SELECT SUM(montant_facture) AS facture, SUM(montpaye) AS enc "
                "FROM factures WHERE date_facture = %s", [today])
    tot = somme[0] if somme else {"facture": 0, "enc": 0}
    return render(request, "gestion/caisse/caisse.html", {"lignes": lignes, "tot": tot})


@profils_autorises(1, 3, 7)
def caisse_acompte(request):
    rows = _resume_factures("etat_facture = 0")
    return render(request, "gestion/caisse/acompte.html",
                  {"factures": rows, "kpi": _kpi_factures(rows)})


@profils_autorises(1, 3, 7)
def caisse_ajout_ac(request, numero_facture):
    rows = sql(
        "SELECT f.*, c.prenom_nom, c.telephone FROM factures f "
        "INNER JOIN client c ON f.id_client = c.id_client "
        "WHERE f.numero_facture = %s", [numero_facture])
    fact = rows[0] if rows else None
    if fact:
        # Échéance au format ISO pour le champ caché (évite le format localisé).
        d_ech = _asdate(fact.get("date_echeance"))
        fact["date_echeance"] = d_ech.isoformat() if d_ech else ""
    _lignes, _inv, paye, _rel, _idc = _synthese_facture(numero_facture)
    return render(request, "gestion/caisse/ajout_ac.html",
                  {"fact": fact, "cumul_paye": paye,
                   "today": date.today().isoformat()})


@profils_autorises(1, 3, 7)
def caisse_fonction(request):
    """Traite les actions de caisse : valider un paiement ou ajouter un acompte."""
    if request.method != "POST":
        return redirect("caisse")

    # --- Modification état / paiement ---
    if "valider" in request.POST:
        id_facture = request.POST.get("id_facture")
        montpaye = request.POST.get("montpaye")
        reste = float(request.POST.get("reste") or 0)
        etat = 1 if reste == 0 else 0
        Factures.objects.filter(id_facture=id_facture).update(
            montpaye=montpaye, etat_facture=etat)
        return redirect("etat")

    # --- Ajout d'un acompte (nouvelle ligne facture) ---
    if "ajouter" in request.POST:
        numero_facture = request.POST.get("numero_facture")
        d_acompte = _asdate(request.POST.get("date_facture")) or date.today()
        date_acompte = d_acompte.isoformat()
        # date_echeance est NOT NULL. La valeur postée peut être au format
        # localisé (« 21 août 2026 ») : on la convertit, sinon on retombe sur
        # la date de l'acompte.
        d_ech = _asdate(request.POST.get("date_echeance"))
        date_echeance = (d_ech or d_acompte).isoformat()
        Factures.objects.create(
            id_client=request.POST.get("id_client"),
            date_facture=date_acompte,
            id_societe=1,
            numero_facture=numero_facture,
            montant_facture=0,
            montpaye=request.POST.get("montpaye") or 0,
            etat_facture=0,
            heure_facture=datetime.now().strftime("%H:%M:%S"),
            date_echeance=date_echeance,
        )
        # Recalcul de l'état global du numéro de facture
        agg = sql("SELECT SUM(montpaye) AS paye, SUM(montant_facture) AS fact "
                  "FROM factures WHERE numero_facture=%s", [numero_facture])
        paye = agg[0]["paye"] or 0
        fact = agg[0]["fact"] or 0
        etat = 1 if (fact - paye) == 0 else 0
        Factures.objects.filter(numero_facture=numero_facture).update(etat_facture=etat)
        return redirect("caisse_acompte")

    return redirect("caisse")


# ===========================================================================
# LIVRE DE CAISSE JOURNALIER (entrées encaissées / sorties dépenses)
# ===========================================================================
@profils_autorises(1, 3, 7)
def caisse_journal(request):
    """Caisse du jour : entrées (factures encaissées) et sorties (dépenses).

    Affiche le jour courant par défaut ; un sélecteur de date permet de
    consulter une autre journée. En bas : total des entrées, total des
    sorties, et le total caisse = entrées - sorties.
    """
    jour = (request.POST.get("jour") or request.GET.get("jour")
            or date.today().isoformat())

    # --- Entrées : sommes réellement encaissées ce jour (montpaye > 0) -------
    entrees = sql(
        "SELECT f.numero_facture, f.montpaye, f.heure_facture, c.prenom_nom "
        "FROM factures f "
        "JOIN client c ON f.id_client = c.id_client "
        "WHERE f.date_facture = %s AND f.montpaye > 0 "
        "ORDER BY f.heure_facture, f.id_facture",
        [jour])
    total_entrees = sum(_num(e.get("montpaye")) for e in entrees)

    # --- Sorties : dépenses saisies ce jour ----------------------------------
    sorties = list(Depense.objects.filter(date_depense=jour).order_by("id_depense"))
    total_sorties = sum(_num(s.montant) for s in sorties)

    return render(request, "gestion/caisse/journal.html", {
        "jour": jour,
        "entrees": entrees,
        "sorties": sorties,
        "total_entrees": total_entrees,
        "total_sorties": total_sorties,
        "total_caisse": total_entrees - total_sorties,
    })


@profils_autorises(1, 3, 7)
def depense_insert(request):
    """Enregistre une sortie de caisse (dépense)."""
    if request.method == "POST" and "bt_depense" in request.POST:
        jour = request.POST.get("jour") or date.today().isoformat()
        nom = (request.POST.get("nom") or "").strip()
        objet = (request.POST.get("objet") or "").strip()
        montant = _num(request.POST.get("montant"))
        if nom and objet and montant > 0:
            Depense.objects.create(
                date_depense=jour,
                nom=nom,
                objet=objet,
                montant=montant,
                id_societe=request.session.get("id_societe", 1),
                id_user=request.session.get("id_user"),
            )
        return redirect(f"{reverse('caisse_journal')}?jour={jour}")
    return redirect("caisse_journal")


@profils_autorises(1, 3, 7)
def depense_supp(request, id_depense):
    """Supprime une sortie de caisse."""
    dep = Depense.objects.filter(id_depense=id_depense).first()
    jour = dep.date_depense.isoformat() if dep and dep.date_depense else date.today().isoformat()
    Depense.objects.filter(id_depense=id_depense).delete()
    return redirect(f"{reverse('caisse_journal')}?jour={jour}")


# ===========================================================================
# COMPTABILITE
# ===========================================================================
@profils_autorises(1, 2, 4)
def finance(request):
    dated = request.POST.get("dated") or request.GET.get("dated")
    datef = request.POST.get("datef") or request.GET.get("datef")
    lignes = []
    tot = {"facture": 0, "enc": 0, "remise": 0, "reste": 0}
    if dated and datef:
        # Agrégation par numéro de facture : montant, encaissé, remise et
        # reliquat = montant - encaissé - remise (cohérent avec la facturation).
        lignes = _resume_factures("date_facture BETWEEN %s AND %s", [dated, datef],
                                  order="ORDER BY f.date_facture ASC")
        for r in lignes:
            r["equilibre"] = abs(_num(r.get("reliquat"))) < 0.5
        k = _kpi_factures(lignes)
        tot = {"facture": k["facture"], "enc": k["encaisse"],
               "remise": k["remise"], "reste": k["reste"]}
    return render(request, "gestion/comptable/finance.html",
                  {"lignes": lignes, "tot": tot, "dated": dated, "datef": datef})


# ===========================================================================
# MARQUAGE
# ===========================================================================
@profils_autorises(1, 2, 5)
def marquage(request):
    numeros = sql("SELECT DISTINCT numero_facture FROM marquage ORDER BY numero_facture DESC")
    selection = request.POST.get("numero_facture") or request.GET.get("numero_facture")
    lignes = []
    if selection:
        lignes = sql(
            "SELECT m.id_marquage, m.numero_facture, m.id_couture, m.date_couture, "
            "m.id_brodeur, m.date_broderie, m.id_bouton, m.date_bouton, "
            "p.des, p.catp, mo.libmod "
            "FROM marquage m "
            "INNER JOIN produit p ON p.codep = m.id_article "
            "INNER JOIN modele mo ON mo.codemod = p.id_modele "
            "WHERE m.numero_facture = %s", [selection])
    kpi = {
        "total": len(lignes),
        "couture": sum(1 for l in lignes if l.get("date_couture")),
        "broderie": sum(1 for l in lignes if l.get("date_broderie")),
        "bouton": sum(1 for l in lignes if l.get("date_bouton")),
    }
    return render(request, "gestion/marquage/marquage.html",
                  {"numeros": numeros, "lignes": lignes, "selection": selection, "kpi": kpi})


@profils_autorises(1, 2, 5)
def marquage_detail(request, id_marquage, phase):
    """Formulaire d'affectation d'un tailleur pour une phase (couture/broderie/bouton)."""
    types = {"couture": "Tailleur simple", "broderie": "Brodeur", "bouton": "Boutonnier"}
    tailleurs = Tailleur.objects.filter(type_tailleur=types.get(phase, "Tailleur simple"))
    return render(request, "gestion/marquage/detail.html",
                  {"id_marquage": id_marquage, "phase": phase, "tailleurs": tailleurs})


@profils_autorises(1, 2, 5)
def marquage_update(request):
    if request.method != "POST":
        return redirect("marquage")
    id_marquage = request.POST.get("id_marquage")
    prenom_nom = request.POST.get("prenom_nom")  # = id_tailleur
    if "bt_couture" in request.POST:
        Marquage.objects.filter(id_marquage=id_marquage).update(
            date_couture=request.POST.get("date_couture") or None, id_couture=prenom_nom)
    elif "bt_broderie" in request.POST:
        Marquage.objects.filter(id_marquage=id_marquage).update(
            date_broderie=request.POST.get("date_broderie") or None, id_brodeur=prenom_nom)
    elif "bt_bouton" in request.POST:
        Marquage.objects.filter(id_marquage=id_marquage).update(
            date_bouton=request.POST.get("date_bouton") or None, id_bouton=prenom_nom)
    return redirect("marquage")


@profils_autorises(1, 2, 5)
def tailleur(request):
    liste = list(Tailleur.objects.all().order_by("-id_tailleur"))
    nb_simple = sum(1 for t in liste if (t.type_tailleur or "").lower().startswith("tailleur"))
    nb_brodeur = sum(1 for t in liste if (t.type_tailleur or "").lower().startswith("brod"))
    nb_bouton = sum(1 for t in liste if (t.type_tailleur or "").lower().startswith("bouton"))
    return render(request, "gestion/marquage/tailleur.html", {
        "tailleurs": liste, "nb_total": len(liste),
        "nb_simple": nb_simple, "nb_brodeur": nb_brodeur, "nb_bouton": nb_bouton})


@profils_autorises(1, 2, 5)
def tailleur_insert(request):
    if request.method == "POST" and "bt_tailleur" in request.POST:
        Tailleur.objects.create(
            prenom_nom=request.POST.get("prenom_nom"),
            type_tailleur=request.POST.get("type_tailleur"),
            id_societe=request.session.get("id_societe", 1),
        )
    return redirect("tailleur")


@profils_autorises(1, 2, 5)
def tarif(request):
    rows = sql("SELECT t.*, mo.libmod FROM tarification t "
               "INNER JOIN modele mo ON t.id_modele = mo.codemod")
    modeles = Modele.objects.all().order_by("libmod")
    return render(request, "gestion/marquage/tarif.html",
                  {"tarifs": rows, "modeles": modeles})


@profils_autorises(1, 2, 5)
def tarif_insert(request):
    if request.method == "POST" and "bt_tarif" in request.POST:
        Tarification.objects.create(
            id_modele=request.POST.get("codemod"),
            tarif_simple=request.POST.get("tarif_simple") or 0,
            tarif_brodeur=request.POST.get("tarif_brodeur") or 0,
            tarif_bouton=request.POST.get("tarif_bouton") or 0,
            id_societe=request.session.get("id_societe", 1),
        )
    return redirect("tarif")


@profils_autorises(1, 2, 5)
def honoraire(request):
    """Honoraires tailleur sur une période (équivalent honno.php)."""
    tailleurs = Tailleur.objects.all()
    resultats = []
    total = 0
    id_tailleur = request.POST.get("prenom_nom")
    dd = request.POST.get("datedeb")
    df = request.POST.get("datefin")
    t = Tailleur.objects.filter(id_tailleur=id_tailleur).first() if id_tailleur else None
    if t and dd and df:
        mapping = {
            "Tailleur simple": ("date_couture", "tarif_simple", "id_couture"),
            "Brodeur": ("date_broderie", "tarif_brodeur", "id_brodeur"),
            "Boutonnier": ("date_bouton", "tarif_bouton", "id_bouton"),
        }
        colonne_date, colonne_tarif, colonne_id = mapping.get(
            t.type_tailleur, ("date_couture", "tarif_simple", "id_couture"))
        query = (
            f"SELECT m.{colonne_date} AS d, mo.libmod, tf.{colonne_tarif} AS tarif "
            "FROM marquage m "
            "INNER JOIN produit p ON m.id_article = p.codep "
            "INNER JOIN modele mo ON p.id_modele = mo.codemod "
            "INNER JOIN tarification tf ON mo.codemod = tf.id_modele "
            f"WHERE m.{colonne_id} = %s AND m.{colonne_date} BETWEEN %s AND %s "
            f"AND m.{colonne_date} IS NOT NULL")
        resultats = sql(query, [id_tailleur, dd, df])
        total = sum(r["tarif"] or 0 for r in resultats)
    return render(request, "gestion/marquage/honoraire.html", {
        "tailleurs": tailleurs, "resultats": resultats, "total": total,
        "tailleur": t, "datedeb": dd, "datefin": df,
    })


# ===========================================================================
# PARAMETRES (profils / utilisateurs)
# ===========================================================================
@profils_autorises(1)
def profil(request):
    liste = Profil.objects.all()
    return render(request, "gestion/param/profil.html", {"profils": liste})


@profils_autorises(1)
def profil_insert(request):
    if request.method == "POST" and "bt_profil" in request.POST:
        Profil.objects.create(
            nomprofil=request.POST.get("nomprofil"),
            id_societe=request.session.get("id_societe", 1),
        )
    return redirect("profil")


@profils_autorises(1)
def utilisateur(request):
    rows = sql("SELECT u.*, p.nomprofil FROM user u "
               "INNER JOIN profil p ON u.id_profil = p.id_profil")
    profils = Profil.objects.all()
    return render(request, "gestion/param/user.html",
                  {"utilisateurs": rows, "profils": profils})


@profils_autorises(1)
def utilisateur_insert(request):
    if request.method == "POST" and "bt_user" in request.POST:
        User.objects.create(
            login=request.POST.get("login"),
            password=request.POST.get("password"),
            id_societe=request.session.get("id_societe", 1),
            id_profil=request.POST.get("nomprofil"),
            etat=1,
        )
    return redirect("utilisateur")


@profils_autorises(1)
def utilisateur_mot_de_passe(request, id_user):
    """Réservé à l'administrateur : change le mot de passe d'un autre utilisateur."""
    if request.method != "POST":
        return redirect("utilisateur")
    cible = User.objects.filter(id_user=id_user).first()
    if cible is None:
        messages.error(request, "Utilisateur introuvable.")
        return redirect("utilisateur")
    nouveau = request.POST.get("nouveau_mdp", "")
    confirmation = request.POST.get("confirmation_mdp", "")
    if len(nouveau) < 4:
        messages.error(request, "Le mot de passe doit comporter au moins 4 caractères.")
    elif nouveau != confirmation:
        messages.error(request, "Les deux mots de passe ne correspondent pas.")
    else:
        # Même convention que la création d'utilisateur (table partagée avec l'app PHP).
        User.objects.filter(id_user=id_user).update(password=nouveau)
        messages.success(request, f"Mot de passe de « {cible.login} » modifié.")
    return redirect("utilisateur")


# ===========================================================================
# TABLEAU DE BORD (statistiques)
# ===========================================================================
import calendar as _cal
import json as _json

MOIS_FR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
           "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
MOIS_FR_LONG = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
                "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _num(valeur):
    """Convertit en float de façon sûre (les colonnes héritées peuvent être
    du texte, vides ou nulles)."""
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


def _asdate(valeur):
    """Retourne un objet date, ou None. Gère les chaînes 'AAAA-MM-JJ',
    les datetime, et les dates invalides ('0000-00-00')."""
    if valeur in (None, "", "0000-00-00"):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(valeur)[:10], fmt).date()
        except ValueError:
            continue
    return None


def _cles_12_mois(aujourdhui):
    """Retourne la liste ordonnée des 12 derniers mois : [(annee, mois), ...]."""
    y, m = aujourdhui.year, aujourdhui.month
    cles = []
    for i in range(11, -1, -1):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        cles.append((yy, mm))
    return cles


@profils_autorises(1, 2, 4, 7)
def dashboard(request):
    id_societe = request.session.get("id_societe", 1)
    # UNE ligne par numéro de facture (montant = montant de la facture, cumul =
    # encaissé réel), pour éviter le double comptage des factures payées en
    # plusieurs fois.
    qs = _resume_factures("id_societe = %s", [id_societe])

    # --- Indicateurs clés ---
    nb_payees = sum(1 for f in qs if _num(f.get("reliquat")) <= 0.5)
    nb_impayees = len(qs) - nb_payees
    nb_factures = len(qs)

    # Le total facturé (et l'encaissé/reliquat/remise associés) portent sur
    # l'année sélectionnée (année en cours par défaut).
    annee_courante, annees = _contexte_annee(request)
    qs_annee = _filtrer_par_annee(qs, annee_courante)
    total_facture = sum(_num(f.get("montant_facture")) for f in qs_annee)
    total_encaisse = sum(_num(f.get("cumul_paye")) for f in qs_annee)
    total_remise = sum(_num(f.get("remise")) for f in qs_annee)
    reliquat = total_facture - total_encaisse - total_remise
    nb_factures_annee = len(qs_annee)

    # --- Montants facturés / encaissés par mois (12 derniers mois) ---
    aujourdhui = date.today()
    cles = _cles_12_mois(aujourdhui)
    fact_mois = {(y, m): 0 for (y, m) in cles}
    enc_mois = {(y, m): 0 for (y, m) in cles}
    for f in qs:
        d = _asdate(f.get("date_facture"))
        if not d:
            continue
        k = (d.year, d.month)
        if k in fact_mois:
            fact_mois[k] += _num(f.get("montant_facture"))
            enc_mois[k] += _num(f.get("cumul_paye"))
    labels_mois = [f"{MOIS_FR[m - 1]} {str(y)[2:]}" for (y, m) in cles]
    data_facture = [round(fact_mois[k], 2) for k in cles]
    data_encaisse = [round(enc_mois[k], 2) for k in cles]

    # --- Nombre de commandes par client (mois courant) ---
    debut_mois = aujourdhui.replace(day=1)
    par_client = {}
    for f in qs:
        d = _asdate(f.get("date_facture"))
        if d and d >= debut_mois:
            cid = f.get("id_client")
            par_client[cid] = par_client.get(cid, 0) + 1
    noms = {c.id_client: c.prenom_nom for c in
            Client.objects.filter(id_client__in=list(par_client.keys()))}
    top = sorted(par_client.items(), key=lambda x: -x[1])[:8]
    labels_clients = [noms.get(cid) or f"Client #{cid}" for cid, _ in top]
    data_clients = [n for _, n in top]

    ctx = {
        "nb_payees": nb_payees,
        "nb_impayees": nb_impayees,
        "nb_factures": nb_factures,
        "nb_factures_annee": nb_factures_annee,
        "annee_courante": annee_courante,
        "annee": annee_courante,
        "annees": annees,
        "total_facture": total_facture,
        "total_encaisse": total_encaisse,
        "reliquat": reliquat,
        "taux_recouvrement": round((total_encaisse / total_facture * 100) if total_facture else 0),
        "pct_payees": round((nb_payees / nb_factures * 100) if nb_factures else 0),
        "mois_courant": f"{MOIS_FR_LONG[aujourdhui.month - 1]} {aujourdhui.year}",
        # données JSON pour Chart.js
        "labels_mois": _json.dumps(labels_mois),
        "data_facture": _json.dumps(data_facture),
        "data_encaisse": _json.dumps(data_encaisse),
        "data_etat": _json.dumps([nb_payees, nb_impayees]),
        "labels_clients": _json.dumps(labels_clients),
        "data_clients": _json.dumps(data_clients),
        "aucun_client": len(top) == 0,
    }
    return render(request, "gestion/dashboard.html", ctx)


# ===========================================================================
# CALENDRIER DES RENDEZ-VOUS (livraisons = date_facture + 21 jours)
# ===========================================================================
DELAI_LIVRAISON = 21  # jours


def _livraisons(id_societe):
    """Liste des factures avec leur date de livraison (échéance)."""
    res = []
    for f in Factures.objects.filter(id_societe=id_societe):
        d_fact = _asdate(f.date_facture)
        if not d_fact:
            continue
        livraison = _asdate(f.date_echeance) or (d_fact + timedelta(days=DELAI_LIVRAISON))
        montant = _num(f.montant_facture)
        res.append({
            "id_facture": f.id_facture,
            "numero_facture": f.numero_facture,
            "id_client": f.id_client,
            "date_facture": d_fact,
            "livraison": livraison,
            "solde": (f.etat_facture or 0) == 1,
            "montant": montant,
            "reste": montant - _num(f.montpaye),
        })
    return res


@profils_autorises(1, 2, 3, 4, 7)
def calendrier(request):
    id_societe = request.session.get("id_societe", 1)

    # Mois affiché (?mois=YYYY-MM), défaut = mois courant
    param = request.GET.get("mois")
    aujourdhui = date.today()
    if param:
        try:
            an, mo = [int(x) for x in param.split("-")]
        except (ValueError, TypeError):
            an, mo = aujourdhui.year, aujourdhui.month
    else:
        an, mo = aujourdhui.year, aujourdhui.month

    livraisons = _livraisons(id_societe)
    noms = {c.id_client: c.prenom_nom for c in Client.objects.all()}

    # Regrouper les livraisons par jour du mois affiché
    par_jour = {}
    for lv in livraisons:
        d = lv["livraison"]
        if d.year == an and d.month == mo:
            lv["client"] = noms.get(lv["id_client"]) or f"Client #{lv['id_client']}"
            par_jour.setdefault(d.day, []).append(lv)

    # Construire la grille du calendrier (semaines commençant le lundi)
    _cal.setfirstweekday(_cal.MONDAY)
    semaines = []
    for semaine in _cal.monthcalendar(an, mo):
        ligne = []
        for jour in semaine:
            cell = {"jour": jour, "events": [], "aujourdhui": False}
            if jour != 0:
                cell["events"] = sorted(par_jour.get(jour, []),
                                        key=lambda e: e["numero_facture"] or "")
                cell["aujourdhui"] = (an == aujourdhui.year and mo == aujourdhui.month
                                      and jour == aujourdhui.day)
            ligne.append(cell)
        semaines.append(ligne)

    # Navigation mois précédent / suivant
    prec_a, prec_m = (an - 1, 12) if mo == 1 else (an, mo - 1)
    suiv_a, suiv_m = (an + 1, 1) if mo == 12 else (an, mo + 1)

    # Prochaines livraisons (à venir, 30 jours)
    limite = aujourdhui + timedelta(days=30)
    a_venir = sorted(
        [lv for lv in livraisons if aujourdhui <= lv["livraison"] <= limite and not lv["solde"]],
        key=lambda e: e["livraison"])
    for lv in a_venir:
        lv["client"] = noms.get(lv["id_client"]) or f"Client #{lv['id_client']}"
        lv["jours_restants"] = (lv["livraison"] - aujourdhui).days

    ctx = {
        "titre_mois": f"{MOIS_FR_LONG[mo - 1]} {an}",
        "jours_fr": JOURS_FR,
        "semaines": semaines,
        "prec": f"{prec_a}-{prec_m:02d}",
        "suiv": f"{suiv_a}-{suiv_m:02d}",
        "courant": f"{aujourdhui.year}-{aujourdhui.month:02d}",
        "a_venir": a_venir,
        "nb_a_venir": len(a_venir),
        "total_livraisons": len([lv for lv in livraisons
                                 if lv["livraison"].year == an and lv["livraison"].month == mo]),
    }
    return render(request, "gestion/calendrier.html", ctx)


@profils_autorises(1, 2, 3, 4, 7)
def calendrier_ics(request):
    """Export iCalendar (.ics) des livraisons à venir — importable dans
    Google Agenda / Outlook pour recevoir des rappels."""
    id_societe = request.session.get("id_societe", 1)
    noms = {c.id_client: c.prenom_nom for c in Client.objects.all()}
    aujourdhui = date.today()

    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0",
              "PRODID:-//Senegal Broderie Moderne//Livraisons//FR",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    horodatage = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    for lv in _livraisons(id_societe):
        if lv["livraison"] < aujourdhui - timedelta(days=1):
            continue
        client = noms.get(lv["id_client"]) or f"Client #{lv['id_client']}"
        d = lv["livraison"].strftime("%Y%m%d")
        fin = (lv["livraison"] + timedelta(days=1)).strftime("%Y%m%d")
        etat = "SOLDÉE" if lv["solde"] else f"Reste {int(lv['reste'])} FCFA"
        lignes += [
            "BEGIN:VEVENT",
            f"UID:facture-{lv['id_facture']}@sbroderie",
            f"DTSTAMP:{horodatage}",
            f"DTSTART;VALUE=DATE:{d}",
            f"DTEND;VALUE=DATE:{fin}",
            f"SUMMARY:Livraison {lv['numero_facture']} - {client}",
            f"DESCRIPTION:Facture {lv['numero_facture']} - {client} ({etat})",
            "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY",
            f"DESCRIPTION:Rappel livraison {lv['numero_facture']}", "END:VALARM",
            "END:VEVENT",
        ]
    lignes.append("END:VCALENDAR")
    contenu = "\r\n".join(lignes)
    resp = HttpResponse(contenu, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="livraisons_sbm.ics"'
    return resp
