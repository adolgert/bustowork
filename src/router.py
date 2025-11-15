"""
Transit routing engine.

Calculates fastest route between two points considering:
- Walking
- Direct transit
- One transfer
"""

from typing import Tuple, List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd
from gtfs_loader import GTFSLoader
from street_network import StreetNetwork
from dataclasses import dataclass


@dataclass
class Route:
    """Represents a calculated route."""
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    departure_time: datetime
    arrival_time: datetime
    total_time_minutes: float
    legs: List[Dict]  # List of route segments

    def __str__(self):
        """Format route as human-readable string."""
        lines = []
        lines.append(f"Departure: {self.departure_time.strftime('%I:%M %p')}")
        lines.append(f"Arrival: {self.arrival_time.strftime('%I:%M %p')}")
        lines.append(f"Total time: {self.total_time_minutes:.1f} minutes")
        lines.append("\nRoute:")
        for i, leg in enumerate(self.legs, 1):
            lines.append(f"  {i}. {leg['description']}")
        return "\n".join(lines)


class Router:
    """Calculate optimal transit routes."""

    def __init__(
        self,
        gtfs_loader: GTFSLoader,
        street_network: StreetNetwork,
        max_walk_miles: float = 1.0,
        walking_speed_mph: float = 4.0,
        max_transfers: int = 1,
        max_transfer_wait_minutes: int = 30
    ):
        """
        Initialize router.

        Args:
            gtfs_loader: GTFS data loader
            street_network: Street network for walking
            max_walk_miles: Maximum walking distance to stops
            walking_speed_mph: Walking speed
            max_transfers: Maximum number of transfers
            max_transfer_wait_minutes: Maximum wait time between transfers
        """
        self.gtfs = gtfs_loader
        self.network = street_network
        self.max_walk_miles = max_walk_miles
        self.walking_speed_mph = walking_speed_mph
        self.max_transfers = max_transfers
        self.max_transfer_wait_minutes = max_transfer_wait_minutes

        # Get weekday service IDs
        self.weekday_services = set(self.gtfs.get_weekday_service_ids())

    def find_fastest_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: datetime
    ) -> Optional[Route]:
        """
        Find fastest route from origin to destination.

        Args:
            origin_lat: Origin latitude
            origin_lon: Origin longitude
            dest_lat: Destination latitude
            dest_lon: Destination longitude
            departure_time: Departure time

        Returns:
            Route object or None if no route found
        """
        routes = []

        # Option 1: Walk only
        walk_route = self._calculate_walk_only_route(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            departure_time
        )
        if walk_route:
            routes.append(walk_route)

        # Option 2: Transit (direct or one transfer)
        transit_route = self._calculate_transit_route(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            departure_time
        )
        if transit_route:
            routes.append(transit_route)

        # Return fastest route
        if routes:
            return min(routes, key=lambda r: r.total_time_minutes)
        return None

    def _calculate_walk_only_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: datetime
    ) -> Optional[Route]:
        """Calculate walking-only route."""
        distance, time_minutes = self.network.get_walking_distance(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            self.walking_speed_mph
        )

        if distance is None or distance > self.max_walk_miles:
            return None

        arrival_time = departure_time + timedelta(minutes=time_minutes)

        return Route(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            departure_time=departure_time,
            arrival_time=arrival_time,
            total_time_minutes=time_minutes,
            legs=[{
                'type': 'walk',
                'description': f"Walk {distance:.2f} miles ({time_minutes:.1f} min)",
                'distance_miles': distance,
                'time_minutes': time_minutes
            }]
        )

    def _calculate_transit_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: datetime
    ) -> Optional[Route]:
        """Calculate best transit route (direct or one transfer)."""
        # Find accessible stops near origin and destination
        origin_stops = self.gtfs.find_stops_within_radius(
            origin_lat, origin_lon,
            self.max_walk_miles
        )

        dest_stops = self.gtfs.find_stops_within_radius(
            dest_lat, dest_lon,
            self.max_walk_miles
        )

        if origin_stops.empty or dest_stops.empty:
            return None

        # Try direct routes
        best_route = self._find_direct_route(
            origin_lat, origin_lon,
            dest_lat, dest_lon,
            origin_stops, dest_stops,
            departure_time
        )

        # Try one-transfer routes if allowed
        if self.max_transfers >= 1:
            transfer_route = self._find_one_transfer_route(
                origin_lat, origin_lon,
                dest_lat, dest_lon,
                origin_stops, dest_stops,
                departure_time
            )

            if transfer_route and (not best_route or
                                  transfer_route.total_time_minutes < best_route.total_time_minutes):
                best_route = transfer_route

        return best_route

    def _find_direct_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        origin_stops: pd.DataFrame,
        dest_stops: pd.DataFrame,
        departure_time: datetime
    ) -> Optional[Route]:
        """Find fastest direct route (no transfers)."""
        departure_seconds = departure_time.hour * 3600 + departure_time.minute * 60

        best_route = None
        best_time = float('inf')

        for _, orig_stop in origin_stops.iterrows():
            # Walking time to origin stop
            walk_to_stop_dist, walk_to_stop_time = self.network.get_walking_distance(
                origin_lat, origin_lon,
                orig_stop['stop_lat'], orig_stop['stop_lon'],
                self.walking_speed_mph
            )

            if walk_to_stop_dist is None:
                continue

            # Find trips from this stop
            stop_times_from = self.gtfs.stop_times[
                (self.gtfs.stop_times['stop_id'] == orig_stop['stop_id'])
            ].copy()

            if stop_times_from.empty:
                continue

            # Convert departure_time to seconds
            stop_times_from['departure_seconds'] = stop_times_from['departure_time'].apply(
                self._time_str_to_seconds
            )

            # Filter to trips departing after we arrive at stop
            arrival_at_stop_seconds = departure_seconds + walk_to_stop_time * 60
            stop_times_from = stop_times_from[
                stop_times_from['departure_seconds'] >= arrival_at_stop_seconds
            ]

            # Filter to weekday service
            stop_times_from = stop_times_from.merge(
                self.gtfs.trips[['trip_id', 'service_id', 'route_id']],
                on='trip_id'
            )
            stop_times_from = stop_times_from[
                stop_times_from['service_id'].isin(self.weekday_services)
            ]

            # Check each destination stop
            for _, dest_stop in dest_stops.iterrows():
                # Find trips that go to this destination
                common_trips = stop_times_from[
                    stop_times_from['trip_id'].isin(
                        self.gtfs.stop_times[
                            self.gtfs.stop_times['stop_id'] == dest_stop['stop_id']
                        ]['trip_id']
                    )
                ]

                for _, trip_from_orig in common_trips.iterrows():
                    # Get arrival time at destination
                    trip_to_dest = self.gtfs.stop_times[
                        (self.gtfs.stop_times['trip_id'] == trip_from_orig['trip_id']) &
                        (self.gtfs.stop_times['stop_id'] == dest_stop['stop_id'])
                    ]

                    if trip_to_dest.empty:
                        continue

                    arrival_at_dest_stop_seconds = self._time_str_to_seconds(
                        trip_to_dest.iloc[0]['arrival_time']
                    )

                    # Walking time from destination stop
                    walk_from_stop_dist, walk_from_stop_time = self.network.get_walking_distance(
                        dest_stop['stop_lat'], dest_stop['stop_lon'],
                        dest_lat, dest_lon,
                        self.walking_speed_mph
                    )

                    if walk_from_stop_dist is None:
                        continue

                    # Calculate total time
                    total_seconds = (
                        walk_to_stop_time * 60 +
                        (trip_from_orig['departure_seconds'] - arrival_at_stop_seconds) +  # Wait time
                        (arrival_at_dest_stop_seconds - trip_from_orig['departure_seconds']) +  # Transit time
                        walk_from_stop_time * 60
                    )

                    total_minutes = total_seconds / 60

                    if total_minutes < best_time:
                        best_time = total_minutes
                        arrival_time = departure_time + timedelta(minutes=total_minutes)

                        # Get route info
                        route_info = self.gtfs.routes[
                            self.gtfs.routes['route_id'] == trip_from_orig['route_id']
                        ].iloc[0]

                        best_route = Route(
                            origin_lat=origin_lat,
                            origin_lon=origin_lon,
                            dest_lat=dest_lat,
                            dest_lon=dest_lon,
                            departure_time=departure_time,
                            arrival_time=arrival_time,
                            total_time_minutes=total_minutes,
                            legs=[
                                {
                                    'type': 'walk',
                                    'description': f"Walk {walk_to_stop_dist:.2f} mi to {orig_stop['stop_name']} ({walk_to_stop_time:.1f} min)",
                                    'distance_miles': walk_to_stop_dist,
                                    'time_minutes': walk_to_stop_time
                                },
                                {
                                    'type': 'wait',
                                    'description': f"Wait for bus ({(trip_from_orig['departure_seconds'] - arrival_at_stop_seconds) / 60:.1f} min)",
                                    'time_minutes': (trip_from_orig['departure_seconds'] - arrival_at_stop_seconds) / 60
                                },
                                {
                                    'type': 'transit',
                                    'description': f"Take Route {route_info['route_short_name']} ({(arrival_at_dest_stop_seconds - trip_from_orig['departure_seconds']) / 60:.1f} min)",
                                    'route': route_info['route_short_name'],
                                    'time_minutes': (arrival_at_dest_stop_seconds - trip_from_orig['departure_seconds']) / 60
                                },
                                {
                                    'type': 'walk',
                                    'description': f"Walk {walk_from_stop_dist:.2f} mi to destination ({walk_from_stop_time:.1f} min)",
                                    'distance_miles': walk_from_stop_dist,
                                    'time_minutes': walk_from_stop_time
                                }
                            ]
                        )

        return best_route

    def _find_one_transfer_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        origin_stops: pd.DataFrame,
        dest_stops: pd.DataFrame,
        departure_time: datetime
    ) -> Optional[Route]:
        """Find fastest route with one transfer."""
        # For now, return None (transfers are complex to implement)
        # Will implement if needed for Stage 3
        return None

    def _time_str_to_seconds(self, time_str: str) -> int:
        """
        Convert GTFS time string to seconds since midnight.

        GTFS times can be > 24:00:00 for trips past midnight.

        Args:
            time_str: Time string like "08:30:00" or "25:30:00"

        Returns:
            Seconds since midnight
        """
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0


