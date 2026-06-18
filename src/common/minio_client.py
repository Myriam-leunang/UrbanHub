import io
from minio import Minio
from src.common.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
    BUCKET_BRONZE,
    BUCKET_SILVER,
    BUCKET_GOLD,
)

# --- Connexion MinIO ---
client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

BUCKETS = [BUCKET_BRONZE, BUCKET_SILVER, BUCKET_GOLD]


def init_buckets():
    """Crée les 3 buckets s'ils n'existent pas encore."""
    for bucket in BUCKETS:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f"[MinIO] Bucket créé : {bucket}")
        else:
            print(f"[MinIO] Bucket déjà existant : {bucket}")


def upload_bytes(bucket: str, object_name: str, data: bytes, content_type: str = "application/octet-stream"):
    """
    Envoie des bytes dans MinIO.
    Exemple : upload_bytes(BUCKET_BRONZE, "velos/snapshot_2024.json", data)
    """
    client.put_object(
        bucket,
        object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    print(f"[MinIO] Upload OK : {bucket}/{object_name}")


def upload_file(bucket: str, object_name: str, file_path: str):
    """
    Envoie un fichier local dans MinIO.
    Exemple : upload_file(BUCKET_SILVER, "velos/clean.parquet", "/tmp/clean.parquet")
    """
    client.fput_object(bucket, object_name, file_path)
    print(f"[MinIO] Fichier uploadé : {bucket}/{object_name}")


def download_file(bucket: str, object_name: str, dest_path: str):
    """
    Télécharge un fichier depuis MinIO vers un chemin local.
    """
    client.fget_object(bucket, object_name, dest_path)
    print(f"[MinIO] Fichier téléchargé : {bucket}/{object_name} -> {dest_path}")


def list_objects(bucket: str, prefix: str = "") -> list:
    """
    Liste les fichiers dans un bucket, avec un préfixe optionnel.
    Exemple : list_objects(BUCKET_BRONZE, prefix="velos/")
    """
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    return [obj.object_name for obj in objects]