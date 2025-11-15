#!/usr/bin/env python3
"""
CLI tool to find bus stops near a location.

Usage:
    python src/find_stops.py --lat 40.4435 --lon -79.9455 --radius 0.5
"""

import argparse
from gtfs_loader import GTFSLoader
import yaml


def main():
    parser = argparse.ArgumentParser(
        description='Find bus stops near a location'
    )
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Latitude of location'
    )
    parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Longitude of location'
    )
    parser.add_argument(
        '--radius',
        type=float,
        default=0.5,
        help='Search radius in miles (default: 0.5)'
    )
    parser.add_argument(
        '--config',
        default='config.example.yaml',
        help='Path to config file (default: config.example.yaml)'
    )

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Load GTFS data
    loader = GTFSLoader(config['gtfs_path'])
    loader.load()

    # Find nearby stops
    print(f"\nSearching for stops within {args.radius} miles of ({args.lat}, {args.lon})...")
    nearby_stops = loader.find_stops_within_radius(args.lat, args.lon, args.radius)

    if len(nearby_stops) == 0:
        print("No stops found within radius.")
        return

    print(f"\nFound {len(nearby_stops)} stops:\n")
    print("=" * 80)

    for idx, stop in nearby_stops.iterrows():
        routes = loader.get_routes_for_stop(stop['stop_id'])
        route_names = ', '.join(routes['route_short_name'].astype(str).tolist())

        print(f"\n{stop['stop_name']}")
        print(f"  Stop ID: {stop['stop_id']}")
        print(f"  Distance: {stop['distance_miles']:.3f} miles")
        print(f"  Location: {stop['stop_lat']:.6f}, {stop['stop_lon']:.6f}")
        print(f"  Routes: {route_names}")

    print("\n" + "=" * 80)
    print(f"\nTotal: {len(nearby_stops)} stops within {args.radius} miles")


if __name__ == '__main__':
    main()
