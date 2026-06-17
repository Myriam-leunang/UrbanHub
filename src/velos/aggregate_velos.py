import io
import pandas as pd
from src.common.config import BUCKET_SILVER, BUCKET_GOLD
from src.common.minio_client import client, upload_bytes, list_objects
from src.common.logging_utils import log_info, log_error


def lire_silver(object_name: str) -> pd.DataFrame:
    """Lit un fichier Parquet depuis MinIO Silver."""
    try:
        response = client.get_object(BUCKET_SILVER, object_name)
        return pd.read_parquet(io.BytesIO(response.read()))
    except Exception as e:
        log_error(f"Erreur lecture Silver ({object_name}) : {e}")
        return pd.DataFrame()


def sauvegarder_gold(df: pd.DataFrame, nom_fichier: str):
    """Sauvegarde un DataFrame en Parquet dans MinIO Gold."""
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    object_name = f"velos/{nom_fichier}.parquet"
    upload_bytes(BUCKET_GOLD, object_name, buffer.read())
    log_info(f"Gold sauvegardé : {nom_fichier} ({len(df)} lignes)")


def calculer_indicateurs(df: pd.DataFrame) -> dict:
    """
    Calcule tous les indicateurs Gold à partir du Silver.
    Retourne un dict de DataFrames prêts à sauvegarder.
    """

    # --- Taux d'utilisation par station ---
    df["taux_utilisation"] = (
        df["bikes_available"] / df["total_docks"]
    ).round(3)

    # --- Stations critiques : quasi-vides (< 10%) ---
    stations_vides = (
        df[df["taux_utilisation"] < 0.10]
        .groupby("station_id")
        .agg(
            station_name=("station_name", "first"),
            ville=("ville", "first"),
            nb_alertes_vide=("station_id", "count"),
            taux_moyen=("taux_utilisation", "mean"),
        )
        .reset_index()
        .sort_values("nb_alertes_vide", ascending=False)
    )

    # --- Stations saturées (> 90%) ---
    stations_saturees = (
        df[df["taux_utilisation"] > 0.90]
        .groupby("station_id")
        .agg(
            station_name=("station_name", "first"),
            ville=("ville", "first"),
            nb_alertes_sature=("station_id", "count"),
            taux_moyen=("taux_utilisation", "mean"),
        )
        .reset_index()
        .sort_values("nb_alertes_sature", ascending=False)
    )

    # --- Taux moyen par station (classement général) ---
    taux_par_station = (
        df.groupby(["station_id", "station_name", "ville"])
        .agg(
            taux_moyen=("taux_utilisation", "mean"),
            bikes_moyen=("bikes_available", "mean"),
            slots_moyen=("free_slots", "mean"),
            nb_snapshots=("timestamp", "count"),
        )
        .reset_index()
        .sort_values("taux_moyen", ascending=False)
        .round(3)
    )

    # --- Pics horaires (moyenne par heure de la journée) ---
    df["heure"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dt.hour
    pics_horaires = (
        df.groupby("heure")
        .agg(
            bikes_moyen=("bikes_available", "mean"),
            taux_moyen=("taux_utilisation", "mean"),
        )
        .reset_index()
        .round(3)
    )

    # --- Déséquilibre par ville ---
    desequilibre_ville = (
        df.groupby("ville")
        .agg(
            nb_stations=("station_id", "nunique"),
            bikes_total=("bikes_available", "sum"),
            slots_total=("free_slots", "sum"),
            taux_moyen=("taux_utilisation", "mean"),
        )
        .reset_index()
        .round(3)
    )

    return {
        "taux_par_station"  : taux_par_station,
        "stations_vides"    : stations_vides,
        "stations_saturees" : stations_saturees,
        "pics_horaires"     : pics_horaires,
        "desequilibre_ville": desequilibre_ville,
    }


def main():
    log_info("=== Démarrage agrégation velos (Silver → Gold) ===")

    # Charge tous les fichiers Silver
    fichiers = list_objects(BUCKET_SILVER, prefix="velos/")

    if not fichiers:
        log_error("Aucun fichier Silver trouvé")
        return

    # Concatène tous les snapshots Silver en un seul DataFrame
    dfs = []
    for f in fichiers:
        df = lire_silver(f)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        log_error("Tous les fichiers Silver sont vides")
        return

    df_total = pd.concat(dfs, ignore_index=True)
    log_info(f"Données chargées : {len(df_total)} lignes au total")

    # Calcule les indicateurs
    indicateurs = calculer_indicateurs(df_total)

    # Sauvegarde chaque indicateur dans Gold
    for nom, df_ind in indicateurs.items():
        sauvegarder_gold(df_ind, nom)

    log_info("=== Agrégation terminée ===")


if __name__ == "__main__":
    main()