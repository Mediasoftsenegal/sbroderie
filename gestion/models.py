"""
Modèles Django mappés sur la base MySQL EXISTANTE `mediapla_sb`.

IMPORTANT : tous les modèles ont `managed = False`. Django n'essaiera JAMAIS
de créer, modifier ou supprimer ces tables : il se contente de lire/écrire les
données déjà présentes. Aucune migration de données n'est nécessaire.

Les noms de tables, de colonnes et de clés primaires ont été déduits du code PHP
d'origine. Si une clé primaire diffère sur votre base, ajustez `primary_key=True`
en conséquence (voir README, section « Vérifier le schéma avec inspectdb »).
"""
from django.db import models


class Profil(models.Model):
    id_profil = models.AutoField(primary_key=True)
    nomprofil = models.CharField(max_length=100)
    id_societe = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "profil"

    def __str__(self):
        return self.nomprofil


class User(models.Model):
    id_user = models.AutoField(primary_key=True)
    login = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    id_societe = models.IntegerField(default=1)
    id_profil = models.IntegerField(default=1)
    etat = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "user"

    def __str__(self):
        return self.login


class Client(models.Model):
    id_client = models.AutoField(primary_key=True)
    codecli = models.CharField(max_length=100, blank=True, null=True)
    prenom_nom = models.CharField(max_length=255, blank=True, null=True)
    genre = models.CharField(max_length=50, blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True, null=True)
    id_societe = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "client"

    def __str__(self):
        return self.prenom_nom or self.codecli or str(self.id_client)


