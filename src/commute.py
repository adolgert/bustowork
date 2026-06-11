"""
Core commute scoring.

The metric: you walk out the door at a uniformly random minute in the
departure window (default 6:00-19:00) and travel to work by walking,
transit, or a combination - whichever arrives soonest. The travel time
includes waiting at the stop. The location's score is a percentile
(default 80th) of that distribution of door-to-door times.

R5 computes this natively: a single request per origin runs a range-RAPTOR
search over every departure minute in the window and returns travel-time
percentiles, so one JVM call replaces the old one-call-per-minute loop
(781 calls per point). Origins are additionally fanned out across a thread
pool - R5's TransportNetwork is read-only and thread-safe, and JPype
releases the GIL while Java code runs.
"""

import csv
import io
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

# Percentiles requested from R5 (it allows at most 5 per request).
PERCENTILES = [10, 25, 50, 80, 95]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str = None) -> dict:
    """Load config.yaml and fill in defaults."""
    path = Path(config_path) if config_path else PROJECT_ROOT / 'config.yaml'
    with open(path) as f:
        config = yaml.safe_load(f)

    config.setdefault('gtfs_path', 'data/GTFS.zip')
    config.setdefault('osm_path', 'data/pittsburgh.osm.pbf')
    config.setdefault('walking_speed', 3.0)        # mph
    config.setdefault('max_trip_time', 90)         # minutes
    config.setdefault('max_transfers', 1)
    config.setdefault('time_window_start', '06:00')
    config.setdefault('time_window_end', '19:00')
    config.setdefault('analysis_date', 'auto')
    config.setdefault('score_percentile', 80)
    config.setdefault('grid_spacing', 500)         # feet
    config.setdefault('heatmap_radius_miles', 8.0)
    return config


def _parse_hhmm(text: str):
    hour, minute = text.split(':')
    return int(hour), int(minute)


