#!/usr/bin/env python3
"""
Debug script to check r5py output format.
"""

import sys
sys.path.insert(0, 'src')

from r5py_router import R5Router
from datetime import datetime
import yaml
from pathlib import Path

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print("Initializing r5py router...")
router = R5Router(
    gtfs_path=config['gtfs_path'],
    osm_path="data/pennsylvania.osm.pbf",
    max_walk_time=15,
    max_trip_duration=60,
    walking_speed=config['walking_speed'] * 1.60934
)

# Test coordinates
origin_lat, origin_lon = 40.4520, -79.9280  # Shadyside
dest_lat, dest_lon = 40.4435, -79.9455  # 5000 Forbes

departure = datetime(2025, 11, 19, 8, 30, 0)

print(f"\nTesting route:")
print(f"  From: {origin_lat}, {origin_lon}")
print(f"  To: {dest_lat}, {dest_lon}")
print(f"  Departure: {departure}")

# Get raw results
import geopandas as gpd

origins = gpd.GeoDataFrame(
    {'id': [0]},
    geometry=gpd.points_from_xy([origin_lon], [origin_lat]),
    crs='EPSG:4326'
)

destinations = gpd.GeoDataFrame(
    {'id': [0]},
    geometry=gpd.points_from_xy([dest_lon], [dest_lat]),
    crs='EPSG:4326'
)

results = router.calculate_travel_times(origins, destinations, departure)

print(f"\nRaw results from r5py:")
print(results)
print(f"\nColumn dtypes:")
print(results.dtypes)
print(f"\nFirst row:")
print(results.iloc[0])

if not results.empty:
    travel_time_value = results.iloc[0]['travel_time']
    print(f"\ntravel_time value: {travel_time_value}")
    print(f"travel_time type: {type(travel_time_value)}")

    # Try different conversions
    print(f"\nDividing by 60.0: {travel_time_value / 60.0}")

    # If it's a timedelta
    if hasattr(travel_time_value, 'total_seconds'):
        print(f"total_seconds(): {travel_time_value.total_seconds()}")
        print(f"total_seconds() / 60: {travel_time_value.total_seconds() / 60}")
