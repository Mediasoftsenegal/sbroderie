# Sénégal Broderie Moderne — Version Django

Portage en **Python / Django** de l'application PHP de gestion de couture, en
conservant les mêmes fonctionnalités et la **même base de données MySQL**
(mêmes paramètres de connexion). Aucune migration de données n'est nécessaire :
Django lit et écrit directement les tables existantes.

---

## 1. Ce qui a été porté

| Module PHP | Équivalent Django | Fonctions |
|---|---|---|
| `index.php` / `access.php` | `index`, `access` | Connexion, redirection par profil |
| `admin/gerant/client` | `clients`, `mesures` | Clients (CRUD) + mesures |
| `admin/articles` | `articles`, `modeles` | Articles & modèles |
| `admin/panier` | `panier_*` | Panier en 4 étapes (session) |
| `admin/facture` | `facture_*`, `facturation`, `etat`, `indicateur`, `mensuel`, `rvsemaine` | Facturation + **PDF** |
| `admin/caisse` | `caisse`, `caisse_acompte`, `caisse_fonction` | Caisse & acomptes |
| `admin/comptable` | `finance` | Comptabilité (période) |
| `admin/marquage` | `marquage`, `tailleur`, `tarif`, `honoraire` | Suivi de production |
| `admin/param` | `profil`, `utilisateur` | Profils & utilisateurs |

Les profils/redirections sont identiques : 1=Admin, 2=Gérant, 3=Caissier,
4=Comptable, 5=Marquage. Le rendu visuel réutilise le thème **SB Admin 2**
(mêmes CSS/JS/vendor). La facture PDF reprend l'en-tête société d'origine.

---

## 2. Paramètres de connexion à la base

Identiques à l'application PHP (dans `sbroderie/settings.py`, surchageables
par variables d'environnement) :

```
Base : mediapla_sb
User : mediapla
Hôte : localhost
```

> Le mot de passe est repris tel quel par défaut. **En production, définissez-le
> via les variables d'environnement cPanel** (voir `.env.example`) et ne le
> laissez pas en clair dans le code.

---

## 3. Déploiement sur cPanel (Setup Python App)

cPanel propose « **Setup Python App** » (Passenger). Étapes :

1. **Téléverser le projet**
   - Compressez ce dossier et téléversez-le, par ex. dans
     `/home/VOTRE_COMPTE/sbroderie_django` (via le Gestionnaire de fichiers ou Git).

2. **Créer l'application Python**
   - cPanel → *Setup Python App* → *Create Application*.
   - Version Python : **3.8+** (3.10/3.11 recommandé).
   - *Application root* : `sbroderie_django`
   - *Application URL* : votre domaine ou sous-domaine.
   - *Application startup file* : `passenger_wsgi.py`
   - *Application Entry point* : `application`

3. **Variables d'environnement** (section *Environment variables*)
   Ajoutez celles de `.env.example` :
   `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`,
   `DJANGO_CSRF_TRUSTED`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

4. **Installer les dépendances**
   - Ouvrez le terminal fourni par cPanel (la commande exacte
     `source /home/.../virtualenv/.../bin/activate` est affichée par cPanel), puis :
   ```bash
   pip install -r requirements.txt
   ```

5. **Fichiers statiques**
   ```bash
   python manage.py collectstatic --noinput
   ```
   Les assets seront rassemblés dans `staticfiles/`. Sur la plupart des offres
   cPanel, servez-les via un lien symbolique ou en configurant `STATIC_ROOT`
   vers `public_html/static`. Réglage simple : après `collectstatic`, copiez/liez
   `staticfiles/` vers un dossier `static` accessible du domaine.

6. **Redémarrer l'application** (bouton *Restart* dans *Setup Python App*).

7. **Vérifier** : ouvrez votre domaine → page de connexion. Connectez-vous avec
   un compte existant de la table `user`.

---

## 4. Vérifier le schéma avec `inspectdb` (recommandé)

Les modèles (`gestion/models.py`) ont été déduits du code PHP. Pour garantir une
correspondance exacte avec VOTRE base (noms de colonnes, clés primaires), lancez
une fois sur le serveur :

```bash
python manage.py inspectdb > modeles_reels.py
```

Comparez `modeles_reels.py` à `gestion/models.py`. Si une **clé primaire**
diffère (ex. `detail_facture`, `tarification`), ajustez `primary_key=True` /
`db_column` dans `gestion/models.py`. Tous les modèles sont en `managed = False`
donc Django ne modifiera jamais vos tables.

---

## 5. Lancer en local (test)

