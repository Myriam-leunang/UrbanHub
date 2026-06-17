import os
from dotenv import load_dotenv

<<<<<<< HEAD
# Charge le fichier .env à la racine du projet
load_dotenv()

# --- MinIO ---
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY",  "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY",  "minioadmin123")
MINIO_SECURE     = os.getenv("MINIO_SECURE", "False").lower() == "true"
=======
load_dotenv()

# --- MinIO ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "password123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"
>>>>>>> 548abe31a0d667e605413e90a0c9efc37d75f0fc

# --- Buckets ---
BUCKET_BRONZE = os.getenv("BUCKET_BRONZE", "urbanhub-bronze")
BUCKET_SILVER = os.getenv("BUCKET_SILVER", "urbanhub-silver")
<<<<<<< HEAD
BUCKET_GOLD   = os.getenv("BUCKET_GOLD",   "urbanhub-gold")

# --- CityBikes ---
CITYBIKES_URL = os.getenv("CITYBIKES_URL", "https://api.citybik.es/v2")

# --- Collecte ---
COLLECT_INTERVAL_SECONDS = int(os.getenv("COLLECT_INTERVAL_SECONDS", 60))
=======
BUCKET_GOLD = os.getenv("BUCKET_GOLD", "urbanhub-gold")

# --- NOAA ---
NOAA_BASE_URL = os.getenv(
    "NOAA_BASE_URL",
    "https://www.ncei.noaa.gov/data/global-hourly/access/"
)
NOAA_YEARS = int(os.getenv("NOAA_YEARS", 5))
NOAA_MAX_WORKERS = int(os.getenv("NOAA_MAX_WORKERS", 10))

# --- Conventions communes ---
TIMEZONE = "UTC"
PARQUET_ENGINE = "pyarrow"
LOG_DIR = "logs"
>>>>>>> 548abe31a0d667e605413e90a0c9efc37d75f0fc