def main():
    """Test the router."""
    import yaml
    from geocoder import Geocoder

    # Load config
    with open('config.example.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Initialize components
    print("Initializing router...")
    gtfs_loader = GTFSLoader(config['gtfs_path'])
    gtfs_loader.load()

    street_network = StreetNetwork()
    # Not loading full network for now - using fallback distances

    router = Router(
        gtfs_loader,
        street_network,
        max_walk_miles=config['max_walk_to_stop'],
        walking_speed_mph=config['walking_speed'],
        max_transfers=config['max_transfers'],
        max_transfer_wait_minutes=config['max_transfer_wait']
    )

    # Test route
    geocoder = Geocoder()

    # From Shadyside to work (5000 Forbes)
    origin = "S Highland Ave & Walnut St, Pittsburgh, PA"
    dest = "5000 Forbes Ave, Pittsburgh, PA"

    print(f"\nCalculating route from {origin} to {dest}...")

    # Use approximate coordinates (Shadyside)
    origin_lat, origin_lon = 40.4520, -79.9280
    dest_coords = geocoder.geocode(dest, "", "")
    if not dest_coords:
        dest_lat, dest_lon = 40.4435, -79.9455
    else:
        dest_lat, dest_lon = dest_coords

    # Test at 8:30 AM
    departure = datetime(2025, 1, 15, 8, 30, 0)

    route = router.find_fastest_route(
        origin_lat, origin_lon,
        dest_lat, dest_lon,
        departure
    )

    if route:
        print("\n" + "=" * 60)
        print(route)
        print("=" * 60)
    else:
        print("No route found!")


if __name__ == '__main__':
    main()
