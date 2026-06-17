UrbanHub — Plateforme de jumeau numérique urbain


Plateforme d'ingestion, de traitement et d'analyse de données multi-sources pour villes intelligentes (Smart City).




Présentation du projet

UrbanHub est un jumeau numérique urbain capable d'observer et d'analyser le fonctionnement d'une ville moderne à partir de trois types de flux de données :

FluxSourceTypeMétéorologiqueNOAA Global Hourly Weather DataBatchMobilité urbaine (vélos)CityBikes APIStreamingPollution atmosphériqueOpenAQ APIIoT


Architecture

Sources de données (NOAA, CityBikes, OpenAQ)
      │
      ▼
Ingestion (API / download / streaming)
      │
      ▼
MinIO Bronze Bucket (urbanhub-bronze/ - Données brutes)
      │
      ▼
MinIO Silver Bucket (urbanhub-silver/ - Nettoyage, normalisation Parquet)
      │
      ▼
MinIO Gold Bucket (urbanhub-gold/ - Agrégations, croisement Parquet)
      │
      ▼
Analyse & Visualisations (notebooks/ & visualisations/)


Structure du dépôt

urbanhub/
├── docker-compose.yml           # Configuration MinIO S3
├── .env.example                 # Modèle de variables d'environnement
├── .env                         # Configuration locale (MinIO & clés API)
├── requirements.txt             # Dépendances Python
├── README.md                    # Documentation du dépôt
│
├── data/                        # Données locales (non versionné)
├── logs/                        # Logs d'exécution (non versionné)
│   ├── pipeline.log
│   └── errors.log
│
├── notebooks/                   # Analyses exploratoires et restitution
│   ├── notebook_meteo.ipynb
│   ├── notebook_velos.ipynb
│   ├── notebook_pollution.ipynb
│   └── notebook_croise.ipynb
│
├── src/                         # Scripts de pipeline de données
│   ├── common/                  # Code transverse et configurations
│   │   ├── config.py
│   │   ├── minio_client.py
│   │   ├── logging_utils.py
│   │   └── geo_utils.py
│   │
│   ├── meteo/                   # Membre A — NOAA Batch
│   │   ├── download_noaa.py
│   │   ├── clean_meteo.py
│   │   └── aggregate_meteo.py
│   │
│   ├── velos/                   # Membre B — CityBikes Streaming
│   │   ├── collect_velos.py
│   │   ├── clean_velos.py
│   │   └── aggregate_velos.py
│   │
│   ├── pollution/               # Membre C — OpenAQ IoT
│   │   ├── collect_pollution.py
│   │   ├── clean_pollution.py
│   │   └── aggregate_pollution.py
│   │
│   └── cross/                   # Tous — Analyse Croisée
│       └── merge_datasets.py
│
├── visualisations/              # Exports de figures et cartes
└── docs/                        # Spécifications et rapports de synthèse
    ├── schemas.md
    └── rapport_final.md


Installation

Prérequis


Python 3.10+
Git


Cloner le dépôt

bashgit clone https://github.com/<votre-org>/urbanhub.git
cd urbanhub

Installer les dépendances

bashpip install -r requirements.txt

Configurer les variables d'environnement

bashcp .env.example .env
# Remplir les clés API dans .env


Utilisation

Partie 1 — Flux Batch (Météo NOAA)

```bash
python src/meteo/download_noaa.py   # Téléchargement parallèle des stations françaises
python src/meteo/clean_meteo.py      # Nettoyage et conversion des données vers Silver
python src/meteo/aggregate_meteo.py  # Calcul des agrégats météo vers Gold
```

Partie 2 — Flux Streaming (CityBikes)

```bash
python src/velos/collect_velos.py    # Collecte en temps réel du snapshot vers Bronze
python src/velos/clean_velos.py       # Extraction et formatage vers Silver
python src/velos/aggregate_velos.py   # Calcul des taux d'usage vers Gold
```

Partie 3 — Flux IoT (OpenAQ)

```bash
python src/pollution/collect_pollution.py   # Ingestion régulière simulant un flux IoT
python src/pollution/clean_pollution.py       # Nettoyage et structuration vers Silver
python src/pollution/aggregate_pollution.py   # Dépassements de seuils vers Gold
```

Analyses exploratoires

Lancer JupyterLab et ouvrir les notebooks dans l'ordre :

bashjupyter lab


Questions métier traitées

Météo (Partie 1)


Identification de périodes météorologiques anormales
Corrélation entre conditions météo et visibilité
Évolution saisonnière des températures en France
Jours présentant des conditions météorologiques extrêmes


Mobilité vélos (Partie 2)


Stations avec le plus fort taux d'utilisation
Zones où l'offre de vélos est insuffisante
Pics d'utilisation journaliers
Déséquilibres géographiques de disponibilité
Stations critiques nécessitant un rééquilibrage


Pollution (Partie 3)


Zones avec les niveaux de pollution les plus élevés
Variation journalière de la pollution
Polluants dominants par ville (PM2.5, PM10, NO2, O3, CO)
Épisodes de pollution anormale


Analyse croisée (Partie 4)


Relation entre conditions météo et pollution
Influence de la météo sur l'utilisation des vélos
Conditions météo favorables à la mobilité douce
Périodes d'interaction forte entre mobilité, pollution et météo



Données

| Source | Période | Format de stockage |
| --- | --- | --- |
| NOAA Global Hourly | 5 dernières années | Parquet Snappy, Bucket Silver & Gold |
| CityBikes API | Temps réel (à partir du collecteur) | JSON dans Bronze, Parquet dans Silver & Gold |
| OpenAQ API | Collecte en continu (France) | JSON dans Bronze, Parquet dans Silver & Gold |


Variables extraites

<details>
<summary>Météo (NOAA)</summary>
station_id · timestamp · temperature · wind_speed · wind_direction · pressure · visibility · precipitation

</details>
<details>
<summary>Vélos (CityBikes)</summary>
station_id · station_name · latitude · longitude · bikes_available · free_slots · timestamp

</details>
<details>
<summary>Pollution (OpenAQ)</summary>
sensor_id · pollutant · value · unit · latitude · longitude · timestamp

</details>

Workflow Git

bash# Créer sa branche de travail
git checkout -b feature/batch-meteo

# Travailler, puis commiter
git add .
git commit -m "feat: ajout script téléchargement NOAA parallèle"

# Pousser et ouvrir une pull request
git push origin feature/batch-meteo

Convention de nommage des branches :


feature/meteo — Membre A
feature/velos — Membre B
feature/pollution — Membre C
feature/analyse-croisee — tous


Convention de commits :


feat: nouvelle fonctionnalité
fix: correction de bug
data: ajout ou modification de pipeline de données
docs: documentation
refactor: refactoring sans changement fonctionnel



| Membre | Rôle | Flux associés |
| --- | --- | --- |
| Membre A | Data Engineer – Batch | Météo NOAA |
| Membre B | Data Engineer – Streaming | Vélos CityBikes |
| Membre C | Data Engineer – IoT | Pollution OpenAQ |


Licence

Projet académique — usage interne uniquement.
