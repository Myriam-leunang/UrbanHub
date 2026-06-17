import os
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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

CITIES = ["paris", "lyon", "marseille", "toulouse", "bordeaux", "lille"]

def generate_mock_meteo_gold(city, dates):
    """Generate mock Gold meteorology aggregates for testing when NOAA script is not run."""
    rows = []
    for d in dates:
        # Realistic seasonal temperatures based on month
        month = d.month
        base_temp = 12.0
        if month in [6, 7, 8]: base_temp = 22.0
        elif month in [12, 1, 2]: base_temp = 5.0
        
        avg_temp = base_temp + np.random.uniform(-4, 4)
        avg_wind = np.random.uniform(2.0, 10.0)
        
        rows.append({
            "date": d.date(),
            "city": city,
            "avg_temperature": round(avg_temp, 1),
            "max_temperature": round(avg_temp + 4, 1),
            "min_temperature": round(avg_temp - 4, 1),
            "avg_wind_speed": round(avg_wind, 1),
            "max_wind_speed": round(avg_wind * 1.5, 1),
            "avg_pressure": round(1013.0 + np.random.uniform(-15, 15), 1),
            "avg_visibility": round(np.random.uniform(5000, 15000), 0),
            "is_extreme_hot": avg_temp > 28.0,
            "is_extreme_cold": avg_temp < 0.0,
            "is_extreme_wind": avg_wind > 12.0,
            "temp_anomaly": round(np.random.uniform(-2, 2), 1)
        })
    return pd.DataFrame(rows)

def generate_mock_velos_gold(city, dates):
    """Generate mock Gold usage pressure aggregates for testing when CityBikes script is not run."""
    rows = []
    for d in dates:
        # Usage pressure is higher on weekdays and mild weather days (e.g. temperature around 20 degrees)
        weekday = d.weekday()
        is_weekend = weekday >= 5
        base_pressure = 0.65 if not is_weekend else 0.45
        
        avg_pressure = base_pressure + np.random.uniform(-0.15, 0.15)
        avg_pressure = max(0.05, min(0.95, avg_pressure))
        
        critical_count = int(np.random.poisson(5)) if avg_pressure > 0.7 else int(np.random.poisson(1))
        
        rows.append({
            "date": d.date(),
            "city": city,
            "avg_usage_pressure": round(avg_pressure, 2),
            "critical_stations_count": critical_count
        })
    return pd.DataFrame(rows)

def load_gold_dataset(bucket, prefix, default_generator, city, dates, tmpdir):
    """Download Gold parquet from MinIO S3, or generate mock if missing."""
    keys = minio_client.list_objects(bucket, prefix=prefix)
    parquet_keys = [k for k in keys if k.endswith('.parquet')]
    
    if parquet_keys:
        local_file = os.path.join(tmpdir, "downloaded.parquet")
        # Download the first found parquet
        if minio_client.download_file(bucket, parquet_keys[0], local_file):
            try:
                df = pd.read_parquet(local_file)
                # Ensure date is format date
                df['date'] = pd.to_datetime(df['date']).dt.date
                return df
            except Exception as e:
                logger.error(f"Error reading {parquet_keys[0]}: {e}")
                
    logger.warning(f"Could not load Gold data for {prefix} in {bucket}. Generating simulation data.")
    return default_generator(city, dates)

def merge_city_datasets(city):
    """Merge daily aggregates for meteorology, bikes usage and pollution for a city."""
    logger.info(f"Merging datasets for city: {city}")
    
    # We will work over the last 30 days for consolidated analysis
    end_date = datetime.utcnow()
    dates = [end_date - timedelta(days=i) for i in range(30)]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Load Pollution Gold (Our own module's output)
        pollution_prefix = f"pollution/city={city}/"
        pollution_keys = minio_client.list_objects("urbanhub-gold", prefix=pollution_prefix)
        pollution_parquet = [k for k in pollution_keys if k.endswith('.parquet')]
        
        if not pollution_parquet:
            logger.warning(f"No Gold pollution data found for {city}. Run aggregate_pollution.py first.")
            return
            
        local_pol = os.path.join(tmpdir, "pollution.parquet")
        minio_client.download_file("urbanhub-gold", pollution_parquet[0], local_pol)
        pollution_df = pd.read_parquet(local_pol)
        pollution_df['date'] = pd.to_datetime(pollution_df['date']).dt.date
        
        # 2. Load Météo Gold (developed by Personne 1, or simulated if missing)
        meteo_df = load_gold_dataset(
            bucket="urbanhub-gold",
            prefix=f"meteo/city={city}/",
            default_generator=generate_mock_meteo_gold,
            city=city,
            dates=dates,
            tmpdir=tmpdir
        )
        
        # 3. Load Vélos Gold (developed by Personne 2, or simulated if missing)
        velos_df = load_gold_dataset(
            bucket="urbanhub-gold",
            prefix=f"velos/city={city}/",
            default_generator=generate_mock_velos_gold,
            city=city,
            dates=dates,
            tmpdir=tmpdir
        )
        
        # Perform joins on 'city' and 'date'
        merged = pollution_df.merge(meteo_df, on=['date', 'city'], how='left')
        merged = merged.merge(velos_df, on=['date', 'city'], how='left')
        
        # Fill missing values if any
        merged.fillna({
            "avg_temperature": 15.0,
            "avg_wind_speed": 5.0,
            "avg_usage_pressure": 0.5,
            "critical_stations_count": 0,
            "pollution_episode_flag": False
        }, inplace=True)
        
        # Upload consolidated dataset to Gold: cross/city=paris/merged_daily.parquet
        local_gold = os.path.join(tmpdir, f"merged_{city}.parquet")
        merged.to_parquet(local_gold, compression='snappy', index=False)
        
        gold_key = f"cross/city={city}/merged_daily.parquet"
        minio_client.upload_file(local_gold, "urbanhub-gold", gold_key)
        logger.info(f"Successfully uploaded Gold merged dataset: {gold_key}")

def main():
    logger.info("Starting Gold datasets merge pipeline...")
    # List cities in pollution gold bucket to identify cities to merge
    gold_objects = minio_client.list_objects("urbanhub-gold", prefix="pollution/")
    
    cities = set()
    for obj in gold_objects:
        parts = obj.split('/')
        for part in parts:
            if part.startswith('city='):
                cities.add(part.split('=')[1])
                
    if not cities:
        # Fallback to default target cities
        cities = CITIES
        logger.info(f"No active pollution gold directories found. Merging default cities: {cities}")
        
    for city in cities:
        merge_city_datasets(city)
        
    logger.info("Finished Gold datasets merge pipeline.")

if __name__ == "__main__":
    main()
