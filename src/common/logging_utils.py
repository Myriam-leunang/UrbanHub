import logging
import os

# Crée le dossier logs/ à la racine si il n'existe pas
os.makedirs("logs", exist_ok=True)

# --- Logger erreurs ---
error_logger = logging.getLogger("errors")
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler("logs/errors.log", encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
error_logger.addHandler(error_handler)

# --- Logger pipeline ---
pipeline_logger = logging.getLogger("pipeline")
pipeline_logger.setLevel(logging.INFO)
pipeline_handler = logging.FileHandler("logs/pipeline.log", encoding="utf-8")
pipeline_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
pipeline_logger.addHandler(pipeline_handler)

# Affiche aussi dans le terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
pipeline_logger.addHandler(console_handler)


def log_info(message: str):
    """Log une étape normale du pipeline."""
    pipeline_logger.info(message)


def log_error(message: str):
    """Log une erreur dans errors.log ET pipeline.log."""
    error_logger.error(message)
    pipeline_logger.error(message)