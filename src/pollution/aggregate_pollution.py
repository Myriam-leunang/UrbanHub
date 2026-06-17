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
    if not hasattr(minio_client, "download_file"):
        minio_client = LocalMinIOClientMock()
except ImportError:
    pass

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
    silver_keys = minio_client.list_objects("urbanhub-silver", prefix=silver_prefix)
    
    if not silver_keys:
        logger.warning(f"No Silver pollution data found for city {city}")
        return
        
    dfs = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for key in silver_keys:
            if key.endswith('.parquet'):
                local_file = os.path.join(tmpdir, os.path.basename(key))
                if minio_client.download_file("urbanhub-silver", key, local_file):
                    try:
                        dfs.append(pd.read_parquet(local_file))
                    except Exception as e:
                        logger.error(f"Error reading {key}: {e}")
                        
        if not dfs:
            return
            
        df = pd.concat(dfs, ignore_index=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        
        # Aggregate daily measurements per pollutant
        daily_grouped = df.groupby(['date', 'pollutant']).agg(
            avg_value=('value', 'mean'),
            max_value=('value', 'max'),
            measurement_count=('value', 'count')
        ).reset_index()
        
        # Exceedance flags
        def check_exceedance(row):
            pollutant = row['pollutant']
            val = row['avg_value']
            threshold = POLLUTANTS_THRESHOLDS.get(pollutant)
            if threshold and val > threshold:
                return True
            return False
            
        daily_grouped['threshold_exceeded'] = daily_grouped.apply(check_exceedance, axis=1)
        
        # Calculate daily aggregate at city level (combining all pollutants into columns for the cross table)
        # We can pivot to make a nice table format: date | city | avg_pm25 | avg_pm10 | avg_no2 | avg_o3 | avg_co | pollution_episode_flag
        pivoted = daily_grouped.pivot(index='date', columns='pollutant', values='avg_value').reset_index()
        
        # Rename columns to avg_pollutant
        pivoted.rename(columns={
            col: f"avg_{col}" for col in pivoted.columns if col != 'date'
        }, inplace=True)
        
        pivoted['city'] = city
        
        # Determine pollution episode flag for the day (if any pollutant exceeded threshold)
        episodes = daily_grouped[daily_grouped['threshold_exceeded'] == True]['date'].unique()
        pivoted['pollution_episode_flag'] = pivoted['date'].apply(lambda d: d in episodes)
        
        # Upload daily pivoted aggregates to Gold
        local_gold = os.path.join(tmpdir, "gold_pollution.parquet")
        pivoted.to_parquet(local_gold, compression='snappy', index=False)
        
        gold_key = f"pollution/city={city}/daily_aggregates.parquet"
        minio_client.upload_file(local_gold, "urbanhub-gold", gold_key)
        logger.info(f"Successfully uploaded Gold pollution aggregates: {gold_key}")

def main():
    logger.info("Starting OpenAQ Gold aggregation...")
    silver_objects = minio_client.list_objects("urbanhub-silver", prefix="pollution/")
    
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
