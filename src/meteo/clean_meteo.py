import os
import sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.common.config import (
    BUCKET_BRONZE, BUCKET_SILVER,
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

# ─── Lecture d'un CSV depuis MinIO Bronze ─────────────────────────────────────
def read_csv_from_minio(client, bucket, object_name):
    response = client.get_object(bucket, object_name)
    df = pd.read_csv(BytesIO(response.read()), low_memory=False)
    return df

# ─── Parsing température ──────────────────────────────────────────────────────
def parse_temperature(series):
    """
    Format NOAA : '+0234' = 23.4°C  /  '+9999' = manquant
    Divise par 10, remplace 999.9 par NaN
    """
    def extract(val):
        try:
            parts = str(val).split(",")
            temp = int(parts[0]) / 10.0
            return None if temp == 999.9 else temp
        except:
            return None
    return series.apply(extract)

# ─── Parsing vent ─────────────────────────────────────────────────────────────
def parse_wind(series):
    """
    Format NOAA : 'direction,qualité,type,vitesse,qualité'
    direction en degrés, vitesse en m/s (divisé par 10)
    999 = manquant
    """
    directions, speeds = [], []
    for val in series:
        try:
            parts = str(val).split(",")
            d = int(parts[0])
            s = int(parts[3]) / 10.0
            directions.append(None if d == 999 else d)
            speeds.append(None if s == 999.9 else s)
        except:
            directions.append(None)
            speeds.append(None)
    return directions, speeds

# ─── Parsing pression ─────────────────────────────────────────────────────────
def parse_pressure(series):
    """
    Format NOAA SLP : '+10132' = 1013.2 hPa
    99999 = manquant
    """
    def extract(val):
        try:
            parts = str(val).split(",")
            p = int(parts[0]) / 10.0
            return None if p == 9999.9 else p
        except:
            return None
    return series.apply(extract)

# ─── Parsing précipitations ───────────────────────────────────────────────────
def parse_precipitation(series):
    """
    Format NOAA AA1 : 'période,depth,condition,qualité'
    depth en mm (divisé par 10)
    9999 = manquant
    """
    def extract(val):
        try:
            parts = str(val).split(",")
            p = int(parts[1]) / 10.0
            return None if p == 999.9 else p
        except:
            return None
    return series.apply(extract)

# ─── Parsing visibilité ───────────────────────────────────────────────────────
def parse_visibility(series):
    """
    Format NOAA VIS : distance en mètres
    999999 = manquant
    """
    def extract(val):
        try:
            parts = str(val).split(",")
            v = int(parts[0])
            return None if v == 999999 else v
        except:
            return None
    return series.apply(extract)

# ─── Nettoyage d'un DataFrame brut ────────────────────────────────────────────
def clean_dataframe(df):
    # Normaliser les noms de colonnes
    df.columns = df.columns.str.strip().str.upper()

    # Vérifier colonnes minimales
    required = ["STATION", "DATE"]
    for col in required:
        if col not in df.columns:
            return None

    cleaned = pd.DataFrame()
    cleaned["station_id"] = df["STATION"].astype(str)

    # Timestamp en UTC
    cleaned["timestamp"] = pd.to_datetime(df["DATE"], utc=True, errors="coerce")

    # Température
    cleaned["temperature"] = parse_temperature(df["TMP"]) if "TMP" in df.columns else None

    # Vent
    if "WND" in df.columns:
        dirs, speeds = parse_wind(df["WND"])
        cleaned["wind_direction"] = dirs
        cleaned["wind_speed"] = speeds
    else:
        cleaned["wind_direction"] = None
        cleaned["wind_speed"] = None

    # Pression
    cleaned["pressure"] = parse_pressure(df["SLP"]) if "SLP" in df.columns else None

    # Précipitations
    cleaned["precipitation"] = parse_precipitation(df["AA1"]) if "AA1" in df.columns else None

    # Visibilité
    cleaned["visibility"] = parse_visibility(df["VIS"]) if "VIS" in df.columns else None

    # Supprimer les lignes sans timestamp ni station
    cleaned = cleaned.dropna(subset=["timestamp", "station_id"])

    # Supprimer les doublons
    cleaned = cleaned.drop_duplicates(subset=["station_id", "timestamp"])

    # Trier par station et temps
    cleaned = cleaned.sort_values(["station_id", "timestamp"]).reset_index(drop=True)

    return cleaned

# ─── Sauvegarde Parquet dans MinIO Silver ─────────────────────────────────────
def save_parquet_to_minio(client, df, bucket, object_name):
    buffer = BytesIO()
    table = pa.Table.from_pandas(df)
    pq.write_table(table, buffer)
    buffer.seek(0)
    data = buffer.getvalue()
    client.put_object(
        bucket,
        object_name,
        BytesIO(data),
        length=len(data),
        content_type="application/octet-stream"
    )

# ─── Pipeline principal ───────────────────────────────────────────────────────
def clean_all():
    client = get_minio_client()
    ensure_bucket(client, BUCKET_SILVER)

    # Lister tous les fichiers Bronze
    objects = list(client.list_objects(BUCKET_BRONZE, prefix="meteo/bronze/", recursive=True))
    print(f"[CLEAN] {len(objects)} fichiers à nettoyer depuis Bronze")

    success, errors, empty = 0, 0, 0

    for obj in tqdm(objects, desc="Nettoyage"):
        try:
            df_raw = read_csv_from_minio(client, BUCKET_BRONZE, obj.object_name)
            df_clean = clean_dataframe(df_raw)

            if df_clean is None or df_clean.empty:
                empty += 1
                continue

            # Chemin Silver : meteo/silver/{year}/{station}.parquet
            parts = obj.object_name.split("/")  # ['meteo','bronze','year','file.csv']
            year = parts[2]
            station = parts[3].replace(".csv", "")
            silver_path = f"meteo/silver/{year}/{station}.parquet"

            save_parquet_to_minio(client, df_clean, BUCKET_SILVER, silver_path)
            success += 1

        except Exception as e:
            print(f"[ERREUR] {obj.object_name} : {e}")
            errors += 1

    print(f"\n[CLEAN] [OK] {success} fichiers nettoyés | [WARN] {empty} vides | [ERROR] {errors} erreurs")

# ─── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    clean_all()