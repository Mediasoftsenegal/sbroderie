"""
Génération de la facture PDF, portage fidèle de admin/facture/details.php (FPDF).

Utilise fpdf2 (pip install fpdf2). Reproduit l'en-tête société, le tableau des
articles, le total en chiffres et en lettres, ainsi que le bon de coupe.
"""
import os
from datetime import datetime
from django.conf import settings
from fpdf import FPDF

from .models import Client, DetailFacture, Factures, Mesure
from .utils import chiffre_en_lettre, format_fcfa

LOGO = os.path.join(settings.BASE_DIR, "static", "img", "logo.jpg")


class FacturePDF(FPDF):
    societe = settings.SOCIETE

    def _format_date(self, value):
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d-%m-%Y")
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return ""
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(value, fmt).strftime("%d-%m-%Y")
                except ValueError:
                    pass
            return value
        return str(value)

    def _date_rv(self, facture):
        for attr in ("date_rv", "date_rdv", "date_rendez_vous", "date_echeance"):
            val = getattr(facture, attr, None)
            if val:
                return self._format_date(val)
        return ""

    def en_tete(self, facture, client):
        if os.path.exists(LOGO):
            try:
                self.image(LOGO, 160, 6, 40)
            except Exception:
                pass
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, self.societe["nom"], 0, 1)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 10, self.societe["adresse1"], 0, 1)
        self.cell(0, 0, self.societe["adresse2"], 0, 1)
        self.cell(0, 10, self.societe["bp"], 0, 1)
        self.cell(0, 0, self.societe["tel"], 0, 1)
        self.ln(8)
        self.set_font("Helvetica", "", 13)
        self.cell(60, 10, "", 0, 0)
        self.cell(60, 10, f"FACTURE N°{facture.numero_facture}", 1, 0, "C")
        self.ln()
        self.set_font("Helvetica", "", 10)
        
        date_rv = self._date_rv(facture)

        self.cell(0, 6, f"CLIENT : {client.prenom_nom or ''}", 0, 1)
        self.cell(0, 6, f"Téléphone : {client.telephone or ''}", 0, 1)

        self.cell(95, 6, f"Date : {self._format_date(facture.date_facture)}", 0, 0)
        self.cell(95, 6, f"Date de RV : {date_rv}" if date_rv else "Date de RV : -", 0, 1, "R")

        self.ln(4)

    def tableau_articles(self, detail):
        articles = (detail.article or "").split(",")
        prix = (detail.prix_unitaire or "").split(",")
        nombres = (detail.nombre or "").split(",")
        self.set_font("Helvetica", "B", 10)
        self.cell(90, 8, "Désignation", 1, 0, "C")
        self.cell(30, 8, "P.U", 1, 0, "C")
        self.cell(20, 8, "Qté", 1, 0, "C")
        self.cell(40, 8, "Montant", 1, 1, "C")
        self.set_font("Helvetica", "", 10)
        total = 0
        for i, art in enumerate(articles):
            pu = _to_float(prix[i]) if i < len(prix) else 0
            qt = _to_float(nombres[i]) if i < len(nombres) else 0
            mt = pu * qt
            total += mt
            self.cell(90, 8, art.strip()[:55], 1, 0)
            self.cell(30, 8, format_fcfa(pu), 1, 0, "R")
            self.cell(20, 8, str(int(qt)), 1, 0, "C")
            self.cell(40, 8, format_fcfa(mt), 1, 1, "R")
        if total == 0:
            total = detail.montant or 0
        return total

    def pied_total(self, facture, total):
        remise = facture.remise or 0
        net = total - remise
        paye = facture.montpaye or 0
        reste = net - paye
        self.set_font("Helvetica", "B", 10)
        self.cell(140, 8, "TOTAL", 1, 0, "R")
        self.cell(40, 8, format_fcfa(total) + " F CFA", 1, 1, "R")
        if remise:
            self.cell(140, 8, "REMISE", 1, 0, "R")
            self.cell(40, 8, format_fcfa(remise) + " F CFA", 1, 1, "R")
            self.cell(140, 8, "NET À PAYER", 1, 0, "R")
            self.cell(40, 8, format_fcfa(net) + " F CFA", 1, 1, "R")
        self.cell(140, 8, "MONTANT ENCAISSÉ", 1, 0, "R")
        self.cell(40, 8, format_fcfa(paye) + " F CFA", 1, 1, "R")
        self.cell(140, 8, "RESTE À PAYER", 1, 0, "R")
        self.cell(40, 8, format_fcfa(reste) + " F CFA", 1, 1, "R")
        self.ln(4)
        self.set_font("Helvetica", "I", 10)
        lettres = chiffre_en_lettre(net).capitalize()
        self.multi_cell(0, 6, f"Arrêtée la présente facture à la somme de : {lettres} francs CFA.")

    # ------------------------------------------------------------------
    # Bons de confection couture (un par pièce) : reprend details.php
    # ------------------------------------------------------------------
    def bon_confection(self, detail, facture, client, mesure, avec_mesures=True):
        articles = (detail.article or "").split(",")
        nombres = (detail.nombre or "").split(",")

        def m(champ):
            val = getattr(mesure, champ, "") if mesure else ""
            return "" if val is None else str(val)

        BON_H = 122  # hauteur approximative d'un bon (mm)

        def un_bon(designation, numero, premier):
            # Saut de page uniquement si le bon ne tient pas dans l'espace restant
            limite = self.h - self.b_margin
            if self.get_y() + BON_H > limite:
                self.add_page()
            elif not premier:
                # trait de découpe pointillé entre deux bons sur la même page
                self.ln(2)
                self.set_draw_color(150, 150, 150)
                self.set_line_width(0.2)
                y = self.get_y()
                x = self.l_margin
                while x < self.w - self.r_margin:
                    self.line(x, y, min(x + 3, self.w - self.r_margin), y)
                    x += 6
                self.set_draw_color(0, 0, 0)
                self.ln(3)
            self.set_text_color(0, 0, 0)
            self.set_font("Courier", "B", 18)
            self.cell(0, 12, "BON DE CONFECTION COUTURE", 0, 1, "C")
            self.set_font("Courier", "", 11)
            rv_date = self._date_rv(facture)
            self.cell(95, 6, f"DATE COMMANDE : {facture.date_facture}", 0, 0)
            self.cell(95, 6, f"DATE DE RV : {rv_date}" if rv_date else "DATE DE RV : -", 0, 1)
            self.cell(130, 6, f"DATE COMMANDE : {facture.date_facture}", 0, 0)
            self.cell(60, 6, f"DATE RDV : {facture.date_echeance or ''}", 0, 1)

            self.cell(
                0,
                6,
                f"CLIENT : {client.prenom_nom or ''}",
                0,
                1,
            )

            self.cell(95, 5, f"TELEPHONE : {client.telephone or ''}", 0, 0)
            self.cell(95, 5, f"DESIGNATION : {designation.strip()}", 0, 1)
            self.set_font("Courier", "B", 18)
            self.cell(0, 11, f"Bon N° : {numero}", 0, 1, "C")
            self.set_font("Courier", "", 11)
            lignes = [
                ("EP : " + m("epaule"), "POITRINE : " + m("poitrine")),
                ("M : " + m("manche"), "TF : " + m("tourfess")),
                ("COU : " + m("cou"), "CEINTURE : " + m("ceinture")),
                ("LB : " + m("longueur"), "LP : " + m("longueurpantalon")),
                ("TAILLE : ", "MANCHE POIGNET : " + m("poignet")),
                ("CUISSE : " + m("cuisse"), "T BRAS : " + m("tourbras")),
                ("GRAND BOUBOU : " + m("longueurgrandboubou"), "BAS : " + m("bas")),
                ("TOUR MANCHE : " + m("tourmanche"), "HANCHE : " + m("hanche")),
            ]
            # Grille de mesures omise quand avec_mesures=False (PDF envoyé au client)
            for g, d in (lignes if avec_mesures else []):
                self.cell(95, 6, g, 0, 0)
                self.cell(95, 6, d, 0, 1)
            self.cell(0, 8, "Tailleurs :  Broderie .....................  Simple .....................", 0, 1)

        premier = True
        for i, art in enumerate(articles):
            a = i + 1
            try:
                qty = int(float((nombres[i] if i < len(nombres) else "1").strip() or 1))
            except (TypeError, ValueError):
                qty = 1
            if qty > 1:
                for j in range(1, qty + 1):
                    un_bon(
                        art,
                        f"{facture.numero_facture}-{a}-{j}/{qty}",
                        premier,
                    )
                    premier = False
            else:
                un_bon(
                    art,
                    f"{facture.numero_facture}-{a}-1/1",
                    premier,
                )
                premier = False


