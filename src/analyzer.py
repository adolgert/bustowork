"""
Time distribution analyzer.

Calculates the distribution of travel times for a location by
sampling every minute throughout the day.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, Optional
from pathlib import Path
import yaml
from tqdm import tqdm

from r5py_router import R5Router
from geocoder import Geocoder


class TimeDistributionAnalyzer:
    """Analyze travel time distribution for a location."""

    def __init__(
        self,
        router: R5Router,
        work_lat: float,
        work_lon: float,
        time_window_start: str = "06:00",
        time_window_end: str = "19:00",
        analysis_date: str = "2025-01-15"  # Weekday
    ):
        """
        Initialize analyzer.

        Args:
            router: R5 router instance
            work_lat: Work location latitude
            work_lon: Work location longitude
            time_window_start: Start time (HH:MM)
            time_window_end: End time (HH:MM)
            analysis_date: Date for analysis (YYYY-MM-DD)
        """
        self.router = router
        self.work_lat = work_lat
        self.work_lon = work_lon

        # Parse time window
        start_parts = time_window_start.split(':')
        self.start_hour = int(start_parts[0])
        self.start_minute = int(start_parts[1])

        end_parts = time_window_end.split(':')
        self.end_hour = int(end_parts[0])
        self.end_minute = int(end_parts[1])

        # Parse date
        date_parts = analysis_date.split('-')
        self.analysis_date = datetime(
            int(date_parts[0]),
            int(date_parts[1]),
            int(date_parts[2])
        )

    def analyze_location(
        self,
        home_lat: float,
        home_lon: float,
        verbose: bool = True
    ) -> Dict:
        """
        Analyze travel time distribution for a home location.

        Calculates travel time for every minute from start to end time,
        in both directions (home→work and work→home).

        Args:
            home_lat: Home location latitude
            home_lon: Home location longitude
            verbose: Show progress bar

        Returns:
            Dictionary with:
                - times: List of all travel times (minutes)
                - to_work_times: Travel times home→work
                - from_work_times: Travel times work→home
                - percentiles: Dict of percentile values
                - statistics: Mean, median, min, max, std
                - unreachable_count: Number of times no route found
        """
        to_work_times = []
        from_work_times = []
        unreachable_count = 0

        # Generate all minute timestamps
        start_time = self.analysis_date.replace(
            hour=self.start_hour,
            minute=self.start_minute
        )
        end_time = self.analysis_date.replace(
            hour=self.end_hour,
            minute=self.end_minute
        )

        current_time = start_time
        timestamps = []
        while current_time <= end_time:
            timestamps.append(current_time)
            current_time += timedelta(minutes=1)

        total_samples = len(timestamps)
        iterator = tqdm(timestamps, desc="Analyzing") if verbose else timestamps

        for departure_time in iterator:
            # Home → Work
            to_work_time = self.router.calculate_route_at_time(
                home_lat, home_lon,
                self.work_lat, self.work_lon,
                departure_time
            )

            if to_work_time is not None:
                to_work_times.append(to_work_time)
            else:
                unreachable_count += 1

            # Work → Home
            from_work_time = self.router.calculate_route_at_time(
                self.work_lat, self.work_lon,
                home_lat, home_lon,
                departure_time
            )

            if from_work_time is not None:
                from_work_times.append(from_work_time)
            else:
                unreachable_count += 1

        # Combine all times
        all_times = to_work_times + from_work_times

        if not all_times:
            return {
                'times': [],
                'to_work_times': [],
                'from_work_times': [],
                'percentiles': {},
                'statistics': {},
                'unreachable_count': unreachable_count,
                'total_samples': total_samples * 2,
                'reachable_ratio': 0.0
            }

        # Calculate percentiles
        percentiles = {
            '10th': np.percentile(all_times, 10),
            '25th': np.percentile(all_times, 25),
            '50th': np.percentile(all_times, 50),
            '75th': np.percentile(all_times, 75),
            '80th': np.percentile(all_times, 80),
            '90th': np.percentile(all_times, 90),
            '95th': np.percentile(all_times, 95)
        }

        # Calculate statistics
        statistics = {
            'mean': np.mean(all_times),
            'median': np.median(all_times),
            'min': np.min(all_times),
            'max': np.max(all_times),
            'std': np.std(all_times)
        }

        return {
            'times': all_times,
            'to_work_times': to_work_times,
            'from_work_times': from_work_times,
            'percentiles': percentiles,
            'statistics': statistics,
            'unreachable_count': unreachable_count,
            'total_samples': total_samples * 2,
            'reachable_ratio': len(all_times) / (total_samples * 2)
        }

    def get_score(self, analysis_result: Dict) -> Optional[float]:
        """
        Get the location score (80th percentile).

        Args:
            analysis_result: Result from analyze_location()

        Returns:
            80th percentile travel time in minutes, or None if no data
        """
        if not analysis_result['times']:
            return None

        return analysis_result['percentiles']['80th']

    def print_summary(self, analysis_result: Dict, location_name: str = "Location"):
        """
        Print analysis summary.

        Args:
            analysis_result: Result from analyze_location()
            location_name: Name of location for display
        """
        print(f"\n{'=' * 70}")
        print(f"Travel Time Analysis: {location_name}")
        print(f"{'=' * 70}")

        if not analysis_result['times']:
            print("No routes found!")
            return

        print(f"\nTotal samples: {analysis_result['total_samples']}")
        print(f"Reachable: {len(analysis_result['times'])} ({analysis_result['reachable_ratio']*100:.1f}%)")
        print(f"Unreachable: {analysis_result['unreachable_count']}")

        print(f"\nTravel Time Distribution (minutes):")
        print(f"  Minimum:     {analysis_result['statistics']['min']:.1f}")
        print(f"  10th %ile:   {analysis_result['percentiles']['10th']:.1f}")
        print(f"  25th %ile:   {analysis_result['percentiles']['25th']:.1f}")
        print(f"  Median:      {analysis_result['percentiles']['50th']:.1f}")
        print(f"  75th %ile:   {analysis_result['percentiles']['75th']:.1f}")
        print(f"  80th %ile:   {analysis_result['percentiles']['80th']:.1f}  ← SCORE")
        print(f"  90th %ile:   {analysis_result['percentiles']['90th']:.1f}")
        print(f"  95th %ile:   {analysis_result['percentiles']['95th']:.1f}")
        print(f"  Maximum:     {analysis_result['statistics']['max']:.1f}")
        print(f"  Mean:        {analysis_result['statistics']['mean']:.1f}")
        print(f"  Std Dev:     {analysis_result['statistics']['std']:.1f}")

        print(f"\nDirection Breakdown:")
        if analysis_result['to_work_times']:
            print(f"  To work:     {len(analysis_result['to_work_times'])} samples, "
                  f"median {np.median(analysis_result['to_work_times']):.1f} min")
        if analysis_result['from_work_times']:
            print(f"  From work:   {len(analysis_result['from_work_times'])} samples, "
                  f"median {np.median(analysis_result['from_work_times']):.1f} min")

        print(f"\n{'=' * 70}\n")


def main():
    """Test the time distribution analyzer."""
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
        time_window_end=config['time_window_end']
    )

    # Test with a location in Shadyside (about 1 mile from CMU)
    print("\nTesting with Shadyside location...")
    test_lat, test_lon = 40.4520, -79.9280

    result = analyzer.analyze_location(test_lat, test_lon)

    analyzer.print_summary(result, "Shadyside Test Location")

    score = analyzer.get_score(result)
    if score:
        print(f"Location Score (80th percentile): {score:.1f} minutes")


if __name__ == '__main__':
    main()
