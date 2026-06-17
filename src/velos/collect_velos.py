import json
import time
import requests
from datetime import datetime, timezone

from src.common.config import CITYBIKES_URL, BUCKET_BRONZE, COLLECT_INTERVAL_SECONDS
from src.common.minio_client import upload_bytes, init_buckets
from src.common.logging_utils import log_info, log_error

# Villes françaises à surveiller
VILLES_FR = [
    "paris",
    "lyon",
    "bordeaux",
    "lille",
    "marseille",
    "nantes",
    "toulouse",
    "rennes",
]


def get_reseaux_france() -> list:
    """Récupère la liste des réseaux vélos situés en France."""
    try:
        response = requests.get(f"{CITYBIKES_URL}/networks", timeout=10)
        response.raise_for_status()
        networks = response.json()["networks"]

        reseaux_fr = [
            n for n in networks
            if n.get("location", {}).get("country", "").upper() == "FR"
        ]

        log_info(f"{len(reseaux_fr)} réseaux trouvés en France")
        return reseaux_fr

    except Exception as e:
        log_error(f"Erreur récupération réseaux : {e}")
        return []


def get_stations_reseau(reseau_id: str) -> list:
    """Récupère les stations d'un réseau donné."""
    try:
        response = requests.get(f"{CITYBIKES_URL}/networks/{reseau_id}", timeout=10)
        response.raise_for_status()
        return response.json()["network"]["stations"]

    except Exception as e:
        log_error(f"Erreur récupération stations ({reseau_id}) : {e}")
        return []


def collecter_snapshot(reseaux: list):
    """
    Collecte un snapshot de toutes les stations françaises
    et l'envoie dans MinIO Bronze.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    toutes_stations = []

    for reseau in reseaux:
        reseau_id   = reseau["id"]
        reseau_nom  = reseau["name"]
        ville       = reseau.get("location", {}).get("city", "inconnue")

        stations = get_stations_reseau(reseau_id)

        for s in stations:
            toutes_stations.append({
                "station_id"     : s.get("id"),
                "station_name"   : s.get("name"),
                "latitude"       : s.get("latitude"),
                "longitude"      : s.get("longitude"),
                "bikes_available": s.get("free_bikes"),
                "free_slots"     : s.get("empty_slots"),
                "reseau"         : reseau_nom,
                "ville"          : ville,
                "timestamp"      : timestamp,
            })

    if not toutes_stations:
        log_error("Aucune station collectée dans ce snapshot")
        return

    # Sérialise en JSON et envoie dans MinIO Bronze
    data = json.dumps(toutes_stations, ensure_ascii=False, indent=2).encode("utf-8")
    object_name = f"velos/snapshot_{timestamp}.json"

    upload_bytes(BUCKET_BRONZE, object_name, data, content_type="application/json")
    log_info(f"Snapshot envoyé : {len(toutes_stations)} stations → Bronze/{object_name}")


def main():
    log_info("=== Démarrage collecte CityBikes ===")

    # Initialise les buckets MinIO au démarrage
    init_buckets()

    # Récupère les réseaux FR une seule fois
    reseaux = get_reseaux_france()

    if not reseaux:
        log_error("Aucun réseau FR trouvé, arrêt du programme")
        return

    # Boucle infinie : collecte toutes les 60 secondes
    while True:
        try:
            collecter_snapshot(reseaux)
        except Exception as e:
            log_error(f"Erreur snapshot : {e}")

        log_info(f"Prochain snapshot dans {COLLECT_INTERVAL_SECONDS}s...")
        time.sleep(COLLECT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()