def _to_float(v):
    try:
        return float(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def generer_facture_pdf(id_facture, avec_mesures=True):
    """Retourne les octets PDF de la facture identifiée par id_facture.

    avec_mesures=False : les bons de confection sont imprimés sans la grille
    de mesures (version destinée au client). Le PDF par défaut est inchangé.
    """
    facture = Factures.objects.filter(id_facture=id_facture).first()
    if not facture:
        return None
    detail = DetailFacture.objects.filter(id_facture=id_facture).first()
    client = Client.objects.filter(id_client=facture.id_client).first()
    if client is None:
        client = Client(prenom_nom="", telephone="")
    mesure = None
    if avec_mesures:
        mesure = Mesure.objects.filter(id_client=facture.id_client).order_by("-id_mesure").first()

    pdf = FacturePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.en_tete(facture, client)
    total = 0
    if detail:
        total = pdf.tableau_articles(detail)
    pdf.pied_total(facture, total)
    # Mention légale en bandeau noir, sous la facture et avant les bons
    pdf.ln(4)
    pdf.set_fill_color(0, 0, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 9,
             "NB: Passé un dèlai de trois(3) mois, la maison décline toute responsabilité",
             0, 1, "C", True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    # Bons de confection (un par pièce, répété selon la quantité)
    if detail:
        pdf.bon_confection(detail, facture, client, mesure, avec_mesures=avec_mesures)

    out = pdf.output(dest="S")
    if isinstance(out, str):
        out = out.encode("latin-1")
    return bytes(out)
