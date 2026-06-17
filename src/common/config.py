import os
from dotenv import load_dotenv

load_dotenv()

# --- MinIO ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "password123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

# --- Buckets ---
BUCKET_BRONZE = os.getenv("BUCKET_BRONZE", "urbanhub-bronze")
BUCKET_SILVER = os.getenv("BUCKET_SILVER", "urbanhub-silver")
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