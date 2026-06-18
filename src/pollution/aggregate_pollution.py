import os
import tempfile
import pandas as pd
import numpy as np

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

# Import the actual MinIO operations from the common client
try:
    from src.common.minio_client import upload_file, download_file, list_objects
    minio_available = True
except ImportError:
    minio_available = False

# Fallback local S3 client simulation in case minio_client is not imported
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
        path = os.path.join("data", bucket, prefix)
        if not os.path.exists(path):
            return []
        keys = []
        for root, _, files in os.walk(path):
            for file in files:
                full_path = os.path.relpath(os.path.join(root, file), os.path.join("data", bucket))
                key = full_path.replace(os.path.sep, "/")
                keys.append(key)
        return keys

local_mock = LocalMinIOClientMock()

# Work thresholds for PM2.5, PM10, NO2
POLLUTANTS_THRESHOLDS = {
    "pm25": 15.0,  # 15 µg/m³
    "pm10": 45.0,  # 45 µg/m³
    "no2": 25.0,   # 25 µg/m³
}

def aggregate_city_pollution(city):
    """Aggregate Silver pollution measurements for a city and upload to Gold."""
    logger.info(f"Aggregating pollution Silver data for city: {city}")
    
    silver_prefix = f"pollution/city={city}/"
    silver_keys = []
    
    if minio_available:
        try:
            silver_keys = list_objects("urbanhub-silver", prefix=silver_prefix)
        except Exception as e:
            logger.warning(f"MinIO listing failed, listing locally: {e}")
            
    if not silver_keys:
        silver_keys = local_mock.list_objects("urbanhub-silver", prefix=silver_prefix)
        
    if not silver_keys:
        logger.warning(f"No Silver pollution data found for city {city}")
        return
        
    dfs = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for key in silver_keys:
            if key.endswith('.parquet'):
                local_file = os.path.join(tmpdir, os.path.basename(key))
                
                downloaded = False
                if minio_available:
                    try:
                        download_file("urbanhub-silver", key, local_file)
                        downloaded = True
                    except Exception as e:
                        logger.warning(f"MinIO download failed, trying local fallback: {e}")
                        
                if not downloaded:
                    if not local_mock.download_file("urbanhub-silver", key, local_file):
                        continue
                        
                try:
                    dfs.append(pd.read_parquet(local_file))
                except Exception as e:
                    logger.error(f"Error reading {key}: {e}")
                        
        if not dfs:
            return
            
        df = pd.concat(dfs, ignore_index=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        daily_grouped = df.groupby(['date', 'pollutant']).agg(
            avg_value=('value', 'mean'),
            max_value=('value', 'max'),
            measurement_count=('value', 'count')
        ).reset_index()
        
        def check_exceedance(row):
            pollutant = row['pollutant']
            val = row['avg_value']
            threshold = POLLUTANTS_THRESHOLDS.get(pollutant)
            if threshold and val > threshold:
                return True
            return False
            
        daily_grouped['threshold_exceeded'] = daily_grouped.apply(check_exceedance, axis=1)
        
        pivoted = daily_grouped.pivot(index='date', columns='pollutant', values='avg_value').reset_index()
        
        pivoted.rename(columns={
            col: f"avg_{col}" for col in pivoted.columns if col != 'date'
        }, inplace=True)
        
        pivoted['city'] = city
        
        episodes = daily_grouped[daily_grouped['threshold_exceeded'] == True]['date'].unique()
        pivoted['pollution_episode_flag'] = pivoted['date'].apply(lambda d: d in episodes)
        
        local_gold = os.path.join(tmpdir, "gold_pollution.parquet")
        pivoted.to_parquet(local_gold, compression='snappy', index=False)
        
        gold_key = f"pollution/city={city}/daily_aggregates.parquet"
        
        uploaded = False
        if minio_available:
            try:
                upload_file("urbanhub-gold", gold_key, local_gold)
                uploaded = True
            except Exception as e:
                logger.warning(f"MinIO upload failed, trying local fallback: {e}")
                
        if not uploaded:
            local_mock.upload_file(local_gold, "urbanhub-gold", gold_key)

def main():
    logger.info("Starting OpenAQ Gold aggregation...")
    
    silver_objects = []
    if minio_available:
        try:
            silver_objects = list_objects("urbanhub-silver", prefix="pollution/")
        except Exception as e:
            logger.warning(f"MinIO listing failed, listing locally: {e}")
            
    if not silver_objects:
        silver_objects = local_mock.list_objects("urbanhub-silver", prefix="pollution/")
        
    cities = set()
    for obj in silver_objects:
        parts = obj.split('/')
        for part in parts:
            if part.startswith('city='):
                cities.add(part.split('=')[1])
                
    logger.info(f"Found cities for pollution aggregation: {list(cities)}")
    for city in cities:
        aggregate_city_pollution(city)
        
    logger.info("Finished OpenAQ Gold aggregation.")

if __name__ == "__main__":
    main()