def pick_analysis_date(gtfs_path: Path, requested: str = 'auto') -> date:
    """
    Choose a weekday to simulate.

    Reads calendar.txt from the GTFS feed to find its validity window. With
    'auto', picks the next Wednesday that falls inside the window (or the
    last one in the window if the feed has expired). An explicit date is
    validated against the window and warned about if outside.
    """
    with zipfile.ZipFile(gtfs_path) as zf:
        with zf.open('calendar.txt') as f:
            rows = list(csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')))
        removed_dates = set()
        try:
            with zf.open('calendar_dates.txt') as f:
                for row in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
                    if row['exception_type'].strip() == '2':
                        removed_dates.add(row['date'].strip())
        except KeyError:
            pass

    weekday_rows = [r for r in rows if r['wednesday'].strip() == '1']
    if not weekday_rows:
        weekday_rows = rows
    start = min(datetime.strptime(r['start_date'].strip(), '%Y%m%d').date()
                for r in weekday_rows)
    end = max(datetime.strptime(r['end_date'].strip(), '%Y%m%d').date()
              for r in weekday_rows)

    if requested and requested != 'auto':
        chosen = datetime.strptime(requested, '%Y-%m-%d').date()
        if not (start <= chosen <= end):
            print(f"WARNING: requested date {chosen} is outside the GTFS "
                  f"feed's validity window ({start} to {end}); transit "
                  f"routing will find no service.", file=sys.stderr)
        return chosen

    def next_wednesday(d: date) -> date:
        return d + timedelta(days=(2 - d.weekday()) % 7)

    today = date.today()
    chosen = next_wednesday(max(today, start))
    if chosen > end:
        # Feed expired: fall back to the last Wednesday it covers.
        chosen = end - timedelta(days=(end.weekday() - 2) % 7)
        print(f"WARNING: GTFS feed expired {end}; simulating {chosen}. "
              f"Download a current feed for accurate results.", file=sys.stderr)
    # Avoid days where calendar_dates.txt removes service (e.g. holidays).
    attempts = 0
    while chosen.strftime('%Y%m%d') in removed_dates and attempts < 8:
        candidate = chosen + timedelta(days=7)
        if candidate > end:
            break
        chosen = candidate
        attempts += 1
    return chosen


class CommuteScorer:
    """Scores locations by percentile door-to-door travel time to work."""

    def __init__(self, config: dict, verbose: bool = True):
        # Import here so --help and config errors don't pay JVM startup.
        import r5py
        self._r5py = r5py

        self.config = config
        self.verbose = verbose

        gtfs_path = PROJECT_ROOT / config['gtfs_path']
        osm_path = PROJECT_ROOT / config['osm_path']
        if not osm_path.exists():
            raise FileNotFoundError(
                f"OSM extract not found at {osm_path}. "
                f"Run: python src/crop_osm.py")

        self.analysis_date = pick_analysis_date(
            gtfs_path, config.get('analysis_date', 'auto'))

        start_h, start_m = _parse_hhmm(config['time_window_start'])
        end_h, end_m = _parse_hhmm(config['time_window_end'])
        self.departure = datetime(
            self.analysis_date.year, self.analysis_date.month,
            self.analysis_date.day, start_h, start_m)
        self.window = (datetime(2000, 1, 1, end_h, end_m)
                       - datetime(2000, 1, 1, start_h, start_m))

        self.walking_speed_kmh = config['walking_speed'] * 1.60934
        self.max_trip = timedelta(minutes=config['max_trip_time'])
        self.max_rides = config['max_transfers'] + 1
        self.score_percentile = config['score_percentile']
        if self.score_percentile not in PERCENTILES:
            raise ValueError(
                f"score_percentile must be one of {PERCENTILES}")

        self.work_lat, self.work_lon = self._resolve_work_location()
        self.work_gdf = gpd.GeoDataFrame(
            {'id': ['work']},
            geometry=gpd.points_from_xy([self.work_lon], [self.work_lat]),
            crs='EPSG:4326')

        if verbose:
            print(f"Building transport network (cached after first run)...")
            print(f"  OSM:  {osm_path.name}")
            print(f"  GTFS: {gtfs_path.name}")
            print(f"  Simulated day: {self.analysis_date} "
                  f"({self.analysis_date.strftime('%A')})")
            print(f"  Departure window: {config['time_window_start']}-"
                  f"{config['time_window_end']}")
        self.network = r5py.TransportNetwork(str(osm_path), [str(gtfs_path)])
        if verbose:
            print(f"  Network ready.")

    def _resolve_work_location(self):
        config = self.config
        if 'work_lat' in config and 'work_lon' in config:
            return float(config['work_lat']), float(config['work_lon'])
        from geocoder import Geocoder
        coords = Geocoder().geocode(config['work_address'], "", "")
        if not coords:
            raise RuntimeError(
                f"Could not geocode work address {config['work_address']!r}. "
                f"Add work_lat/work_lon to config.yaml to skip geocoding.")
        if self.verbose:
            print(f"Work: {config['work_address']} -> "
                  f"{coords[0]:.6f}, {coords[1]:.6f}")
        return coords

    def _matrix(self, origins: gpd.GeoDataFrame,
                destinations: gpd.GeoDataFrame,
                transit: bool = True) -> pd.DataFrame:
        r5py = self._r5py
        modes = ([r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK]
                 if transit else [r5py.TransportMode.WALK])
        return r5py.TravelTimeMatrix(
            self.network,
            origins=origins,
            destinations=destinations,
            departure=self.departure,
            departure_time_window=self.window,
            percentiles=PERCENTILES,
            transport_modes=modes,
            speed_walking=self.walking_speed_kmh,
            max_time=self.max_trip,
            max_public_transport_rides=self.max_rides,
        )

    def score_points(self, points: gpd.GeoDataFrame,
                     n_threads: int = None) -> pd.DataFrame:
        """
        Percentile travel times point -> work for many points at once.

        Args:
            points: GeoDataFrame with 'id' column, EPSG:4326 point geometry.
            n_threads: parallel R5 requests (default: cpu_count - 2, max 16)

        Returns:
            DataFrame indexed like points with travel_time_p10..p95 columns
            (minutes; NaN where that percentile exceeds max_trip_time).
        """
        import os
        if n_threads is None:
            n_threads = max(1, min((os.cpu_count() or 4) - 2, 16))
        n_chunks = max(1, min(len(points), n_threads * 4))
        bounds = np.array_split(np.arange(len(points)), n_chunks)
        chunks = [points.iloc[idx] for idx in bounds]

        if self.verbose:
            print(f"Routing {len(points)} origins -> work across "
                  f"{n_threads} threads ({n_chunks} chunks)...")

        results = []
        done = 0
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(self._matrix, chunk, self.work_gdf)
                       for chunk in chunks if len(chunk)]
            for future in as_completed(futures):
                results.append(future.result())
                done += 1
                if self.verbose and done % max(1, len(futures) // 10) == 0:
                    print(f"  {done}/{len(futures)} chunks done")

        matrix = pd.concat(results, ignore_index=True)
        return matrix.rename(columns={'from_id': 'id'}).drop(columns='to_id')

    def score_from_work(self, points: gpd.GeoDataFrame) -> pd.DataFrame:
        """Percentile travel times work -> points (single one-to-many call)."""
        matrix = self._matrix(self.work_gdf, points)
        return matrix.rename(columns={'to_id': 'id'}).drop(columns='from_id')

    def walk_time(self, lat: float, lon: float) -> float:
        """Walk-only travel time to work in minutes (NaN if over the cap)."""
        origin = gpd.GeoDataFrame(
            {'id': ['origin']},
            geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        matrix = self._matrix(origin, self.work_gdf, transit=False)
        # Walk time is departure-independent; the median is the value.
        return float(matrix['travel_time_p50'].iloc[0])

    def analyze_point(self, lat: float, lon: float,
                      include_from_work: bool = False) -> dict:
        """Full percentile breakdown for a single location."""
        origin = gpd.GeoDataFrame(
            {'id': ['origin']},
            geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        to_work = self._matrix(origin, self.work_gdf)
        result = {
            'lat': lat,
            'lon': lon,
            'analysis_date': str(self.analysis_date),
            'window': (f"{self.config['time_window_start']}-"
                       f"{self.config['time_window_end']}"),
            'to_work': {f'p{p}': _nan_to_none(to_work[f'travel_time_p{p}'].iloc[0])
                        for p in PERCENTILES},
            'walk_only': _nan_to_none(self.walk_time(lat, lon)),
        }
        result['score'] = result['to_work'][f'p{self.score_percentile}']
        if include_from_work:
            from_work = self._matrix(self.work_gdf, origin)
            result['from_work'] = {
                f'p{p}': _nan_to_none(from_work[f'travel_time_p{p}'].iloc[0])
                for p in PERCENTILES}
        return result


def _nan_to_none(value):
    value = float(value)
    return None if np.isnan(value) else value


def reachable_lower_bound(row) -> float:
    """
    Lower bound on the fraction of departure minutes with a route within
    max_trip_time: if the p-th percentile is finite, at least p% of
    departures make it.
    """
    bound = 0.0
    for p in PERCENTILES:
        if not np.isnan(row[f'travel_time_p{p}']):
            bound = p / 100.0
    return bound