class Mesure(models.Model):
    id_mesure = models.AutoField(primary_key=True)
    genre = models.CharField(max_length=50, blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    longueur = models.CharField(max_length=50, blank=True, null=True)
    longueurgrandboubou = models.CharField(max_length=50, blank=True, null=True)
    epaule = models.CharField(max_length=50, blank=True, null=True)
    cou = models.CharField(max_length=50, blank=True, null=True)
    manche = models.CharField(max_length=50, blank=True, null=True)
    longueurpantalon = models.CharField(max_length=50, blank=True, null=True)
    tourfess = models.CharField(max_length=50, blank=True, null=True)
    cuisse = models.CharField(max_length=50, blank=True, null=True)
    bas = models.CharField(max_length=50, blank=True, null=True)
    poitrine = models.CharField(max_length=50, blank=True, null=True)
    tourmanche = models.CharField(max_length=50, blank=True, null=True)
    ceinture = models.CharField(max_length=50, blank=True, null=True)
    hanche = models.CharField(max_length=50, blank=True, null=True)
    tourbras = models.CharField(max_length=50, blank=True, null=True)
    poignet = models.CharField(max_length=50, blank=True, null=True)
    id_societe = models.IntegerField(default=1, blank=True, null=True)
    id_client = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "mesure"


class Modele(models.Model):
    codemod = models.AutoField(primary_key=True)
    libmod = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "modele"

    def __str__(self):
        return self.libmod


class Produit(models.Model):
    codep = models.AutoField(primary_key=True)
    des = models.CharField(max_length=255, blank=True, null=True)
    pu = models.FloatField(default=0)
    catp = models.CharField(max_length=50, blank=True, null=True)
    id_modele = models.IntegerField(blank=True, null=True)
    genre = models.CharField(max_length=50, blank=True, null=True)
    couleur = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "produit"

    def __str__(self):
        return self.des or str(self.codep)


class Factures(models.Model):
    id_facture = models.AutoField(primary_key=True)
    id_client = models.IntegerField(blank=True, null=True)
    date_facture = models.DateField(blank=True, null=True)
    id_societe = models.IntegerField(default=1)
    numero_facture = models.CharField(max_length=100, blank=True, null=True)
    montant_facture = models.FloatField(default=0, blank=True, null=True)
    remise = models.FloatField(default=0, blank=True, null=True)
    montpaye = models.FloatField(default=0, blank=True, null=True)
    etat_facture = models.IntegerField(default=0, blank=True, null=True)
    heure_facture = models.CharField(max_length=20, blank=True, null=True)
    date_echeance = models.DateField(blank=True, null=True)
    cmpt = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "factures"


class DetailFacture(models.Model):
    id_detail = models.AutoField(primary_key=True, db_column="id_detail")
    id_facture = models.IntegerField(blank=True, null=True)
    id_client = models.IntegerField(blank=True, null=True)
    article = models.TextField(blank=True, null=True)
    prix_unitaire = models.TextField(blank=True, null=True)
    nombre = models.TextField(blank=True, null=True)
    montant = models.FloatField(default=0, blank=True, null=True)
    id_societe = models.IntegerField(default=1)
    id_article = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "detail_facture"


class Depense(models.Model):
    """Sortie de caisse (dépense) : nom de la personne, objet, montant."""
    id_depense = models.AutoField(primary_key=True)
    date_depense = models.DateField()
    nom = models.CharField(max_length=250)
    objet = models.CharField(max_length=250)
    montant = models.FloatField(default=0)
    id_societe = models.IntegerField(default=1)
    id_user = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "depense"

    def __str__(self):
        return f"{self.nom} - {self.objet}"


class FacturesArchive(models.Model):
    """Factures soldées archivées (déplacées hors de `factures`)."""
    id_facture = models.AutoField(primary_key=True)
    id_client = models.IntegerField(blank=True, null=True)
    date_facture = models.DateField(blank=True, null=True)
    id_societe = models.IntegerField(default=1)
    numero_facture = models.CharField(max_length=100, blank=True, null=True)
    montant_facture = models.FloatField(default=0, blank=True, null=True)
    montpaye = models.FloatField(default=0, blank=True, null=True)
    etat_facture = models.IntegerField(default=0, blank=True, null=True)
    heure_facture = models.CharField(max_length=20, blank=True, null=True)
    date_echeance = models.DateField(blank=True, null=True)
    remise = models.FloatField(default=0, blank=True, null=True)
    date_archivage = models.DateField(blank=True, null=True)
    annee_archive = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "factures_archive"


class DetailFactureArchive(models.Model):
    id_detail = models.AutoField(primary_key=True, db_column="id_detail")
    id_facture = models.IntegerField(blank=True, null=True)
    id_client = models.IntegerField(blank=True, null=True)
    article = models.TextField(blank=True, null=True)
    prix_unitaire = models.TextField(blank=True, null=True)
    nombre = models.TextField(blank=True, null=True)
    montant = models.FloatField(default=0, blank=True, null=True)
    id_societe = models.IntegerField(default=1)
    id_article = models.TextField(blank=True, null=True)
    date_archivage = models.DateField(blank=True, null=True)
    annee_archive = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "detail_facture_archive"


class Marquage(models.Model):
    id_marquage = models.AutoField(primary_key=True)
    id_article = models.IntegerField(blank=True, null=True)
    numero_facture = models.CharField(max_length=100, blank=True, null=True)
    id_couture = models.IntegerField(blank=True, null=True)
    date_couture = models.DateField(blank=True, null=True)
    id_brodeur = models.IntegerField(blank=True, null=True)
    date_broderie = models.DateField(blank=True, null=True)
    id_bouton = models.IntegerField(blank=True, null=True)
    date_bouton = models.DateField(blank=True, null=True)
    etat = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "marquage"


class Tailleur(models.Model):
    id_tailleur = models.AutoField(primary_key=True)
    prenom_nom = models.CharField(max_length=255, blank=True, null=True)
    type_tailleur = models.CharField(max_length=100, blank=True, null=True)
    id_societe = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "tailleur"

    def __str__(self):
        return self.prenom_nom or str(self.id_tailleur)


class Tarification(models.Model):
    id_tarification = models.AutoField(primary_key=True, db_column="id_tarification")
    id_modele = models.IntegerField(blank=True, null=True)
    tarif_simple = models.FloatField(default=0, blank=True, null=True)
    tarif_brodeur = models.FloatField(default=0, blank=True, null=True)
    tarif_bouton = models.FloatField(default=0, blank=True, null=True)
    id_societe = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = "tarification"
