UrbanHub — Plateforme de jumeau numérique urbain


Plateforme d'ingestion, de traitement et d'analyse de données multi-sources pour villes intelligentes (Smart City).




Présentation du projet

UrbanHub est un jumeau numérique urbain capable d'observer et d'analyser le fonctionnement d'une ville moderne à partir de trois types de flux de données :

FluxSourceTypeMétéorologiqueNOAA Global Hourly Weather DataBatchMobilité urbaine (vélos)CityBikes APIStreamingPollution atmosphériqueOpenAQ APIIoT


Architecture

Sources de données
      │
      ▼
Ingestion (API / Scraping / Download)
      │
      ▼
Stockage Data Lake (data/raw/)
      │
      ▼
Traitement Data Engineering (data/processed/)
      │
      ▼
Analyse & Visualisations (notebooks/)
      │
      ▼
Indicateurs urbains (reports/)


Structure du dépôt

urbanhub/
├── README.md
├── .gitignore
├── requirements.txt
├── .env.example
│
├── data/                        ← non versionné (.gitignore)
│   ├── raw/
│   │   ├── meteo/
│   │   ├── velos/
│   │   └── pollution/
│   └── processed/
│       ├── meteo/
│       ├── velos/
│       └── pollution/
│
├── notebooks/
│   ├── 01_batch_meteo.ipynb
│   ├── 02_streaming_velos.ipynb
│   ├── 03_iot_pollution.ipynb
│   └── 04_analyse_croisee.ipynb
│
├── src/
│   ├── batch/                   ← Membre A — NOAA
│   │   ├── download.py
│   │   └── clean.py
│   ├── streaming/               ← Membre B — CityBikes
│   │   ├── collector.py
│   │   └── clean.py
│   ├── iot/                     ← Membre C — OpenAQ
│   │   ├── ingestion.py
│   │   └── clean.py
│   └── utils/
│       ├── storage.py
│       └── helpers.py
│
└── reports/
    ├── figures/
    └── rapport_final.pdf


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

bashpython src/batch/download.py   # Téléchargement parallèle des stations françaises
python src/batch/clean.py      # Nettoyage et conversion des données

Partie 2 — Flux Streaming (CityBikes)

bashpython src/streaming/collector.py   # Collecte automatique toutes les minutes
python src/streaming/clean.py       # Traitement des snapshots

Partie 3 — Flux IoT (OpenAQ)

bashpython src/iot/ingestion.py   # Ingestion régulière simulant un flux IoT
python src/iot/clean.py       # Nettoyage et structuration

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

Les données brutes et traitées ne sont pas versionnées (fichiers trop volumineux).

SourcePériodeFormat stockageNOAA Global Hourly5 dernières annéesParquet, partitionné par année/stationCityBikes APIDepuis le déploiementCSV horodaté, partitionné par jourOpenAQ APICollecte en continuParquet, partitionné par polluant/ville/date


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


feature/batch-meteo — Membre A
feature/streaming-velos — Membre B
feature/iot-pollution — Membre C
feature/analyse-croisee — tous


Convention de commits :


feat: nouvelle fonctionnalité
fix: correction de bug
data: ajout ou modification de pipeline de données
docs: documentation
refactor: refactoring sans changement fonctionnel



Équipe

MembreRôleFluxMembre AData Engineer – BatchMétéo NOAAMembre BData Engineer – StreamingCityBikesMembre CData Engineer – IoTOpenAQ


Licence

Projet académique — usage interne uniquement.
