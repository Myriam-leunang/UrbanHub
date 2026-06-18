import json
import io
import pandas as pd
from src.common.config import BUCKET_BRONZE, BUCKET_SILVER
from src.common.minio_client import client, upload_bytes, list_objects
from src.common.logging_utils import log_info, log_error


def lire_snapshot_bronze(object_name: str) -> pd.DataFrame:
    """Lit un fichier JSON depuis MinIO Bronze et retourne un DataFrame."""
    try:
        response = client.get_object(BUCKET_BRONZE, object_name)
        data = json.loads(response.read().decode("utf-8"))
        return pd.DataFrame(data)
    except Exception as e:
        log_error(f"Erreur lecture Bronze ({object_name}) : {e}")
        return pd.DataFrame()


def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    """Applique tous les nettoyages sur le DataFrame brut."""

    # 1. Supprimer les stations sans coordonnées GPS
    df = df.dropna(subset=["latitude", "longitude"])

    # 2. Supprimer les lignes sans bikes_available ET sans free_slots
    df = df.dropna(subset=["bikes_available", "free_slots"], how="all")

    # 3. Remplir les valeurs manquantes restantes par 0
    df["bikes_available"] = df["bikes_available"].fillna(0).astype(int)
    df["free_slots"]      = df["free_slots"].fillna(0).astype(int)

    # 4. Calculer total_docks
    df["total_docks"] = df["bikes_available"] + df["free_slots"]

    # 5. Supprimer les stations avec total_docks = 0 (stations invalides)
    df = df[df["total_docks"] > 0]

    # 6. Uniformiser les colonnes en snake_case (déjà fait dans collect)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]

    # 7. Supprimer les doublons
    df = df.drop_duplicates(subset=["station_id", "timestamp"])

    # 8. Réordonner les colonnes
    colonnes = [
        "station_id", "station_name", "latitude", "longitude",
        "bikes_available", "free_slots", "total_docks",
        "reseau", "ville", "timestamp"
    ]
    df = df[[c for c in colonnes if c in df.columns]]

    return df


def sauvegarder_silver(df: pd.DataFrame, timestamp: str):
    """Sauvegarde le DataFrame nettoyé en Parquet dans MinIO Silver."""
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    object_name = f"velos/clean_{timestamp}.parquet"
    upload_bytes(BUCKET_SILVER, object_name, buffer.read(), content_type="application/octet-stream")
    log_info(f"Silver sauvegardé : {len(df)} stations -> {object_name}")


def main():
    log_info("=== Démarrage nettoyage velos (Bronze -> Silver) ===")

    # Liste tous les snapshots Bronze disponibles
    snapshots = list_objects(BUCKET_BRONZE, prefix="velos/")

    if not snapshots:
        log_error("Aucun snapshot trouvé dans Bronze/velos/")
        return

    log_info(f"{len(snapshots)} snapshots à traiter")

    for object_name in snapshots:
        log_info(f"Traitement : {object_name}")

        df = lire_snapshot_bronze(object_name)

        if df.empty:
            log_error(f"Snapshot vide, ignoré : {object_name}")
            continue

        df_clean = nettoyer(df)

        # Extrait le timestamp depuis le nom du fichier
        # ex: velos/snapshot_2024-01-01T10-00-00Z.json -> 2024-01-01T10-00-00Z
        timestamp = object_name.replace("velos/snapshot_", "").replace(".json", "")

        sauvegarder_silver(df_clean, timestamp)

    log_info("=== Nettoyage terminé ===")


if __name__ == "__main__":
    main()