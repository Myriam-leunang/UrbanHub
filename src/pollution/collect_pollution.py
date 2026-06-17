import os
import sys
import json
import random
import requests
from datetime import datetime

# Fallback logger definition in case logging_utils.py is not yet implemented
class SimpleLogger:
    def info(self, msg): print(f"INFO: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def error(self, msg): print(f"ERROR: {msg}")

logger = SimpleLogger()

try:
    from src.common.logging_utils import logger
except ImportError:
    pass

# Fallback config settings
OPENAQ_API_KEY = ""
try:
    from src.common.config import OPENAQ_API_KEY
except ImportError:
    pass

# Fallback local S3 client simulation in case minio_client.py is not yet implemented
class LocalMinIOClientMock:
    def upload_bytes(self, data, bucket, object_name):
        path = os.path.join("data", bucket, object_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        logger.info(f"[Local Storage] Saved raw bytes to: {path}")
        return True

    def upload_file(self, local_path, bucket, object_name):
        path = os.path.join("data", bucket, object_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        import shutil
        shutil.copy(local_path, path)
        logger.info(f"[Local Storage] Copied file to: {path}")
        return True

    def download_file(self, bucket, object_name, local_path):
        path = os.path.join("data", bucket, object_name)
        if os.path.exists(path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            import shutil
            shutil.copy(path, local_path)
            logger.info(f"[Local Storage] Downloaded {object_name} from: {path}")
            return True
        logger.error(f"[Local Storage] Object {object_name} not found in {bucket}")
        return False

    def list_objects(self, bucket, prefix=""):
        path = os.path.join("data", bucket)
        if not os.path.exists(path):
            return []
        keys = []
        for root, _, files in os.walk(path):
            for file in files:
                full_path = os.path.relpath(os.path.join(root, file), path)
                key = full_path.replace(os.path.sep, "/")
                if key.startswith(prefix):
                    keys.append(key)
        return keys

minio_client = LocalMinIOClientMock()

try:
    from src.common.minio_client import minio_client
    if not hasattr(minio_client, "upload_bytes"):
        minio_client = LocalMinIOClientMock()
except ImportError:
    pass

CITIES_COORDS = {
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "lyon": {"lat": 45.7640, "lon": 4.8357},
    "marseille": {"lat": 43.2965, "lon": 5.3698},
    "toulouse": {"lat": 43.6047, "lon": 1.4442},
    "bordeaux": {"lat": 44.8378, "lon": -0.5792},
    "lille": {"lat": 50.6292, "lon": 3.0573}
}

def generate_simulated_openaq_data():
    """Generate mock OpenAQ v3 data for French cities."""
    results = []
    now_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Generate mock sensors measurements
    sensor_id_counter = 1000
    for city, coords in CITIES_COORDS.items():
        location_id = random.randint(100, 999)
        sensors = []
        
        # Pollutants configuration: (name, unit, min_val, max_val)
        pollutants_config = [
            ("pm25", "µg/m³", 5.0, 35.0),
            ("pm10", "µg/m³", 10.0, 60.0),
            ("no2", "µg/m³", 5.0, 40.0),
            ("o3", "µg/m³", 20.0, 80.0),
            ("co", "µg/m³", 100.0, 600.0)
        ]
        
        for name, unit, min_val, max_val in pollutants_config:
            sensor_id_counter += 1
            # Add some randomness and occasional spikes
            val = random.uniform(min_val, max_val)
            if random.random() > 0.95:  # 5% chance of high pollution spike
                val *= 2.0
                
            sensors.append({
                "id": sensor_id_counter,
                "parameter": {"name": name, "units": unit},
                "value": round(val, 2),
                "datetime": now_str
            })
            
        results.append({
            "location": {
                "id": location_id,
                "name": f"{city.capitalize()} Station",
                "coordinates": {"latitude": coords["lat"], "longitude": coords["lon"]},
                "locality": city.capitalize()
            },
            "sensors": sensors
        })
        
    return {"results": results}

def main():
    logger.info("Starting OpenAQ IoT Ingestion script...")
    
    data = None
    if OPENAQ_API_KEY:
        url = "https://api.openaq.org/v3/locations?countriesId=108&limit=50"
        headers = {"X-API-Key": OPENAQ_API_KEY}
        try:
            logger.info(f"Querying OpenAQ API v3 from {url}...")
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                logger.info("Successfully retrieved data from OpenAQ API.")
            else:
                logger.warning(f"OpenAQ API error {response.status_code}. Falling back to simulation.")
        except Exception as e:
            logger.warning(f"Failed to query OpenAQ API: {e}. Falling back to simulation.")
            
    if data is None:
        logger.info("Using simulated quality-of-air data for France cities.")
        data = generate_simulated_openaq_data()
        
    # Format dates and paths
    now = datetime.utcnow()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H%M%S')
    
    object_name = f"pollution/date={date_str}/snapshots_{time_str}.json"
    json_bytes = json.dumps(data).encode('utf-8')
    
    # Store raw measurements in Bronze bucket
    success = minio_client.upload_bytes(
        data=json_bytes,
        bucket="urbanhub-bronze",
        object_name=object_name
    )
    if success:
        logger.info(f"Successfully uploaded OpenAQ raw data to Bronze: {object_name}")
    else:
        logger.error("Failed to store data in Data Lake.")

if __name__ == "__main__":
    main()
