import os
from dotenv import load_dotenv

# Charge le fichier .env à la racine du projet
load_dotenv()

# --- MinIO ---
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY",  "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY",  "minioadmin123")
MINIO_SECURE     = os.getenv("MINIO_SECURE", "False").lower() == "true"

# --- Buckets ---
BUCKET_BRONZE = os.getenv("BUCKET_BRONZE", "urbanhub-bronze")
BUCKET_SILVER = os.getenv("BUCKET_SILVER", "urbanhub-silver")
BUCKET_GOLD   = os.getenv("BUCKET_GOLD",   "urbanhub-gold")

# --- CityBikes ---
CITYBIKES_URL = os.getenv("CITYBIKES_URL", "https://api.citybik.es/v2")

# --- Collecte ---
COLLECT_INTERVAL_SECONDS = int(os.getenv("COLLECT_INTERVAL_SECONDS", 60))