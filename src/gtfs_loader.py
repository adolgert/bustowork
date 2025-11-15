"""
GTFS data loader and utilities.

Loads Pittsburgh Regional Transit GTFS data and provides
spatial indexing for efficient stop lookups.
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from rtree import index
import numpy as np
from typing import Tuple, List, Dict
from pathlib import Path
import zipfile


class GTFSLoader:
    """Load and query GTFS transit data."""

    def __init__(self, gtfs_path: str):
        """
        Initialize GTFS loader.

        Args:
            gtfs_path: Path to GTFS zip file or directory
        """
        self.gtfs_path = Path(gtfs_path)
        self.stops = None
        self.routes = None
        self.trips = None
        self.stop_times = None
        self.calendar = None
        self.stops_gdf = None
        self.spatial_index = None

    def load(self) -> None:
        """Load GTFS data from zip file."""
        print(f"Loading GTFS data from {self.gtfs_path}...")

        # Read GTFS files from zip
        with zipfile.ZipFile(self.gtfs_path, 'r') as zf:
            self.stops = pd.read_csv(zf.open('stops.txt'))
            self.routes = pd.read_csv(zf.open('routes.txt'))
            self.trips = pd.read_csv(zf.open('trips.txt'))
            self.stop_times = pd.read_csv(zf.open('stop_times.txt'))
            self.calendar = pd.read_csv(zf.open('calendar.txt'))

        print(f"  ✓ Loaded {len(self.routes)} routes")
        print(f"  ✓ Loaded {len(self.stops)} stops")
        print(f"  ✓ Loaded {len(self.trips)} trips")

        # Create GeoDataFrame of stops
        self._create_stops_geodataframe()

        # Build spatial index
        self._build_spatial_index()

    def _create_stops_geodataframe(self) -> None:
        """Convert stops to GeoDataFrame with Point geometries."""
        stops = self.stops.copy()

        # Create Point geometries from lat/lon
        geometry = [Point(lon, lat) for lon, lat in
                   zip(stops['stop_lon'], stops['stop_lat'])]

        self.stops_gdf = gpd.GeoDataFrame(
            stops,
            geometry=geometry,
            crs='EPSG:4326'  # WGS84 lat/lon
        )

        # Project to state plane for accurate distance calculations
        # Pennsylvania South State Plane (EPSG:2272) - feet
        self.stops_gdf = self.stops_gdf.to_crs('EPSG:2272')

        print(f"  ✓ Created spatial index for {len(self.stops_gdf)} stops")

    def _build_spatial_index(self) -> None:
        """Build R-tree spatial index for fast stop lookups."""
        self.spatial_index = index.Index()

        for idx, stop in self.stops_gdf.iterrows():
            # Insert stop bounds into spatial index
            self.spatial_index.insert(
                idx,
                stop.geometry.bounds,
                obj=stop['stop_id']
            )

    def find_stops_within_radius(
        self,
        lat: float,
        lon: float,
        radius_miles: float
    ) -> gpd.GeoDataFrame:
        """
        Find all stops within radius of a point.

        Args:
            lat: Latitude of center point
            lon: Longitude of center point
            radius_miles: Search radius in miles

        Returns:
            GeoDataFrame of stops within radius with distances
        """
        # Create point in same CRS as stops (state plane feet)
        point_wgs84 = Point(lon, lat)
        point_gdf = gpd.GeoDataFrame(
            {'geometry': [point_wgs84]},
            crs='EPSG:4326'
        )
        point_projected = point_gdf.to_crs('EPSG:2272').geometry[0]

        # Convert radius to feet (state plane is in feet)
        radius_feet = radius_miles * 5280

        # Create search bounds
        minx = point_projected.x - radius_feet
        miny = point_projected.y - radius_feet
        maxx = point_projected.x + radius_feet
        maxy = point_projected.y + radius_feet

        # Query spatial index for candidates
        candidate_indices = list(self.spatial_index.intersection(
            (minx, miny, maxx, maxy)
        ))

        if not candidate_indices:
            return gpd.GeoDataFrame()

        # Get candidate stops
        candidates = self.stops_gdf.loc[candidate_indices].copy()

        # Calculate exact distances
        candidates['distance_miles'] = candidates.geometry.distance(
            point_projected
        ) / 5280  # convert feet to miles

        # Filter to exact radius
        nearby_stops = candidates[
            candidates['distance_miles'] <= radius_miles
        ].sort_values('distance_miles')

        return nearby_stops

    def get_routes_for_stop(self, stop_id: str) -> pd.DataFrame:
        """
        Get all routes that serve a stop.

        Args:
            stop_id: Stop ID

        Returns:
            DataFrame of routes serving this stop
        """
        # Get all trips that visit this stop
        stop_times_for_stop = self.stop_times[
            self.stop_times['stop_id'] == stop_id
        ]

        trip_ids = stop_times_for_stop['trip_id'].unique()

        # Get routes for these trips
        trips_for_stop = self.trips[self.trips['trip_id'].isin(trip_ids)]
        route_ids = trips_for_stop['route_id'].unique()

        routes_for_stop = self.routes[
            self.routes['route_id'].isin(route_ids)
        ]

        return routes_for_stop

    def get_stop_info(self, stop_id: str) -> Dict:
        """
        Get detailed information about a stop.

        Args:
            stop_id: Stop ID

        Returns:
            Dictionary with stop information
        """
        stop = self.stops[self.stops['stop_id'] == stop_id].iloc[0]
        routes = self.get_routes_for_stop(stop_id)

        return {
            'stop_id': stop_id,
            'stop_name': stop['stop_name'],
            'lat': stop['stop_lat'],
            'lon': stop['stop_lon'],
            'routes': routes[['route_short_name', 'route_long_name']].to_dict('records')
        }

    def get_weekday_service_ids(self) -> List[str]:
        """
        Get service IDs for typical weekdays.

        Returns:
            List of service IDs that run on weekdays
        """
        # Find services that run Monday-Friday
        weekday_services = self.calendar[
            (self.calendar['monday'] == 1) &
            (self.calendar['tuesday'] == 1) &
            (self.calendar['wednesday'] == 1) &
            (self.calendar['thursday'] == 1) &
            (self.calendar['friday'] == 1)
        ]

        return weekday_services['service_id'].tolist()


def main():
    """Test the GTFS loader."""
    import yaml

    # Load config
    with open('config.example.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize loader
    loader = GTFSLoader(config['gtfs_path'])
    loader.load()

    # Test finding stops near work location
    # For now, use hardcoded coordinates (will add geocoding later)
    # 5000 Forbes Ave, Pittsburgh, PA ≈ 40.4435° N, 79.9455° W
    test_lat = 40.4435
    test_lon = -79.9455

    print(f"\nFinding stops within 0.5 miles of test location...")
    nearby_stops = loader.find_stops_within_radius(test_lat, test_lon, 0.5)

    print(f"\nFound {len(nearby_stops)} stops:\n")

    for idx, stop in nearby_stops.head(10).iterrows():
        routes = loader.get_routes_for_stop(stop['stop_id'])
        route_names = ', '.join(routes['route_short_name'].astype(str).tolist())

        print(f"  • {stop['stop_name']}")
        print(f"    Distance: {stop['distance_miles']:.2f} miles")
        print(f"    Routes: {route_names}")
        print()


if __name__ == '__main__':
    main()
