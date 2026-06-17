# Spécification des Schémas de Données - UrbanHub

Ce document décrit les schémas de données pour les différentes couches (Bronze, Silver, Gold) des flux traités par le **Rôle 3** (Pollution atmosphérique OpenAQ & Analyses Croisées).

---

## 1. Flux Pollution (OpenAQ)

### Couche Bronze (Raw Snapshots)
* **Format** : JSON
* **Chemin MinIO** : `urbanhub-bronze/pollution/date=YYYY-MM-DD/snapshots_HHMMSS.json`
* **Contenu** : Réponse brute de l'API OpenAQ v3 contenant les informations géographiques des stations (`locations`) et les mesures horaires associées pour les capteurs (`sensors`).

### Couche Silver (Cleaned Table)
* **Format** : Parquet (Snappy compression)
* **Chemin MinIO** : `urbanhub-silver/pollution/city=CITY/date=YYYY-MM-DD/data_snapshots_HHMMSS.parquet`
* **Schéma** :
  | Colonne | Type | Description |
  | --- | --- | --- |
  | `sensor_id` | String | Identifiant unique du capteur OpenAQ |
  | `pollutant` | String | Nom normalisé du polluant (`pm25`, `pm10`, `no2`, `o3`, `co`) |
  | `value` | Float | Valeur numérique de la mesure |
  | `unit` | String | Unité physique de la mesure (ex: `µg/m³`) |
  | `latitude` | Float | Latitude géographique de la station de mesure |
  | `longitude` | Float | Longitude géographique de la station de mesure |
  | `timestamp` | String (ISO 8601 UTC) | Date et heure de la mesure |
  | `city` | String | Nom normalisé de la ville la plus proche |

### Couche Gold (Daily Aggregates)
* **Format** : Parquet (Snappy compression)
* **Chemin MinIO** : `urbanhub-gold/pollution/city=CITY/daily_aggregates.parquet`
* **Schéma** :
  | Colonne | Type | Description |
  | --- | --- | --- |
  | `date` | Date | Date locale de l'agrégation |
  | `city` | String | Ville d'observation |
  | `avg_pm25` | Float | Concentration moyenne journalière en PM2.5 (µg/m³) |
  | `avg_pm10` | Float | Concentration moyenne journalière en PM10 (µg/m³) |
  | `avg_no2` | Float | Concentration moyenne journalière en NO2 (µg/m³) |
  | `avg_o3` | Float | Concentration moyenne journalière en O3 (µg/m³) |
  | `avg_co` | Float | Concentration moyenne journalière en CO (µg/m³) |
  | `pollution_episode_flag` | Boolean | `True` si un polluant dépasse son seuil limite journalier |

---

## 2. Flux Croisé (Gold Cross-analysis)

* **Format** : Parquet (Snappy compression)
* **Chemin MinIO** : `urbanhub-gold/cross/city=CITY/merged_daily.parquet`
* **Schéma** :
  | Colonne | Type | Source | Description |
  | --- | --- | --- | --- |
  | `date` | Date | Tous | Date locale commune de jointure |
  | `city` | String | Tous | Ville d'observation |
  | `avg_pm25` | Float | Pollution | Moyenne journalière PM2.5 (µg/m³) |
  | `avg_pm10` | Float | Pollution | Moyenne journalière PM10 (µg/m³) |
  | `avg_no2` | Float | Pollution | Moyenne journalière NO2 (µg/m³) |
  | `avg_o3` | Float | Pollution | Moyenne journalière O3 (µg/m³) |
  | `avg_co` | Float | Pollution | Moyenne journalière CO (µg/m³) |
  | `pollution_episode_flag` | Boolean | Pollution | Indicateur d'épisode de pollution |
  | `avg_temperature` | Float | Météo | Température moyenne journalière (°C) |
  | `max_temperature` | Float | Météo | Température maximale journalière (°C) |
  | `min_temperature` | Float | Météo | Température minimale journalière (°C) |
  | `avg_wind_speed` | Float | Météo | Vitesse moyenne du vent (m/s) |
  | `max_wind_speed` | Float | Météo | Vitesse maximale du vent (m/s) |
  | `avg_pressure` | Float | Météo | Pression atmosphérique moyenne (hPa) |
  | `avg_visibility` | Float | Météo | Visibilité moyenne (m) |
  | `is_extreme_hot` | Boolean | Météo | Indicateur de jour de forte chaleur |
  | `is_extreme_cold` | Boolean | Météo | Indicateur de jour de gel / grand froid |
  | `is_extreme_wind` | Boolean | Météo | Indicateur de vent fort |
  | `temp_anomaly` | Float | Météo | Écart de température par rapport à la normale |
  | `avg_usage_pressure` | Float | Vélos | Pression moyenne d'usage des stations vélos |
  | `critical_stations_count` | Integer | Vélos | Nombre de stations saturées ou vides dans la journée |
