import math

# Center coordinates for target French cities
CITIES_COORDINATES = {
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "lyon": {"lat": 45.7640, "lon": 4.8357},
    "marseille": {"lat": 43.2965, "lon": 5.3698},
    "toulouse": {"lat": 43.6047, "lon": 1.4442},
    "bordeaux": {"lat": 44.8378, "lon": -0.5792},
    "lille": {"lat": 50.6292, "lon": 3.0573}
}

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on the Earth's surface
    using the Haversine formula. Returns distance in kilometers.
    """
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (TypeError, ValueError):
        return float('inf')
        
    R = 6371.0 # Radius of Earth in kilometers
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2.0) ** 2) + \
        (math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c

def find_nearest_city(lat, lon, max_distance_km=30.0):
    """
    Identify the nearest city among the target French cities within a specific radius.
    Returns the city name in lowercase, or 'unknown'.
    """
    if lat is None or lon is None:
        return "unknown"
        
    nearest_city = "unknown"
    min_distance = float('inf')
    
    for city, coords in CITIES_COORDINATES.items():
        dist = haversine_distance(lat, lon, coords["lat"], coords["lon"])
        if dist < min_distance and dist <= max_distance_km:
            min_distance = dist
            nearest_city = city
            
    return nearest_city
