"""
Query the commute score for a single location.

Usage:
    python src/query.py "5500 Walnut St, Pittsburgh, PA"
    python src/query.py --latlon 40.4520 -79.9280
    python src/query.py "312 S Highland Ave" --both --json

The score is the Nth percentile (default 80th) of door-to-door travel time
to the work address, over all departure minutes in the window (default
6:00-19:00), by walking and/or transit - waiting for the bus included.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commute import CommuteScorer, PERCENTILES, load_config


def resolve_location(args):
    if args.latlon:
        return args.latlon[0], args.latlon[1], None
    if not args.address:
        print("Provide an address or --latlon LAT LON", file=sys.stderr)
        sys.exit(2)
    address = ' '.join(args.address)
    from geocoder import Geocoder
    if ',' in address:
        # Address already includes city/state.
        coords = Geocoder().geocode(address, "", "")
    else:
        coords = Geocoder().geocode(address, "Pittsburgh", "PA")
    if coords is None:
        print(f"Could not geocode {address!r}", file=sys.stderr)
        sys.exit(1)
    return coords[0], coords[1], address


def fmt(minutes):
    return "> cap" if minutes is None else f"{minutes:5.1f} min"


def main():
    parser = argparse.ArgumentParser(
        description='Commute score for one location',
        usage='query.py [address | --latlon LAT LON] [options]')
    parser.add_argument('address', nargs='*', help='Street address')
    parser.add_argument('--latlon', nargs=2, type=float,
                        metavar=('LAT', 'LON'))
    parser.add_argument('--config', default=None, help='Path to config.yaml')
    parser.add_argument('--date', default=None,
                        help='Simulated date YYYY-MM-DD (default: auto)')
    parser.add_argument('--both', action='store_true',
                        help='Also report work -> home direction')
    parser.add_argument('--json', action='store_true',
                        help='Machine-readable output')
    args = parser.parse_args()

    lat, lon, address = resolve_location(args)

    config = load_config(args.config)
    if args.date:
        config['analysis_date'] = args.date

    scorer = CommuteScorer(config, verbose=not args.json)
    result = scorer.analyze_point(lat, lon, include_from_work=args.both)
    if address:
        result['address'] = address

    if args.json:
        print(json.dumps(result, indent=2))
        return

    cap = config['max_trip_time']
    print()
    print(f"Location: {address or ''} ({lat:.5f}, {lon:.5f})")
    print(f"To work:  {config['work_address']}")
    print(f"Leaving at a random minute {result['window']} "
          f"on {result['analysis_date']}, walk or transit:")
    print()
    for p in PERCENTILES:
        marker = "  <- score" if p == scorer.score_percentile else ""
        print(f"  {p:2d}% of departures arrive within "
              f"{fmt(result['to_work'][f'p{p}'])}{marker}")
    print(f"\n  Walking only: {fmt(result['walk_only'])}"
          f"   (cap: {cap} min)")

    if args.both:
        print(f"\nReturn trip (work -> home), same window:")
        for p in PERCENTILES:
            print(f"  {p:2d}%: {fmt(result['from_work'][f'p{p}'])}")

    score = result['score']
    print(f"\nScore: {fmt(score).strip()}"
          f" ({scorer.score_percentile}th percentile door-to-door)")


if __name__ == '__main__':
    main()
