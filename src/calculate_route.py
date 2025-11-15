#!/usr/bin/env python3
"""
CLI tool to calculate a route between two locations.

Usage:
    python src/calculate_route.py \
        --from-lat 40.4520 --from-lon -79.9280 \
        --to-lat 40.4435 --to-lon -79.9455 \
        --time "08:30"
"""

import argparse
from datetime import datetime
from gtfs_loader import GTFSLoader
from street_network import StreetNetwork
from router import Router
import yaml


def main():
    parser = argparse.ArgumentParser(
        description='Calculate route between two locations'
    )
    parser.add_argument('--from-lat', type=float, required=True)
    parser.add_argument('--from-lon', type=float, required=True)
    parser.add_argument('--to-lat', type=float, required=True)
    parser.add_argument('--to-lon', type=float, required=True)
    parser.add_argument('--time', default="08:30", help='Departure time (HH:MM)')
    parser.add_argument('--date', default="2025-01-15", help='Date (YYYY-MM-DD)')
    parser.add_argument('--config', default='config.example.yaml')

    args = parser.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize components
    print("Loading GTFS data...")
    gtfs_loader = GTFSLoader(config['gtfs_path'])
    gtfs_loader.load()

    print("Initializing street network (using fallback distances)...")
    street_network = StreetNetwork()

    print("Initializing router...")
    router = Router(
        gtfs_loader,
        street_network,
        max_walk_miles=config['max_walk_to_stop'],
        walking_speed_mph=config['walking_speed'],
        max_transfers=config['max_transfers'],
        max_transfer_wait_minutes=config['max_transfer_wait']
    )

    # Parse departure time
    time_parts = args.time.split(':')
    date_parts = args.date.split('-')
    departure = datetime(
        int(date_parts[0]), int(date_parts[1]), int(date_parts[2]),
        int(time_parts[0]), int(time_parts[1])
    )

    print(f"\nCalculating route...")
    print(f"  From: ({args.from_lat}, {args.from_lon})")
    print(f"  To: ({args.to_lat}, {args.to_lon})")
    print(f"  Departure: {departure.strftime('%Y-%m-%d %I:%M %p')}")
    print()

    route = router.find_fastest_route(
        args.from_lat, args.from_lon,
        args.to_lat, args.to_lon,
        departure
    )

    if route:
        print("=" * 70)
        print(route)
        print("=" * 70)
    else:
        print("No route found!")


if __name__ == '__main__':
    main()
