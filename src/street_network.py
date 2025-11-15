"""
Street network utilities for calculating walking distances and times.
"""

import osmnx as ox
import networkx as nx
from typing import Tuple, Optional
import numpy as np
from pathlib import Path


class StreetNetwork:
    """Calculate walking distances using OpenStreetMap street network."""

    def __init__(self, cache_dir: str = "cache/osm"):
        """
        Initialize street network.

        Args:
            cache_dir: Directory to cache OSM data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Configure OSMnx
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(self.cache_dir)

        self.graph = None
        self._distance_cache = {}

    def load_network(
        self,
        place_name: str = "Pittsburgh, Pennsylvania, USA"
    ) -> None:
        """
        Load street network for an area.

        Args:
            place_name: Name of place to download network for
        """
        print(f"Loading street network for {place_name}...")
        print("  (This may take a few minutes on first run, then will be cached)")

        try:
            # Download walk network
            self.graph = ox.graph_from_place(
                place_name,
                network_type='walk'
            )
            print(f"  ✓ Loaded street network with {len(self.graph.nodes)} nodes")

        except Exception as e:
            print(f"  ✗ Error loading street network: {e}")
            print("  → Will use straight-line distances with 1.3x multiplier as fallback")
            self.graph = None

    def get_walking_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        miles_per_hour: float = 4.0
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate walking distance and time between two points.

        Args:
            lat1: Origin latitude
            lon1: Origin longitude
            lat2: Destination latitude
            lon2: Destination longitude
            miles_per_hour: Walking speed (default: 4.0 mph)

        Returns:
            Tuple of (distance_miles, time_minutes) or (None, None) if unreachable
        """
        # Check cache
        cache_key = (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5))
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        if self.graph is None:
            # Fallback to straight-line distance with multiplier
            distance_miles = self._haversine_distance(lat1, lon1, lat2, lon2) * 1.3
            time_minutes = (distance_miles / miles_per_hour) * 60
            result = (distance_miles, time_minutes)
            self._distance_cache[cache_key] = result
            return result

        try:
            # Find nearest nodes
            orig_node = ox.distance.nearest_nodes(self.graph, lon1, lat1)
            dest_node = ox.distance.nearest_nodes(self.graph, lon2, lat2)

            # Calculate shortest path
            path_length = nx.shortest_path_length(
                self.graph,
                orig_node,
                dest_node,
                weight='length'
            )

            # Convert meters to miles
            distance_miles = path_length / 1609.34

            # Calculate time in minutes
            time_minutes = (distance_miles / miles_per_hour) * 60

            result = (distance_miles, time_minutes)
            self._distance_cache[cache_key] = result
            return result

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # No path exists
            return (None, None)

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate straight-line distance between two points using Haversine formula.

        Args:
            lat1: Origin latitude
            lon1: Origin longitude
            lat2: Destination latitude
            lon2: Destination longitude

        Returns:
            Distance in miles
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))

        # Earth radius in miles
        r = 3959
        return c * r


def main():
    """Test street network."""
    network = StreetNetwork()

    # For testing, use fallback mode (no network download)
    print("\nTesting walking distance calculations...")

    # Test: 5000 Forbes to a nearby stop
    # Forbes Ave + Morewood (about 0.12 miles actual)
    work_lat, work_lon = 40.4435, -79.9455
    stop_lat, stop_lon = 40.444698, -79.943756

    distance, time = network.get_walking_distance(
        work_lat, work_lon,
        stop_lat, stop_lon
    )

    print(f"\nFrom work to nearby stop:")
    print(f"  Distance: {distance:.3f} miles")
    print(f"  Walking time: {time:.1f} minutes")

    # Test with network (commented out to avoid long download for now)
    # network.load_network("Pittsburgh, Pennsylvania, USA")
    # distance2, time2 = network.get_walking_distance(
    #     work_lat, work_lon,
    #     stop_lat, stop_lon
    # )
    # print(f"\nWith street network:")
    # print(f"  Distance: {distance2:.3f} miles")
    # print(f"  Walking time: {time2:.1f} minutes")


if __name__ == '__main__':
    main()