```bash
pip install -r requirements.txt
# Renseignez les variables DB_* de votre base de test, puis :
python manage.py runserver
```

Ouvrez http://127.0.0.1:8000/

---

## 6. Notes de sécurité

- L'application d'origine stockait les **mots de passe en clair**. Pour rester
  compatible avec la base existante, l'authentification les compare directement,
  tout en **supportant aussi les hachages Django** si vous décidez de les migrer.
- Les requêtes ont été **paramétrées** (protection contre l'injection SQL, qui
  était présente dans le code PHP d'origine).
- Passez `DJANGO_DEBUG=False` en production et renseignez `DJANGO_ALLOWED_HOSTS`
  et `DJANGO_CSRF_TRUSTED` avec votre domaine.

---

## 7. Arborescence

```
sbroderie_django/
├── passenger_wsgi.py        # point d'entrée cPanel/Passenger
├── manage.py
├── requirements.txt
├── .env.example             # variables d'environnement à définir sur cPanel
├── sbroderie/               # configuration du projet
│   ├── settings.py          # connexion DB (mêmes paramètres que le PHP)
│   ├── urls.py / wsgi.py
│   └── __init__.py          # active PyMySQL
├── gestion/                 # application
│   ├── models.py            # tables existantes (managed=False)
│   ├── views.py             # logique des pages
│   ├── urls.py
│   ├── auth.py              # connexion/session/rôles
│   ├── pdf.py               # facture PDF (fpdf2)
│   ├── utils.py             # format FCFA + chiffres en lettres
│   ├── context_processors.py
│   ├── templatetags/fcfa.py
│   └── templates/gestion/   # pages (thème SB Admin 2)
└── static/                  # CSS/JS/vendor/img repris de l'app PHP
```

## 8. Nouveautés — Tableau de bord & Calendrier

**Tableau de bord** (`/tableau-de-bord/`, accès Admin/Gérant/Comptable, page
d'accueil par défaut) :
- Indicateurs : nombre de factures payées / impayées, total facturé, total
  encaissé, reste à encaisser.
- Graphique des **montants facturés vs encaissés** sur 12 mois.
- Répartition **payées / impayées** (anneau).
- **Nombre de commandes par client** pour le mois en cours.

**Calendrier des rendez-vous** (`/calendrier/`) :
- Chaque facture a une **date de livraison = date de facture + 21 jours**.
- Vue mensuelle (navigation mois précédent/suivant) affichant les livraisons,
  en attente (orange) ou soldées (vert).
- Panneau « Prochaines livraisons » (30 jours), avec compte à rebours.
- **Export .ics** (bouton) importable dans Google Agenda / Outlook, avec rappel
  automatique 1 jour avant chaque livraison.

Les graphiques utilisent Chart.js (déjà inclus dans le thème). Aucune
dépendance supplémentaire, aucune modification de la base de données.

## 9. IMPORTANT — Ne pas lancer `migrate` (erreur 1142 CREATE denied)

Tous les modèles sont en `managed = False` et pointent vers vos **tables
existantes**. Le projet **ne doit jamais** exécuter `makemigrations` ni
`migrate` : ces commandes tentent de créer la table interne
`django_migrations`, ce que l'utilisateur MySQL (droits données uniquement,
sans `CREATE`) refuse :

```
(1142, "CREATE command denied to user 'mediapla'@'localhost' for table 'django_migrations'")
```

Ce comportement est normal sur hébergement mutualisé et sans danger : au
fonctionnement, l'application ne fait que des SELECT/INSERT/UPDATE/DELETE sur
les tables déjà présentes.

**Que faire :**
1. Si vous avez déjà généré une migration par erreur, supprimez-la
   (gardez `__init__.py`) :
   - Windows : `del gestion\migrations\0001_initial.py`
   - Linux/macOS : `rm gestion/migrations/0001_initial.py`
2. Ne lancez **jamais** `makemigrations` / `migrate`.
3. Démarrez directement l'application :
   - En local : `python manage.py runserver`
   - Sur cPanel : via *Setup Python App* (Passenger), bouton *Restart*.
4. Connectez-vous avec un utilisateur existant de la table `user`.

Le réglage `MIGRATION_MODULES = {"gestion": None}` (dans `settings.py`) neutralise
déjà ces commandes : `migrate` affichera « No migrations to apply » et
`makemigrations` « No changes detected ».

**Test en local** : pointez les variables `DB_*` vers une base MySQL locale
(ou activez *Remote MySQL* sur cPanel en ajoutant votre IP), puis `runserver`.
La page de connexion s'affiche même sans base ; les autres pages nécessitent
l'accès aux tables.

## 10. Correctifs d'alignement au schéma réel

- La clé primaire réelle de `detail_facture` est **`id_detail`** (et non
  `id_detail_facture`) : corrigé dans le modèle `DetailFacture`.
- La table `tarification` n'expose pas de clé primaire dans le code PHP ;
  elle n'est utilisée qu'en SQL brut / `create()`, donc sans incidence. Si
  une page de tarifs échouait un jour sur *Unknown column*, lancez
  `python manage.py inspectdb tarification` et ajustez le modèle.

- La table `client` réelle **n'a pas** de colonne `etat` : le champ a été retiré
  du modèle `Client`, la liste n'effectue plus de filtre `etat`, et la
  suppression d'un client est désormais une suppression réelle
  (`DELETE`) au lieu d'un `UPDATE etat=0` (qui échouait déjà côté PHP).
- Les autres tables ont été vérifiées d'après les `INSERT` du code PHP et
  correspondent au modèle. La seule table non recoupée automatiquement est
  `marquage` : si une page « Marquage » renvoie une erreur *Unknown column*,
  lancez `python manage.py inspectdb marquage` et envoyez le résultat pour
  aligner le modèle (ou ajustez `gestion/models.py`).

## 11. Fichiers statiques (CSS/JS/images) — WhiteNoise

Les fichiers statiques sont servis par **WhiteNoise**, intégré à l'application.
Avantage : ils fonctionnent en local **et** sur cPanel, que `DEBUG` soit vrai ou
faux, sans configuration Apache/alias.

- Installez la dépendance (déjà dans `requirements.txt`) :
  `pip install -r requirements.txt`
- En **local**, rien d'autre à faire : grâce à `WHITENOISE_USE_FINDERS`, les
  fichiers sont servis directement depuis le dossier `static/`.
- En **production (cPanel)**, lancez une fois :
  `python manage.py collectstatic --noinput`
  (rassemble et compresse les fichiers dans `staticfiles/`, ce qui supprime aussi
  l'avertissement « No directory at staticfiles/ »).

Si vous voyiez auparavant des erreurs 404 sur `/static/...`, c'était parce que
`runserver` ne sert les statiques que si `DEBUG=True` ; WhiteNoise règle
définitivement ce point.

## 12. MySQL strict — erreur ONLY_FULL_GROUP_BY

Sur un MySQL 5.7/8.0 récent, le mode `ONLY_FULL_GROUP_BY` est actif par défaut
et rejette les `GROUP BY` « à l'ancienne » utilisés par l'application (héritée du
PHP), avec l'erreur :

```
(1055, "... incompatible with sql_mode=only_full_group_by")
```

C'est réglé de deux façons complémentaires :

1. Les requêtes concernées (facturation, indicateur, état, mensuel, RV, acompte)
   ont été **réécrites** pour être conformes : une ligne par numéro de facture
   (ligne d'origine via `MIN(id_facture)`) + sommes agrégées. Cela fonctionne
   quel que soit le `sql_mode` du serveur, et corrige aussi l'affichage quand une
   facture a des acomptes.
2. En filet de sécurité, la connexion fixe un mode SQL sans `ONLY_FULL_GROUP_BY`
   dans `settings.py` :

```python
"init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'"
```

## 13. Nouveaux profils : Invité et Commercial

Deux profils ont été ajoutés :

- **Invité** : consultation **uniquement des factures** (liste Facturation,
  détail d'une facture et PDF). Toute autre page le renvoie vers la liste des factures.
- **Commercial** : tableau de bord, calendrier RV, clients, mesures, articles,
  modèles, nouvelle facture, facturation et caisse (+ acompte). Les pages marquage,
  comptabilité, suivi (état/indicateur/mensuel) et paramètres lui sont interdites.

**La reconnaissance se fait par le NOM du profil** (robuste aux identifiants).
Il suffit donc de créer deux profils nommés exactement **« Invité »** et
**« Commercial »** via *Paramètres → Profils* (peu importe l'id attribué), puis de
créer les utilisateurs via *Paramètres → Utilisateurs* en choisissant le bon profil.

Noms reconnus (insensible à la casse et aux accents) : Administrateur/Admin,
Gérant, Caisse/Caissier, Comptable/Finance, Marquage, Invité/Guest, Commercial.
Si un profil porte un autre nom, l'application retombe sur son identifiant
numérique (1..7) comme avant.

Au passage, l'accès est désormais **contrôlé côté serveur pour chaque page**
(auparavant seul le menu était masqué) : un utilisateur ne peut plus atteindre une
page interdite en tapant l'URL directement.
