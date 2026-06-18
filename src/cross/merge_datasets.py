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

CITIES = ["paris", "lyon", "marseille", "toulouse", "bordeaux", "lille"]

def generate_mock_meteo_gold(city, dates):
    """Generate mock Gold meteorology aggregates for testing when NOAA script is not run."""
    rows = []
    for d in dates:
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
    keys = []
    if minio_available:
        try:
            keys = list_objects(bucket, prefix=prefix)
        except Exception as e:
            logger.warning(f"MinIO list failed, listing locally: {e}")
            
    if not keys:
        keys = local_mock.list_objects(bucket, prefix=prefix)
        
    parquet_keys = [k for k in keys if k.endswith('.parquet')]
    
    if parquet_keys:
        local_file = os.path.join(tmpdir, "downloaded.parquet")
        
        downloaded = False
        if minio_available:
            try:
                download_file(bucket, parquet_keys[0], local_file)
                downloaded = True
            except Exception as e:
                logger.warning(f"MinIO download failed, trying local: {e}")
                
        if not downloaded:
            if not local_mock.download_file(bucket, parquet_keys[0], local_file):
                logger.warning(f"Could not download {parquet_keys[0]} locally.")
                
        if os.path.exists(local_file):
            try:
                df = pd.read_parquet(local_file)
                df['date'] = pd.to_datetime(df['date']).dt.date
                return df
            except Exception as e:
                logger.error(f"Error reading {parquet_keys[0]}: {e}")
                
    logger.warning(f"Could not load Gold data for {prefix} in {bucket}. Generating simulation data.")
    return default_generator(city, dates)

def merge_city_datasets(city):
    """Merge daily aggregates for meteorology, bikes usage and pollution for a city."""
    logger.info(f"Merging datasets for city: {city}")
    
    end_date = datetime.utcnow()
    dates = [end_date - timedelta(days=i) for i in range(30)]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pollution_prefix = f"pollution/city={city}/"
        
        pollution_keys = []
        if minio_available:
            try:
                pollution_keys = list_objects("urbanhub-gold", prefix=pollution_prefix)
            except Exception as e:
                logger.warning(f"MinIO listing failed: {e}")
                
        if not pollution_keys:
            pollution_keys = local_mock.list_objects("urbanhub-gold", prefix=pollution_prefix)
            
        pollution_parquet = [k for k in pollution_keys if k.endswith('.parquet')]
        
        if not pollution_parquet:
            logger.warning(f"No Gold pollution data found for {city}. Run aggregate_pollution.py first.")
            return
            
        local_pol = os.path.join(tmpdir, "pollution.parquet")
        
        downloaded = False
        if minio_available:
            try:
                download_file("urbanhub-gold", pollution_parquet[0], local_pol)
                downloaded = True
            except Exception as e:
                logger.warning(f"MinIO download failed: {e}")
                
        if not downloaded:
            local_mock.download_file("urbanhub-gold", pollution_parquet[0], local_pol)
            
        pollution_df = pd.read_parquet(local_pol)
        pollution_df['date'] = pd.to_datetime(pollution_df['date']).dt.date
        
        meteo_df = load_gold_dataset(
            bucket="urbanhub-gold",
            prefix=f"meteo/gold/", # NOAA script saves to meteo/gold/
            default_generator=generate_mock_meteo_gold,
            city=city,
            dates=dates,
            tmpdir=tmpdir
        )
        
        velos_df = load_gold_dataset(
            bucket="urbanhub-gold",
            prefix=f"velos/", # Vélos script saves to velos/
            default_generator=generate_mock_velos_gold,
            city=city,
            dates=dates,
            tmpdir=tmpdir
        )
        
        merged = pollution_df.merge(meteo_df, on=['date', 'city'], how='left')
        merged = merged.merge(velos_df, on=['date', 'city'], how='left')
        
        merged.fillna({
            "avg_temperature": 15.0,
            "avg_wind_speed": 5.0,
            "avg_usage_pressure": 0.5,
            "critical_stations_count": 0,
            "pollution_episode_flag": False
        }, inplace=True)
        
        local_gold = os.path.join(tmpdir, f"merged_{city}.parquet")
        merged.to_parquet(local_gold, compression='snappy', index=False)
        
        gold_key = f"cross/city={city}/merged_daily.parquet"
        
        uploaded = False
        if minio_available:
            try:
                upload_file("urbanhub-gold", gold_key, local_gold)
                uploaded = True
            except Exception as e:
                logger.warning(f"MinIO upload failed: {e}")
                
        if not uploaded:
            local_mock.upload_file(local_gold, "urbanhub-gold", gold_key)

def main():
    logger.info("Starting Gold datasets merge pipeline...")
    
    gold_objects = []
    if minio_available:
        try:
            gold_objects = list_objects("urbanhub-gold", prefix="pollution/")
        except Exception as e:
            logger.warning(f"MinIO listing failed: {e}")
            
    if not gold_objects:
        gold_objects = local_mock.list_objects("urbanhub-gold", prefix="pollution/")
        
    cities = set()
    for obj in gold_objects:
        parts = obj.split('/')
        for part in parts:
            if part.startswith('city='):
                cities.add(part.split('=')[1])
                
    if not cities:
        cities = CITIES
        logger.info(f"No active pollution gold directories found. Merging default cities: {cities}")
        
    for city in cities:
        merge_city_datasets(city)
        
    logger.info("Finished Gold datasets merge pipeline.")

if __name__ == "__main__":
    main()
