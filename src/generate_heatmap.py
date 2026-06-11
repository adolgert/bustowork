"""
Generate the commute heat map.

Builds a grid of points around the work location and scores every point in
one parallel batch (see commute.py). Writes heatmap_data.json in the format
the Flask viewer (src/app.py) expects.

Usage:
    python src/generate_heatmap.py [--config config.yaml]
        [--radius-miles 8] [--spacing-feet 500] [--output heatmap_data.json]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commute import (CommuteScorer, PERCENTILES, PROJECT_ROOT,
                     load_config, reachable_lower_bound)


def build_grid(work_lat: float, work_lon: float,
               spacing_feet: float, radius_miles: float) -> gpd.GeoDataFrame:
    """
    Square-spaced grid of points within radius_miles of work, built in
    PA State Plane South (EPSG:2272, feet) and projected back to WGS84
    in one vectorized call.
    """
    work = gpd.GeoDataFrame(
        {'id': [0]},
        geometry=gpd.points_from_xy([work_lon], [work_lat]),
        crs='EPSG:4326').to_crs('EPSG:2272')
    work_x = work.geometry.iloc[0].x
    work_y = work.geometry.iloc[0].y

    radius_feet = radius_miles * 5280.0
    n = int(radius_feet // spacing_feet)
    i, j = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    i, j = i.ravel(), j.ravel()
    inside = (i * i + j * j) * spacing_feet ** 2 <= radius_feet ** 2
    i, j = i[inside], j[inside]

    grid = gpd.GeoDataFrame(
        {'id': np.arange(len(i)), 'ring': np.maximum(np.abs(i), np.abs(j))},
        geometry=gpd.points_from_xy(work_x + i * spacing_feet,
                                    work_y + j * spacing_feet),
        crs='EPSG:2272').to_crs('EPSG:4326')
    grid['lon'] = grid.geometry.x
    grid['lat'] = grid.geometry.y
    return grid


def main():
    parser = argparse.ArgumentParser(description='Generate commute heat map')
    parser.add_argument('--config', default=None, help='Path to config.yaml')
    parser.add_argument('--radius-miles', type=float, default=None,
                        help='Grid radius around work (default from config)')
    parser.add_argument('--spacing-feet', type=float, default=None,
                        help='Grid spacing (default from config)')
    parser.add_argument('--threads', type=int, default=None,
                        help='Parallel R5 requests (default: cores - 2)')
    parser.add_argument('--output', default=str(PROJECT_ROOT / 'heatmap_data.json'))
    args = parser.parse_args()

    config = load_config(args.config)
    radius = args.radius_miles or config['heatmap_radius_miles']
    spacing = args.spacing_feet or config['grid_spacing']

    scorer = CommuteScorer(config)
    grid = build_grid(scorer.work_lat, scorer.work_lon, spacing, radius)
    print(f"Grid: {len(grid)} points, {spacing:.0f} ft spacing, "
          f"{radius:.1f} mi radius")

    t0 = time.monotonic()
    times = scorer.score_points(grid, n_threads=args.threads)
    elapsed = time.monotonic() - t0
    print(f"Routing finished in {elapsed/60:.1f} minutes "
          f"({elapsed/len(grid)*1000:.0f} ms/point)")

    merged = grid.merge(times, on='id')
    score_col = f"travel_time_p{config['score_percentile']}"

    points = []
    for _, row in merged.iterrows():
        score = row[score_col]
        stats = {f'p{p}': (None if np.isnan(row[f'travel_time_p{p}'])
                           else round(float(row[f'travel_time_p{p}']), 1))
                 for p in PERCENTILES}
        points.append({
            'lat': round(float(row['lat']), 6),
            'lon': round(float(row['lon']), 6),
            'score': None if np.isnan(score) else round(float(score), 1),
            'ring': int(row['ring']),
            'reachable_ratio': reachable_lower_bound(row),
            'statistics': stats if any(v is not None for v in stats.values())
                          else None,
        })

    n_scored = sum(1 for p in points if p['score'] is not None)
    results = {
        'work_location': {'lat': scorer.work_lat, 'lon': scorer.work_lon},
        'grid_spacing_feet': spacing,
        'radius_miles': radius,
        'score_percentile': config['score_percentile'],
        'analysis_date': str(scorer.analysis_date),
        'time_window': (f"{config['time_window_start']}-"
                        f"{config['time_window_end']}"),
        'direction': 'to_work',
        'points': points,
        'rings_analyzed': int(merged['ring'].max()) + 1,
        'total_points': len(points),
        'stopped_reason': f'Scored full {radius:.1f}-mile-radius grid',
        'generation_time': datetime.now().isoformat(),
        'routing_seconds': round(elapsed, 1),
    }

    output = Path(args.output)
    with open(output, 'w') as f:
        json.dump(results, f)
    print(f"\nScored {n_scored}/{len(points)} points "
          f"(rest unreachable within {config['max_trip_time']} min cap)")
    print(f"Saved {output}")
    print("View with: python src/app.py")


if __name__ == '__main__':
    main()
