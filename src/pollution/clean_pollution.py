import os
import json
import tempfile
import pandas as pd
from src.common.geo_utils import find_nearest_city

# Fallback logger definition
class SimpleLogger:
    def info(self, msg): print(f"INFO: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def error(self, msg): print(f"ERROR: {msg}")

logger = SimpleLogger()

try:
    from src.common.logging_utils import logger
except ImportError:
    pass

# Fallback S3 client definition
class LocalMinIOClientMock:
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
    if not hasattr(minio_client, "upload_file"):
        minio_client = LocalMinIOClientMock()
except ImportError:
    pass

def clean_json_file(raw_key):
    """Parse raw OpenAQ json file, clean, map city, and save to Silver parquet."""
    logger.info(f"Processing raw OpenAQ file: {raw_key}")
    
    # Extract file details: pollution/date=2026-06-17/snapshots_120511.json
    parts = raw_key.split('/')
    if len(parts) < 3:
        return
        
    date_part = parts[1] # e.g. "date=2026-06-17"
    filename = parts[2]  # e.g. "snapshots_120511.json"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        local_json = os.path.join(tmpdir, "raw.json")
        if not minio_client.download_file("urbanhub-bronze", raw_key, local_json):
            return
            
        try:
            with open(local_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            results = data.get('results', [])
            cleaned_measurements = []
            
            for res in results:
                location = res.get('location', {})
                coords = location.get('coordinates', {})
                lat = coords.get('latitude')
                lon = coords.get('longitude')
                locality = location.get('locality', '')
                
                # Identify city using our geographical utility
                city = find_nearest_city(lat, lon)
                if city == "unknown" and locality:
                    # Try direct string matching
                    loc_lower = locality.lower()
                    for target in ["paris", "lyon", "marseille", "toulouse", "bordeaux", "lille"]:
                        if target in loc_lower:
                            city = target
                            break
                            
                # Exclude measurements with unknown or non-target cities
                if city == "unknown":
                    continue
                    
                sensors = res.get('sensors', [])
                for sensor in sensors:
                    sensor_id = sensor.get('id')
                    param = sensor.get('parameter', {})
                    pollutant_name = param.get('name', '').lower()
                    unit = param.get('units', '')
                    val = sensor.get('value')
                    raw_dt = sensor.get('datetime')
                    
                    # Normalize pollutant names
                    norm_pollutant = None
                    for name in ["pm25", "pm10", "no2", "o3", "co"]:
                        if name in pollutant_name.replace(".", ""):
                            norm_pollutant = name
                            break
                            
                    if not norm_pollutant:
                        continue
                        
                    # Filter aberrant values (negative values or overly high peaks)
                    if val is None or val < 0.0 or val > 1000.0:
                        continue
                        
                    # Normalize timestamp
                    try:
                        ts = pd.to_datetime(raw_dt).strftime('%Y-%m-%dT%H:%M:%SZ')
                    except Exception:
                        ts = pd.to_datetime(date_part.split('=')[1]).strftime('%Y-%m-%dT%H:%M:%SZ')
                        
                    cleaned_measurements.append({
                        "sensor_id": str(sensor_id),
                        "pollutant": norm_pollutant,
                        "value": float(val),
                        "unit": unit,
                        "latitude": float(lat) if lat else None,
                        "longitude": float(lon) if lon else None,
                        "timestamp": ts,
                        "city": city
                    })
                    
            if not cleaned_measurements:
                logger.warning(f"No valid pollution measurements found in {raw_key}")
                return
                
            df = pd.DataFrame(cleaned_measurements)
            df.drop_duplicates(subset=['sensor_id', 'pollutant', 'timestamp'], inplace=True)
            
            # Save by city to support partitioned loading
            for city_name, city_df in df.groupby('city'):
                local_parquet = os.path.join(tmpdir, f"data_{city_name}.parquet")
                city_df.to_parquet(local_parquet, compression='snappy', index=False)
                
                silver_key = f"pollution/city={city_name}/{date_part}/data_{filename.replace('.json', '.parquet')}"
                minio_client.upload_file(local_parquet, "urbanhub-silver", silver_key)
                logger.info(f"Uploaded Silver pollution parquet: {silver_key}")
                
        except Exception as e:
            logger.error(f"Error cleaning OpenAQ file {raw_key}: {e}")

def main():
    logger.info("Starting OpenAQ clean pipeline...")
    raw_files = minio_client.list_objects("urbanhub-bronze", prefix="pollution/")
    logger.info(f"Found {len(raw_files)} raw pollution files to clean.")
    
    for raw_file in raw_files:
        if raw_file.endswith('.json'):
            clean_json_file(raw_file)
            
    logger.info("Finished OpenAQ clean pipeline.")

if __name__ == "__main__":
    main()
