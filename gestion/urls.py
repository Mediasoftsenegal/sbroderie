from django.urls import path

from . import views

urlpatterns = [
    # Authentification
    path("", views.index, name="index"),
    path("access/", views.access, name="access"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),

    # Tableau de bord & calendrier
    path("tableau-de-bord/", views.dashboard, name="dashboard"),
    path("calendrier/", views.calendrier, name="calendrier"),
    path("calendrier/export.ics", views.calendrier_ics, name="calendrier_ics"),

    # Clients & mesures
    path("clients/", views.clients, name="clients"),
    path("clients/ajouter/", views.client_insert, name="client_insert"),
    path("clients/<int:id_client>/modifier/", views.client_modif, name="client_modif"),
    path("clients/<int:id_client>/supprimer/", views.client_supp, name="client_supp"),
    path("mesures/", views.mesures, name="mesures"),
    path("mesures/ajouter/", views.ajout_mesure, name="ajout_mesure_new"),
    path("mesures/ajouter/<int:id_client>/", views.ajout_mesure, name="ajout_mesure"),
    path("mesures/enregistrer/", views.mesure_insert, name="mesure_insert"),
    path("mesures/<int:id_mesure>/modifier/", views.mesure_modif, name="mesure_modif"),

    # Articles & modèles
    path("articles/", views.articles, name="articles"),
    path("articles/ajouter/", views.article_insert, name="article_insert"),
    path("articles/<int:codep>/modifier/", views.article_modif, name="article_modif"),
    path("articles/<int:codep>/supprimer/", views.article_supp, name="article_supp"),
    path("modeles/", views.modeles, name="modeles"),
    path("modeles/ajouter/", views.modele_insert, name="modele_insert"),

    # Panier -> facturation
    path("panier/", views.panier_client, name="panier_client"),
    path("panier/<int:id_client>/produits/", views.panier_produit, name="panier_produit"),
    path("panier/<int:id_client>/ajouter/<int:codep>/", views.panier_add, name="panier_add"),
    path("panier/<int:id_client>/retirer/<int:codep>/", views.panier_del, name="panier_del"),
    path("panier/<int:id_client>/voir/", views.panier_voir, name="panier_voir"),
    path("facture/info/", views.facture_info, name="facture_info"),
    path("facture/creer/", views.facture_creer, name="facture_creer"),
    path("facture/<int:id_facture>/details/", views.facture_details, name="facture_details"),
    path("facture/<int:id_facture>/pdf/", views.facture_pdf, name="facture_pdf"),
    path("facture/<int:id_facture>/pdf-sans-mesures/", views.facture_pdf_sans_mesures,
         name="facture_pdf_sans_mesures"),
    path("facture/<int:id_facture>/whatsapp/", views.facture_whatsapp, name="facture_whatsapp"),

    # Facturation (suivi)
    path("facturation/", views.facturation, name="facturation"),
    path("indicateur/", views.indicateur, name="indicateur"),
    path("etat/", views.etat, name="etat"),
    path("etat/<str:numero_facture>/modifier/", views.modif_etat, name="modif_etat"),
    path("regularisation/", views.regularisation, name="regularisation"),
    path("regularisation/valider/", views.regularisation_valider, name="regularisation_valider"),
    path("regularisation/corriger/", views.regularisation_corriger, name="regularisation_corriger"),
    path("regularisation/supprimer/", views.regularisation_supprimer, name="regularisation_supprimer"),
    path("regularisation/etat/", views.regularisation_etat, name="regularisation_etat"),
    path("regularisation/archiver/", views.regularisation_archiver, name="regularisation_archiver"),
    path("regularisation/archives/", views.regularisation_archives, name="regularisation_archives"),
    path("rvsemaine/", views.rvsemaine, name="rvsemaine"),
    path("mensuel/", views.mensuel, name="mensuel"),

    # Caisse
    path("caisse/", views.caisse, name="caisse"),
    path("caisse/acompte/", views.caisse_acompte, name="caisse_acompte"),
    path("caisse/acompte/<str:numero_facture>/", views.caisse_ajout_ac, name="caisse_ajout_ac"),
    path("caisse/action/", views.caisse_fonction, name="caisse_fonction"),
    path("caisse/journal/", views.caisse_journal, name="caisse_journal"),
    path("caisse/depense/ajouter/", views.depense_insert, name="depense_insert"),
    path("caisse/depense/<int:id_depense>/supprimer/", views.depense_supp, name="depense_supp"),

    # Comptabilité
    path("finance/", views.finance, name="finance"),

    # Marquage
    path("marquage/", views.marquage, name="marquage"),
    path("marquage/<int:id_marquage>/<str:phase>/", views.marquage_detail, name="marquage_detail"),
    path("marquage/enregistrer/", views.marquage_update, name="marquage_update"),
    path("tailleur/", views.tailleur, name="tailleur"),
    path("tailleur/ajouter/", views.tailleur_insert, name="tailleur_insert"),
    path("tarif/", views.tarif, name="tarif"),
    path("tarif/ajouter/", views.tarif_insert, name="tarif_insert"),
    path("honoraire/", views.honoraire, name="honoraire"),

    # Paramètres
    path("profil/", views.profil, name="profil"),
    path("profil/ajouter/", views.profil_insert, name="profil_insert"),
    path("utilisateur/", views.utilisateur, name="utilisateur"),
    path("utilisateur/ajouter/", views.utilisateur_insert, name="utilisateur_insert"),
    path("utilisateur/<int:id_user>/mot-de-passe/", views.utilisateur_mot_de_passe,
         name="utilisateur_mot_de_passe"),
]
