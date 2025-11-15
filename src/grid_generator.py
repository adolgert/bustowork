"""
Grid heat map generator.

Creates an expanding grid from work location and analyzes commute times
for each grid point.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import json
import yaml
from datetime import datetime
from tqdm import tqdm

from r5py_router import R5Router
from analyzer import TimeDistributionAnalyzer
from geocoder import Geocoder


class GridHeatMapGenerator:
    """Generate heat map by analyzing grid points around work location."""

    def __init__(
        self,
        analyzer: TimeDistributionAnalyzer,
        work_lat: float,
        work_lon: float,
        grid_spacing_feet: int = 500,
        max_score_threshold: int = 60  # minutes
    ):
        """
        Initialize grid heat map generator.

        Args:
            analyzer: Time distribution analyzer
            work_lat: Work location latitude
            work_lon: Work location longitude
            grid_spacing_feet: Distance between grid points in feet
            max_score_threshold: Stop expanding when all points exceed this score
        """
        self.analyzer = analyzer
        self.work_lat = work_lat
        self.work_lon = work_lon
        self.grid_spacing_feet = grid_spacing_feet
        self.max_score_threshold = max_score_threshold

        # Convert work location to state plane coordinates (feet)
        self._init_projections()

    def _init_projections(self):
        """Initialize coordinate projections."""
        # Create point in WGS84
        work_point_wgs84 = Point(self.work_lon, self.work_lat)
        work_gdf = gpd.GeoDataFrame(
            {'geometry': [work_point_wgs84]},
            crs='EPSG:4326'
        )

        # Convert to PA State Plane South (feet)
        work_projected = work_gdf.to_crs('EPSG:2272')
        self.work_x = work_projected.geometry[0].x
        self.work_y = work_projected.geometry[0].y

    def _grid_to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert grid coordinates (PA State Plane feet) to lat/lon.

        Args:
            x: X coordinate in feet
            y: Y coordinate in feet

        Returns:
            Tuple of (latitude, longitude)
        """
        point = Point(x, y)
        gdf = gpd.GeoDataFrame(
            {'geometry': [point]},
            crs='EPSG:2272'
        )
        gdf_wgs84 = gdf.to_crs('EPSG:4326')
        return gdf_wgs84.geometry[0].y, gdf_wgs84.geometry[0].x

    def generate_ring_points(self, ring_number: int) -> List[Tuple[float, float]]:
        """
        Generate grid points for a given ring around work location.

        Ring 0 is just the work location.
        Ring 1 is the 8 points surrounding work.
        Ring 2 is the 16 points in the next layer, etc.

        Args:
            ring_number: Ring number (0 = center, 1 = first ring, etc.)

        Returns:
            List of (lat, lon) tuples for points in this ring
        """
        if ring_number == 0:
            return [(self.work_lat, self.work_lon)]

        points = []
        spacing = self.grid_spacing_feet
        distance = ring_number * spacing

        # Generate points along the ring
        # For a square grid, we need points at each grid intersection
        for i in range(-ring_number, ring_number + 1):
            for j in range(-ring_number, ring_number + 1):
                # Only include points on the perimeter of the ring
                if abs(i) == ring_number or abs(j) == ring_number:
                    x = self.work_x + (i * spacing)
                    y = self.work_y + (j * spacing)
                    lat, lon = self._grid_to_latlon(x, y)
                    points.append((lat, lon))

        return points

    def generate_heatmap(
        self,
        max_rings: int = 20,
        save_path: Optional[str] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Generate heat map by expanding outward from work location.

        Args:
            max_rings: Maximum number of rings to analyze
            save_path: Path to save results JSON (optional)
            verbose: Show progress

        Returns:
            Dictionary with:
                - points: List of analyzed points with scores
                - work_location: Work lat/lon
                - grid_spacing_feet: Grid spacing
                - max_score_threshold: Score threshold used
                - rings_analyzed: Number of rings analyzed
                - total_points: Total points analyzed
                - stopped_reason: Why generation stopped
        """
        results = {
            'work_location': {
                'lat': self.work_lat,
                'lon': self.work_lon
            },
            'grid_spacing_feet': self.grid_spacing_feet,
            'max_score_threshold': self.max_score_threshold,
            'points': [],
            'rings_analyzed': 0,
            'total_points': 0,
            'stopped_reason': None,
            'generation_time': datetime.now().isoformat()
        }

        print(f"\nGenerating heat map...")
        print(f"  Work location: {self.work_lat:.6f}, {self.work_lon:.6f}")
        print(f"  Grid spacing: {self.grid_spacing_feet} feet")
        print(f"  Max score threshold: {self.max_score_threshold} minutes")
        print(f"  Max rings: {max_rings}")
        print()

        for ring in range(max_rings + 1):
            ring_points = self.generate_ring_points(ring)

            if verbose:
                print(f"\nRing {ring}: {len(ring_points)} points")

            ring_results = []
            ring_scores = []

            iterator = tqdm(ring_points, desc=f"  Analyzing") if verbose else ring_points

            for lat, lon in iterator:
                # Analyze this point
                analysis = self.analyzer.analyze_location(lat, lon, verbose=False)
                score = self.analyzer.get_score(analysis)

                point_result = {
                    'lat': lat,
                    'lon': lon,
                    'score': score,
                    'ring': ring,
                    'reachable_ratio': analysis['reachable_ratio'],
                    'statistics': {
                        'min': analysis['statistics'].get('min'),
                        'median': analysis['statistics'].get('median'),
                        'max': analysis['statistics'].get('max'),
                        'mean': analysis['statistics'].get('mean')
                    } if analysis['statistics'] else None
                }

                ring_results.append(point_result)
                results['points'].append(point_result)

                if score is not None:
                    ring_scores.append(score)

            results['rings_analyzed'] = ring + 1
            results['total_points'] = len(results['points'])

            # Check stopping condition
            if ring_scores:
                min_score = min(ring_scores)
                max_score = max(ring_scores)
                avg_score = np.mean(ring_scores)

                if verbose:
                    print(f"  Ring scores: min={min_score:.1f}, avg={avg_score:.1f}, max={max_score:.1f}")

                # Stop if all points in ring exceed threshold
                if min_score > self.max_score_threshold:
                    results['stopped_reason'] = f'All points in ring {ring} exceed threshold'
                    if verbose:
                        print(f"\n✓ Stopping: All points in ring exceed {self.max_score_threshold} min threshold")
                    break
            else:
                if verbose:
                    print(f"  Ring scores: No reachable points")

            # Check if we hit max rings
            if ring == max_rings:
                results['stopped_reason'] = f'Reached maximum rings ({max_rings})'
                if verbose:
                    print(f"\n✓ Stopping: Reached maximum rings ({max_rings})")

        # Save results if path provided
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n✓ Saved heat map data to {save_path}")

        return results

    def print_summary(self, results: Dict):
        """
        Print summary of heat map generation.

        Args:
            results: Results dictionary from generate_heatmap()
        """
        print(f"\n{'=' * 70}")
        print("Heat Map Generation Summary")
        print(f"{'=' * 70}")
        print(f"\nWork Location: {results['work_location']['lat']:.6f}, {results['work_location']['lon']:.6f}")
        print(f"Grid Spacing: {results['grid_spacing_feet']} feet")
        print(f"Rings Analyzed: {results['rings_analyzed']}")
        print(f"Total Points: {results['total_points']}")
        print(f"Stopped: {results['stopped_reason']}")

        # Calculate score statistics
        scores = [p['score'] for p in results['points'] if p['score'] is not None]
        if scores:
            print(f"\nScore Distribution (80th percentile travel time):")
            print(f"  Minimum:  {min(scores):.1f} minutes")
            print(f"  25th %:   {np.percentile(scores, 25):.1f} minutes")
            print(f"  Median:   {np.percentile(scores, 50):.1f} minutes")
            print(f"  75th %:   {np.percentile(scores, 75):.1f} minutes")
            print(f"  Maximum:  {max(scores):.1f} minutes")

        reachable_points = sum(1 for p in results['points'] if p['score'] is not None)
        print(f"\nReachability: {reachable_points}/{results['total_points']} points ({reachable_points/results['total_points']*100:.1f}%)")

        print(f"\n{'=' * 70}\n")


def main():
    """Test the grid heat map generator."""
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print("Initializing r5py router...")

    # Initialize router
    osm_path = Path("data/pennsylvania.osm.pbf")
    if not osm_path.exists():
        print(f"Error: OSM data not found at {osm_path}")
        print("Run: python setup_r5py.py")
        return

    router = R5Router(
        gtfs_path=config['gtfs_path'],
        osm_path=str(osm_path),
        max_walk_time=int(config['max_walk_to_stop'] * 60 / config['walking_speed']),
        max_trip_duration=config['max_trip_time'],
        walking_speed=config['walking_speed'] * 1.60934
    )

    # Geocode work address
    geocoder = Geocoder()
    work_coords = geocoder.geocode(config['work_address'], "", "")
    if not work_coords:
        print(f"Error: Could not geocode work address: {config['work_address']}")
        return

    work_lat, work_lon = work_coords
    print(f"Work location: {work_lat:.6f}, {work_lon:.6f}")

    # Initialize analyzer
    analyzer = TimeDistributionAnalyzer(
        router,
        work_lat,
        work_lon,
        time_window_start=config['time_window_start'],
        time_window_end=config['time_window_end'],
        analysis_date=config.get('analysis_date', '2025-11-19')
    )

    # Initialize grid generator
    generator = GridHeatMapGenerator(
        analyzer,
        work_lat,
        work_lon,
        grid_spacing_feet=config['grid_spacing'],
        max_score_threshold=config['max_time_threshold']
    )

    # Generate heat map (start with just 3 rings for testing)
    print("\nStarting heat map generation...")
    print("NOTE: This will take a while! Each point takes ~2-3 minutes.")
    print("Testing with 3 rings first (~25 points = ~1 hour)")

    results = generator.generate_heatmap(
        max_rings=3,
        save_path='heatmap_data.json',
        verbose=True
    )

    generator.print_summary(results)

    print("\nTo generate full heat map, increase max_rings in the code.")
    print("Estimated time: ~2-3 minutes per point")


if __name__ == '__main__':
    main()
