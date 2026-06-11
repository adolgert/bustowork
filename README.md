# Pittsburgh Commute Analysis Tool

Answers one question: from any spot in Pittsburgh, how long does it really
take to get to work by walking and/or transit - *including the time spent
waiting for the bus*?

The model: you walk out the door at a uniformly random minute (6am-7pm by
default) and take whatever gets you there soonest - walking, a bus, or a
walk-to-stop-plus-bus combination. Sampling every departure minute gives a
distribution of door-to-door times; a location's **score is the 80th
percentile** of that distribution. A location with one bus an hour scores
badly even though Google says it "has service." A location near several
frequent lines scores well.

It produces:

1. **Heat map** - interactive browser map of scores across the city
2. **CLI query** - score for a single address or lat/lon, for house hunting

## How it works (and why it's fast)

Routing uses [r5py](https://r5py.readthedocs.io/) / Conveyal R5. R5's
range-RAPTOR computes travel-time percentiles over an entire departure
window in a single request per origin - one JVM call replaces a
call-per-minute loop. Origins are also fanned out across a thread pool
(R5's network is read-only and thread-safe). Net effect: ~44 ms per grid
point instead of ~2.5 minutes; a full 8-mile-radius map takes minutes, not
days.

## Setup

```bash
# 1. Java 21+ (required by r5py)
java -version

# 2. Python dependencies
python -m venv venv && venv/bin/pip install -r requirements.txt

# 3. Data: a PRT GTFS feed and an OSM extract
#    GTFS: https://www.rideprt.org/developerresources/GTFS.zip -> data/GTFS.zip
#    (strip header-only .txt tables from the zip if R5 complains)
#    OSM: put pennsylvania.osm.pbf (e.g. from Geofabrik) in data/, then:
venv/bin/python src/crop_osm.py   # -> data/pittsburgh.osm.pbf (~45 MB)

# 4. Configure
cp config.example.yaml config.yaml   # set work_address
```

The GTFS feed expires every few months (see `feed_info.txt` inside the
zip). `analysis_date: auto` picks a valid Wednesday automatically and
warns when the feed is stale.

## Usage

### Query one location

```bash
venv/bin/python src/query.py "5500 Walnut St, Pittsburgh, PA"
venv/bin/python src/query.py --latlon 40.4520 -79.9280
venv/bin/python src/query.py "312 S Highland Ave" --both --json
```

Example output:

```
Leaving at a random minute 06:00-19:00 on 2026-06-17, walk or transit:

  10% of departures arrive within  13.0 min
  25% of departures arrive within  15.0 min
  50% of departures arrive within  18.0 min
  80% of departures arrive within  20.0 min  <- score
  95% of departures arrive within  20.0 min

  Walking only:  20.0 min   (cap: 90 min)
```

Other flags: `--both` (return-trip percentiles), `--json` (machine-readable),
`--date YYYY-MM-DD` (simulate a specific service day), `--config PATH`.

First run builds the transport network (~30 s); r5py caches it afterwards.

### Generate the heat map

```bash
venv/bin/python src/generate_heatmap.py                    # full map
venv/bin/python src/generate_heatmap.py --radius-miles 3   # quick test
```

Writes `heatmap_data.json`.

### View the heat map

```bash
venv/bin/python src/app.py    # then open http://localhost:5000
```

## Project structure

| File | Purpose |
|------|---------|
| `src/commute.py` | Core scorer: R5 departure-window percentiles, threaded fan-out |
| `src/query.py` | CLI score for one address / lat-lon |
| `src/generate_heatmap.py` | Grid scoring -> `heatmap_data.json` |
| `src/app.py` + `templates/index.html` | Flask + Plotly heat map viewer |
| `src/crop_osm.py` | Crop a state-sized PBF to the Pittsburgh area |
| `src/geocoder.py` | Nominatim geocoding wrapper |
| `src/router.py`, `src/gtfs_loader.py`, ... | Earlier hand-rolled router (superseded by r5py, kept as standalone tools) |

The old per-minute pipeline (`analyzer.py`, `grid_generator*.py`,
`r5py_router.py`) was removed; see git history if you need it.

## Moving to another machine

```bash
./package.sh            # writes bustowork-transfer.tar.gz (~100 MB)
```

The tarball contains the code (with git history), `config.yaml`, the GTFS
feed, the cropped OSM extract, and the generated heat map - so nothing
needs recomputing. On the target machine you only install Java 21+ and the
Python dependencies (instructions are printed by the script). Deliberately
excluded: `venv/` (platform-specific, rebuild it), the 323 MB
`pennsylvania.osm.pbf` (only needed to re-crop), and r5py's network cache
in `~/.cache/r5py` (rebuilds automatically in ~30 s on first query).

## Notes

- The score counts a departure minute as unreachable when the trip exceeds
  `max_trip_time` (default 90 min); if more than 20% of minutes are
  unreachable the 80th-percentile score is null and the point shows as
  missing on the map.
- Keep `config.yaml` out of the repository if you consider your work
  address private; only `config.example.yaml` is meant to be committed.

## License

Private project - not for distribution.
