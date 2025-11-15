# Pittsburgh Commute Analysis Tool

A personalized tool to evaluate residential locations in Pittsburgh based on transit accessibility using a custom time-to-work metric.

## Overview

This tool calculates commute times for every minute of the day (6am-7pm) in both directions (to and from work), then uses the 80th percentile as a location quality score. It produces:

1. **Heat Map**: Interactive browser map showing commute scores across Pittsburgh
2. **Address Lookup**: Detailed analysis of transit access for any address

See [project.md](project.md) for full project overview and [requirements.md](requirements.md) for detailed specifications.

## Quick Start

### Prerequisites

- **Python 3.9+**
- **Java Runtime Environment (JRE)** - required for r5py routing engine
- **GTFS Data** - Pittsburgh Regional Transit data (already in `data/GTFS.zip`)

📋 **See [INSTALL.md](INSTALL.md) for detailed installation instructions for all platforms.**

### Installation

```bash
# 1. Install Java (see INSTALL.md for your platform)
java -version  # verify Java is installed

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Download OSM data
python setup_r5py.py

# 4. Create your config file
cp config.example.yaml config.yaml
# Edit config.yaml with your work address
```

### Configuration

Edit `config.yaml`:

```yaml
# Your work location (private - not committed to git)
work_address: "5000 Forbes Ave, Pittsburgh, PA"

# Analysis parameters
max_time_threshold: 60  # minutes - heat map boundary
grid_spacing: 500  # feet between grid points

# Commute constraints
walking_speed: 4.0  # mph
max_walk_to_stop: 1.0  # miles
max_transfers: 1
max_transfer_wait: 30  # minutes
max_trip_time: 60  # minutes

# Time window (every minute from 6am to 7pm)
time_window_start: "06:00"
time_window_end: "19:00"
```

## Usage

### Test Routing

Test the routing engine with a single route:

```bash
python src/r5py_router.py
```

### Generate Heat Map

Coming in Stage 4:

```bash
python src/generate_heatmap.py --config config.yaml
```

This will:
- Start at your work location
- Expand outward in a 500ft grid
- Calculate 80th percentile commute time for each point
- Stop when scores exceed your threshold
- Save results to `heatmap_data.json`

### Web Interface

Coming in Stage 5:

```bash
python src/app.py
```

Then open http://localhost:5000 in your browser.

## Project Structure

```
bustowork/
├── data/
│   ├── GTFS.zip              # Pittsburgh transit data
│   └── pittsburgh.osm        # Street network (auto-downloaded)
├── src/
│   ├── gtfs_loader.py        # GTFS data loading
│   ├── geocoder.py           # Address geocoding
│   ├── street_network.py    # Walking distances
│   ├── r5py_router.py        # Fast routing with r5py
│   ├── analyzer.py           # Coming: Time distribution analysis
│   ├── grid_generator.py    # Coming: Grid-based heat map
│   └── app.py                # Coming: Web interface
├── config.yaml               # Your settings (gitignored)
├── config.example.yaml       # Example configuration
├── requirements.txt          # Python dependencies
├── setup_r5py.py            # Setup script
└── README.md                # This file
```

## Development Stages

- [x] **Stage 1**: GTFS Foundation - Load transit data, find nearby stops
- [x] **Stage 2**: Routing Engine - Calculate single trip times
- [ ] **Stage 3**: Time Distribution - Calculate 1,560-sample distribution per location
- [ ] **Stage 4**: Grid Heat Map - Expand outward from work, compute scores
- [ ] **Stage 5**: Web Visualization - Interactive map interface
- [ ] **Stage 6**: Address Lookup - LLM-powered transit descriptions

## How It Works

### The Custom Metric

For each location:
1. Calculate travel time for **every minute** from 6am to 7pm (780 minutes)
2. Calculate both **to work** and **from work** (1,560 total samples)
3. At each minute, find the **fastest route** (walking, direct bus, or one transfer)
4. **80th percentile** of all times = location score

This captures:
- Bus frequency (buses every 10 min vs 30 min)
- Coverage throughout the day
- Worst-case scenarios (not just optimal times)

### Grid Expansion Strategy

Instead of analyzing the entire city:
1. Start at work location
2. Create 500ft grid around it
3. Calculate scores for grid points
4. Expand outward
5. **Stop when scores exceed threshold** (e.g., 60 minutes)

This naturally limits computation to relevant areas.

## Technical Details

### Routing Engine: r5py

Uses [r5py](https://r5py.readthedocs.io/) - a Python wrapper for R5 (Rapid Realistic Routing):
- Fast GTFS-based routing
- Handles walking + multiple transit modes
- Efficiently computes travel time matrices
- Much faster than custom routing algorithms

### Data Sources

- **Transit**: Pittsburgh Regional Transit GTFS (buses + T light rail)
- **Streets**: OpenStreetMap via osmnx
- **Geocoding**: Nominatim (OpenStreetMap)

### Performance

With r5py:
- Single route: **<1 second** (vs 30+ seconds with custom router)
- 1,560 samples per location: **~10-20 minutes**
- 400 grid points: **~60-120 hours** on local machine

The expanding grid strategy significantly reduces this by only analyzing reachable areas.

## Privacy

Your work address is stored in `config.yaml` which is **gitignored**. Only the example config is committed to the repository.

## Requirements

See [requirements.md](requirements.md) for full specification.

## License

Private project - not for distribution.

## Troubleshooting

For detailed troubleshooting including platform-specific issues, see [INSTALL.md](INSTALL.md).

Common issues:

- **"Java not found"** - Install Java JRE (see INSTALL.md)
- **"OSM data not found"** - Run `python setup_r5py.py`
- **"No route found"** - Check work address is in Pittsburgh, verify GTFS data exists
- **Routing is slow** - First run builds network (takes time), subsequent runs are faster

## Contact

This is a personal tool. See project documentation for details.
