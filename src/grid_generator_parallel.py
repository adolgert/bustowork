"""
Parallel grid heat map generator.

Uses multiprocessing to analyze multiple grid points simultaneously.
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
from multiprocessing import Pool, cpu_count, get_context
import os

from r5py_router import R5Router
from analyzer import TimeDistributionAnalyzer


# Global variables for worker processes
_WORKER_ROUTER = None
_WORKER_CONFIG = None


def _init_worker(config_dict):
    """
    Initialize worker process with r5py router.

    This is called once per worker process at startup.
    Building the transport network takes ~1 minute and ~2GB RAM.
    """
    global _WORKER_ROUTER, _WORKER_CONFIG
    _WORKER_CONFIG = config_dict

    print(f"Worker {os.getpid()}: Initializing r5py transport network...")

    # Build router once per worker (expensive!)
    _WORKER_ROUTER = R5Router(
        gtfs_path=config_dict['gtfs_path'],
        osm_path=config_dict['osm_path'],
        max_walk_time=config_dict['max_walk_time'],
        max_trip_duration=config_dict['max_trip_duration'],
        walking_speed=config_dict['walking_speed']
    )

    print(f"Worker {os.getpid()}: Ready!")


def _analyze_point_worker(point_data):
    """
    Worker function to analyze a single grid point.

    Reuses the r5py router that was initialized once per worker.
    """
    lat, lon, ring = point_data
    config = _WORKER_CONFIG

    # Reuse the router that was built in _init_worker
    router = _WORKER_ROUTER

    # Initialize analyzer (lightweight - just wraps the router)
    analyzer = TimeDistributionAnalyzer(
        router,
        config['work_lat'],
        config['work_lon'],
        time_window_start=config['time_window_start'],
        time_window_end=config['time_window_end'],
        analysis_date=config['analysis_date']
    )

    # Analyze this point
    analysis = analyzer.analyze_location(lat, lon, verbose=False)
    score = analyzer.get_score(analysis)

    return {
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


class ParallelGridHeatMapGenerator:
    """Generate heat map using multiprocessing for speed."""

    def __init__(
        self,
        work_lat: float,
        work_lon: float,
        config: Dict,
        grid_spacing_feet: int = 500,
        max_score_threshold: int = 60,
        num_workers: Optional[int] = None
    ):
        """
        Initialize parallel grid heat map generator.

        Args:
            work_lat: Work location latitude
            work_lon: Work location longitude
            config: Configuration dictionary
            grid_spacing_feet: Distance between grid points in feet
            max_score_threshold: Stop expanding when all points exceed this score
            num_workers: Number of parallel workers (default: cpu_count())
        """
        self.work_lat = work_lat
        self.work_lon = work_lon
        self.config = config
        self.grid_spacing_feet = grid_spacing_feet
        self.max_score_threshold = max_score_threshold
        self.num_workers = num_workers or cpu_count()

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

        # Generate points along the ring
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
        Generate heat map by expanding outward from work location using multiprocessing.

        Args:
            max_rings: Maximum number of rings to analyze
            save_path: Path to save results JSON (optional)
            verbose: Show progress

        Returns:
            Dictionary with heat map data
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
            'generation_time': datetime.now().isoformat(),
            'num_workers': self.num_workers
        }

        print(f"\nGenerating heat map with {self.num_workers} parallel workers...")
        print(f"  Work location: {self.work_lat:.6f}, {self.work_lon:.6f}")
        print(f"  Grid spacing: {self.grid_spacing_feet} feet")
        print(f"  Max score threshold: {self.max_score_threshold} minutes")
        print(f"  Max rings: {max_rings}")
        print()

        # Prepare config for workers
        worker_config = {
            'gtfs_path': self.config['gtfs_path'],
            'osm_path': self.config['osm_path'],
            'max_walk_time': self.config['max_walk_time'],
            'max_trip_duration': self.config['max_trip_duration'],
            'walking_speed': self.config['walking_speed'],
            'work_lat': self.work_lat,
            'work_lon': self.work_lon,
            'time_window_start': self.config['time_window_start'],
            'time_window_end': self.config['time_window_end'],
            'analysis_date': self.config['analysis_date']
        }

        # Create process pool using 'spawn' method (not 'fork')
        # This is required for r5py/JPype to work in multiprocessing
        # 'spawn' starts fresh Python process, avoiding Java VM fork issues
        ctx = get_context('spawn')
        with ctx.Pool(processes=self.num_workers, initializer=_init_worker, initargs=(worker_config,)) as pool:
            for ring in range(max_rings + 1):
                ring_points = self.generate_ring_points(ring)

                if verbose:
                    print(f"\nRing {ring}: {len(ring_points)} points (analyzing in parallel with {self.num_workers} workers)")

                # Prepare point data for workers
                point_data = [(lat, lon, ring) for lat, lon in ring_points]

                # Analyze points in parallel
                if verbose:
                    # Use imap_unordered with tqdm for progress
                    ring_results = list(tqdm(
                        pool.imap_unordered(_analyze_point_worker, point_data),
                        total=len(point_data),
                        desc=f"  Analyzing"
                    ))
                else:
                    ring_results = pool.map(_analyze_point_worker, point_data)

                # Add results
                results['points'].extend(ring_results)
                results['rings_analyzed'] = ring + 1
                results['total_points'] = len(results['points'])

                # Check stopping condition
                ring_scores = [r['score'] for r in ring_results if r['score'] is not None]

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
        """Print summary of heat map generation."""
        print(f"\n{'=' * 70}")
        print("Heat Map Generation Summary")
        print(f"{'=' * 70}")
        print(f"\nWork Location: {results['work_location']['lat']:.6f}, {results['work_location']['lon']:.6f}")
        print(f"Grid Spacing: {results['grid_spacing_feet']} feet")
        print(f"Parallel Workers: {results['num_workers']}")
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
    """Test the parallel grid heat map generator."""
    from geocoder import Geocoder

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print("Initializing parallel heat map generator...")

    # Check for OSM data
    osm_path = Path("data/pennsylvania.osm.pbf")
    if not osm_path.exists():
        print(f"Error: OSM data not found at {osm_path}")
        print("Run: python setup_r5py.py")
        return

    # Geocode work address
    geocoder = Geocoder()
    work_coords = geocoder.geocode(config['work_address'], "", "")
    if not work_coords:
        print(f"Error: Could not geocode work address: {config['work_address']}")
        return

    work_lat, work_lon = work_coords
    print(f"Work location: {work_lat:.6f}, {work_lon:.6f}")

    # Prepare config for generator
    generator_config = {
        'gtfs_path': config['gtfs_path'],
        'osm_path': str(osm_path),
        'max_walk_time': int(config['max_walk_to_stop'] * 60 / config['walking_speed']),
        'max_trip_duration': config['max_trip_time'],
        'walking_speed': config['walking_speed'] * 1.60934,
        'time_window_start': config['time_window_start'],
        'time_window_end': config['time_window_end'],
        'analysis_date': config.get('analysis_date', '2025-11-19')
    }

    # Determine number of workers
    num_cpus = cpu_count()
    # Use 75% of CPUs or 16, whichever is smaller
    num_workers = min(int(num_cpus * 0.75), 16)

    print(f"System has {num_cpus} CPUs, using {num_workers} workers")
    print(f"Estimated memory usage: ~{num_workers * 2}GB")

    # Initialize generator
    generator = ParallelGridHeatMapGenerator(
        work_lat,
        work_lon,
        generator_config,
        grid_spacing_feet=config['grid_spacing'],
        max_score_threshold=config['max_time_threshold'],
        num_workers=num_workers
    )

    # Generate heat map
    print("\nStarting heat map generation...")
    print("NOTE: First workers will build r5py network (takes ~1 min each)")
    print("Then analysis proceeds in parallel - much faster!")
    print("\nTesting with 3 rings first...")

    results = generator.generate_heatmap(
        max_rings=3,
        save_path='heatmap_data.json',
        verbose=True
    )

    generator.print_summary(results)

    print("\nSpeedup estimate:")
    print(f"  Sequential: ~{len(results['points']) * 2.5:.0f} minutes")
    print(f"  Parallel ({num_workers} workers): ~{len(results['points']) * 2.5 / num_workers:.0f} minutes")
    print(f"  Speedup: ~{num_workers:.1f}x faster")


if __name__ == '__main__':
    main()
