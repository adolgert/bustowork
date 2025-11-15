"""
Fast transit routing using r5py.

r5py is a Python wrapper for R5 (Rapid Realistic Routing on Real-world and
Reimagined networks), designed for efficient GTFS-based routing analysis.
"""

import r5py
import geopandas as gpd
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, List, Optional
from pathlib import Path
import yaml


class R5Router:
    """Fast transit router using r5py."""

    def __init__(
        self,
        gtfs_path: str,
        osm_path: str,
        max_walk_time: int = 15,  # minutes
        max_trip_duration: int = 60,  # minutes
        walking_speed: float = 4.8  # km/h (approximately 3 mph)
    ):
        """
        Initialize r5py router.

        Args:
            gtfs_path: Path to GTFS zip file
            osm_path: Path to OSM PBF file
            max_walk_time: Maximum walking time in minutes
            max_trip_duration: Maximum total trip duration in minutes
            walking_speed: Walking speed in km/h
        """
        self.gtfs_path = Path(gtfs_path)
        self.osm_path = Path(osm_path)
        self.max_walk_time = max_walk_time
        self.max_trip_duration = max_trip_duration
        self.walking_speed = walking_speed

        print(f"Initializing r5py transport network...")
        print(f"  GTFS: {self.gtfs_path}")
        print(f"  OSM: {self.osm_path}")

        # Build transport network
        self.transport_network = r5py.TransportNetwork(
            osm_pbf=str(self.osm_path),
            gtfs=[str(self.gtfs_path)]
        )

        print(f"  ✓ Transport network ready")

    def calculate_travel_times(
        self,
        origins: gpd.GeoDataFrame,
        destinations: gpd.GeoDataFrame,
        departure_time: datetime,
        transport_modes: List[r5py.TransportMode] = None
    ) -> pd.DataFrame:
        """
        Calculate travel times from origins to destinations.

        Args:
            origins: GeoDataFrame with origin points (must have 'id' column)
            destinations: GeoDataFrame with destination points (must have 'id' column)
            departure_time: Departure datetime
            transport_modes: List of transport modes (default: WALK + TRANSIT)

        Returns:
            DataFrame with columns: from_id, to_id, travel_time
        """
        if transport_modes is None:
            transport_modes = [
                r5py.TransportMode.WALK,
                r5py.TransportMode.TRANSIT
            ]

        # Create travel time matrix (returns results directly)
        results = r5py.TravelTimeMatrix(
            self.transport_network,
            origins=origins,
            destinations=destinations,
            transport_modes=transport_modes,
            departure=departure_time,
            max_time=timedelta(minutes=self.max_trip_duration),
            speed_walking=self.walking_speed
        )

        return results

    def calculate_route_at_time(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: datetime
    ) -> Optional[float]:
        """
        Calculate travel time for a single origin-destination pair.

        Args:
            origin_lat: Origin latitude
            origin_lon: Origin longitude
            dest_lat: Destination latitude
            dest_lon: Destination longitude
            departure_time: Departure datetime

        Returns:
            Travel time in minutes, or None if no route found
        """
        # Create GeoDataFrames for origin and destination
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

        # Calculate travel time
        results = self.calculate_travel_times(
            origins,
            destinations,
            departure_time
        )

        if results.empty:
            return None

        # Return travel time in minutes
        travel_time_seconds = results.iloc[0]['travel_time']
        if pd.isna(travel_time_seconds):
            return None

        return travel_time_seconds / 60.0


def download_osm_data(
    place_name: str = "Pittsburgh, Pennsylvania, USA",
    output_path: str = "data/pittsburgh.osm.pbf"
) -> Path:
    """
    Download OpenStreetMap data for Pittsburgh.

    Args:
        place_name: Name of place to download
        output_path: Where to save OSM PBF file

    Returns:
        Path to downloaded file
    """
    import osmnx as ox

    output_path = Path(output_path)

    if output_path.exists():
        print(f"OSM data already exists: {output_path}")
        return output_path

    print(f"Downloading OSM data for {place_name}...")
    print("  (This may take several minutes on first run)")

    # Download graph (unsimplified for OSM XML export)
    graph = ox.graph_from_place(place_name, network_type='walk', simplify=False)

    # Save as OSM XML
    xml_path = output_path.with_suffix('.osm')
    ox.save_graph_xml(graph, filepath=xml_path)

    # Convert to PBF using osmconvert (if available)
    # Otherwise, we'll need to use the .osm file directly
    # Note: r5py can work with .osm files, but .pbf is more efficient

    print(f"  ✓ Saved to {xml_path}")
    print("  → For better performance, convert to PBF format:")
    print(f"     osmconvert {xml_path} -o={output_path}")

    return xml_path


def main():
    """Test r5py router."""
    import sys

    # Check if Java is available
    import subprocess
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        print("Java is installed ✓")
    except FileNotFoundError:
        print("ERROR: Java is not installed or not in PATH")
        print("r5py requires Java Runtime Environment (JRE)")
        print("Install: apt-get install default-jre  (or equivalent)")
        sys.exit(1)

    # Load config
    with open('config.example.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Check for OSM data
    osm_path = Path("data/pennsylvania.osm.pbf")
    if not osm_path.exists():
        print("\nERROR: OSM data not found")
        print("Run: python setup_r5py.py")
        sys.exit(1)

    # Initialize router
    try:
        router = R5Router(
            gtfs_path=config['gtfs_path'],
            osm_path=str(osm_path),
            max_walk_time=int(config['max_walk_to_stop'] * 60 / config['walking_speed']),  # Convert miles to minutes
            max_trip_duration=config['max_trip_time'],
            walking_speed=config['walking_speed'] * 1.60934  # mph to km/h
        )

        # Test route from Shadyside to work
        print("\nTesting route calculation...")
        origin_lat, origin_lon = 40.4520, -79.9280  # Shadyside
        dest_lat, dest_lon = 40.4435, -79.9455  # 5000 Forbes

        # Use date within GTFS calendar range (Oct 19, 2025 - Feb 21, 2026)
        departure = datetime(2025, 11, 15, 8, 30, 0)

        travel_time = router.calculate_route_at_time(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            departure
        )

        if travel_time:
            print(f"\nTravel time: {travel_time:.1f} minutes")
        else:
            print("\nNo route found")

    except Exception as e:
        print(f"\nError initializing router: {e}")
        print("\nMake sure you have:")
        print("  1. Java installed (java -version)")
        print("  2. OSM data downloaded (run download_osm_data())")
        print("  3. r5py installed (pip install r5py)")


if __name__ == '__main__':
    main()
