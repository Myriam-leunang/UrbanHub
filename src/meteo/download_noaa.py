import os
import sys
import requests
import pandas as pd
from io import StringIO, BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.common.config import (
    NOAA_BASE_URL, NOAA_YEARS, NOAA_MAX_WORKERS,
    BUCKET_BRONZE, MINIO_ENDPOINT, MINIO_ROOT_USER,
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

def file_exists_in_minio(client, bucket, object_name):
    try:
        client.stat_object(bucket, object_name)
        return True
    except:
        return False

# ─── Chargement des stations France ───────────────────────────────────────────
def get_french_stations():
    urls = [
        "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv",
        "https://noaa-isd-pds.s3.amazonaws.com/isd-history.csv",
        "https://www.ncei.noaa.gov/data/global-hourly/doc/isd-history.csv",
    ]

    for url in urls:
        try:
            print(f"[NOAA] Tentative : {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            df = pd.read_csv(StringIO(response.text), low_memory=False)
            df.columns = df.columns.str.strip()

            france = df[df["CTRY"].str.strip() == "FR"].copy()
            france["station_file_id"] = (
                france["USAF"].astype(str).str.zfill(6) + "-" +
                france["WBAN"].astype(str).str.zfill(5)
            )
            print(f"[NOAA] ✅ {len(france)} stations françaises trouvées.")
            return france["station_file_id"].tolist()

        except Exception as e:
            print(f"[WARN] URL indisponible : {e}")
            continue

    raise RuntimeError("❌ Impossible de récupérer la liste des stations NOAA.")

# ─── Téléchargement d'un fichier station / année ──────────────────────────────
def download_station_year(station_id, year, minio_client, max_retries=3):
    station_file = station_id.replace("-", "")
    url = f"{NOAA_BASE_URL}{year}/{station_file}.csv"
    object_name = f"meteo/bronze/{year}/{station_file}.csv"

    # Skip si déjà dans MinIO
    if file_exists_in_minio(minio_client, BUCKET_BRONZE, object_name):
        return "skipped"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 404:
                return None

            response.raise_for_status()
            content = response.content

            minio_client.put_object(
                BUCKET_BRONZE,
                object_name,
                BytesIO(content),
                length=len(content),
                content_type="text/csv"
            )
            return object_name

        except Exception as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # backoff : 1s, 2s, 4s
            else:
                print(f"[ERREUR] {station_id} / {year} : {e}")
                return None

# ─── Téléchargement parallèle ─────────────────────────────────────────────────
def download_all_stations(stations, years):
    client = get_minio_client()
    ensure_bucket(client, BUCKET_BRONZE)

    tasks = [
        (station, year)
        for station in stations
        for year in years
    ]

    print(f"[NOAA] {len(tasks)} fichiers à vérifier ({len(stations)} stations × {len(years)} ans)")
    success, skipped, errors = 0, 0, 0

    with ThreadPoolExecutor(max_workers=NOAA_MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_station_year, s, y, client): (s, y)
            for s, y in tasks
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Téléchargement"):
            result = future.result()
            if result == "skipped":
                skipped += 1
            elif result:
                success += 1
            else:
                errors += 1

    print(f"\n[NOAA] ✅ {success} téléchargés | ⏭️ {skipped} déjà présents | ❌ {errors} non disponibles")

# ─── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    current_year = datetime.now().year
    years = list(range(current_year - NOAA_YEARS, current_year + 1))

    stations = get_french_stations()
    download_all_stations(stations, years)