import os
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.common.config import (
    BUCKET_SILVER, BUCKET_GOLD,
    MINIO_ENDPOINT, MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD, MINIO_SECURE
)
from minio import Minio

# ─── Client MinIO ──────────────────────────────────────────────────────────────
def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=MINIO_SECURE
    )

def ensure_bucket(client, bucket):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print(f"[MinIO] Bucket créé : {bucket}")

# ─── Lecture Parquet depuis MinIO ─────────────────────────────────────────────
def read_parquet_from_minio(client, bucket, object_name):
    response = client.get_object(bucket, object_name)
    return pq.read_table(BytesIO(response.read())).to_pandas()

# ─── Sauvegarde Parquet dans MinIO ────────────────────────────────────────────
def save_parquet_to_minio(client, df, bucket, object_name):
    buffer = BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buffer)
    buffer.seek(0)
    data = buffer.getvalue()
    client.put_object(
        bucket, object_name,
        BytesIO(data), length=len(data),
        content_type="application/octet-stream"
    )
    print(f"[Gold] ✅ Sauvegardé : {object_name}")

# ─── Chargement de toutes les données Silver ──────────────────────────────────
def load_all_silver(client):
    objects = list(client.list_objects(BUCKET_SILVER, prefix="meteo/silver/", recursive=True))
    print(f"[AGG] Chargement de {len(objects)} fichiers Silver...")

    dfs = []
    for obj in tqdm(objects, desc="Chargement"):
        try:
            df = read_parquet_from_minio(client, BUCKET_SILVER, obj.object_name)
            dfs.append(df)
        except Exception as e:
            print(f"[ERREUR] {obj.object_name} : {e}")

    if not dfs:
        raise RuntimeError("❌ Aucune donnée Silver trouvée.")

    df_all = pd.concat(dfs, ignore_index=True)
    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], utc=True)
    print(f"[AGG] ✅ {len(df_all):,} lignes chargées.")
    return df_all

# ─── Q1 : Périodes météorologiques anormales ──────────────────────────────────
def detect_anomalies(df):
    """
    Calcule la moyenne et l'écart-type par mois.
    Une période est anormale si température > moyenne + 2*std ou < moyenne - 2*std.
    """
    df = df.copy()
    df["month"] = df["timestamp"].dt.month
    df["year"]  = df["timestamp"].dt.year
    df["date"]  = df["timestamp"].dt.date

    stats = df.groupby("month")["temperature"].agg(["mean", "std"]).reset_index()
    df = df.merge(stats, on="month")

    df["anomalie_temp"] = (
        (df["temperature"] > df["mean"] + 2 * df["std"]) |
        (df["temperature"] < df["mean"] - 2 * df["std"])
    )

    anomalies = df[df["anomalie_temp"]].groupby(["year", "month"]).agg(
        nb_anomalies=("anomalie_temp", "sum"),
        temp_min=("temperature", "min"),
        temp_max=("temperature", "max"),
        temp_moy=("temperature", "mean")
    ).reset_index()

    return anomalies

# ─── Q2 : Corrélation météo / visibilité ──────────────────────────────────────
def compute_meteo_visibility_correlation(df):
    """
    Corrélation entre température, vent, pression et visibilité.
    """
    cols = ["temperature", "wind_speed", "pressure", "visibility"]
    df_corr = df[cols].dropna()
    corr = df_corr.corr()
    return corr.reset_index().rename(columns={"index": "variable"})

# ─── Q3 : Évolution saisonnière de la température ─────────────────────────────
def compute_seasonal_temperature(df):
    """
    Moyenne de température par saison et par année.
    """
    df = df.copy()
    df["month"] = df["timestamp"].dt.month
    df["year"]  = df["timestamp"].dt.year

    def get_season(month):
        if month in [12, 1, 2]:  return "Hiver"
        elif month in [3, 4, 5]: return "Printemps"
        elif month in [6, 7, 8]: return "Été"
        else:                     return "Automne"

    df["saison"] = df["month"].apply(get_season)

    seasonal = df.groupby(["year", "saison"]).agg(
        temp_moyenne=("temperature", "mean"),
        temp_min=("temperature", "min"),
        temp_max=("temperature", "max"),
        nb_mesures=("temperature", "count")
    ).reset_index()

    return seasonal

# ─── Q4 : Jours météo extrêmes ────────────────────────────────────────────────
def detect_extreme_days(df):
    """
    Jours extrêmes : température < 0°C ou > 35°C,
    vent > 20 m/s, précipitations > 20mm.
    """
    df = df.copy()
    df["date"] = df["timestamp"].dt.date

    daily = df.groupby("date").agg(
        temp_max=("temperature", "max"),
        temp_min=("temperature", "min"),
        vent_max=("wind_speed", "max"),
        precip_total=("precipitation", "sum"),
        visibilite_min=("visibility", "min")
    ).reset_index()

    daily["gel"]         = daily["temp_min"] < 0
    daily["canicule"]    = daily["temp_max"] > 35
    daily["tempete"]     = daily["vent_max"] > 20
    daily["fortes_pluies"] = daily["precip_total"] > 20
    daily["brouillard"]  = daily["visibilite_min"] < 1000

    daily["jour_extreme"] = (
        daily["gel"] | daily["canicule"] |
        daily["tempete"] | daily["fortes_pluies"] |
        daily["brouillard"]
    )

    extremes = daily[daily["jour_extreme"]].copy()
    return extremes

# ─── Pipeline principal ───────────────────────────────────────────────────────
def aggregate_all():
    client = get_minio_client()
    ensure_bucket(client, BUCKET_GOLD)

    # Chargement Silver
    df = load_all_silver(client)

    # Q1 — Anomalies
    print("\n[AGG] Q1 : Calcul des périodes anormales...")
    df_anomalies = detect_anomalies(df.dropna(subset=["temperature"]))
    save_parquet_to_minio(client, df_anomalies, BUCKET_GOLD, "meteo/gold/anomalies_temperature.parquet")

    # Q2 — Corrélation
    print("[AGG] Q2 : Calcul des corrélations météo / visibilité...")
    df_corr = compute_meteo_visibility_correlation(df)
    save_parquet_to_minio(client, df_corr, BUCKET_GOLD, "meteo/gold/correlation_meteo_visibilite.parquet")

    # Q3 — Saisonnalité
    print("[AGG] Q3 : Calcul de l'évolution saisonnière...")
    df_seasonal = compute_seasonal_temperature(df.dropna(subset=["temperature"]))
    save_parquet_to_minio(client, df_seasonal, BUCKET_GOLD, "meteo/gold/evolution_saisonniere.parquet")

    # Q4 — Jours extrêmes
    print("[AGG] Q4 : Détection des jours extrêmes...")
    df_extremes = detect_extreme_days(df)
    save_parquet_to_minio(client, df_extremes, BUCKET_GOLD, "meteo/gold/jours_extremes.parquet")

    print("\n[AGG] 🎉 Agrégation terminée ! 4 fichiers Gold générés.")

# ─── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    aggregate_all()