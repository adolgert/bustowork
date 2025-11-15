# Pittsburgh Commute Analysis Tool - Requirements

## Overview
A personalized commute analysis tool for evaluating residential locations in Pittsburgh based on transit accessibility to a work location using a custom time-to-work metric.

## Core Concept
Calculate commute times for every minute of the day (6am-7pm) in both directions (to work and from work), then use the 80th percentile of this combined distribution as a location quality score.

## Data Sources
- **Pittsburgh GTFS Data**: Port Authority of Allegheny County static GTFS data
  - Includes bus routes and T light rail
  - Download to `data/` directory (OK to check in)
  - Analyze weekday schedules only

## Commute Time Calculation

### Time Windows
- Calculate travel times for every minute from 6:00 AM to 7:00 PM (13 hours = 780 minutes)
- For each minute, calculate:
  - Time to travel FROM home TO work starting at that minute
  - Time to travel FROM work TO home starting at that minute
- Combined vector: 1,560 time samples per location

### Routing Constraints
- **Walking speed**: 4 mph
- **Maximum walk to bus stop**: 1 mile
- **Maximum transfers**: 1 transfer allowed
- **Maximum transfer wait time**: 30 minutes
- **Maximum total trip time**: 1 hour
- **Wait time**: Include time waiting for bus to arrive (this is critical to the analysis)

### Routing Logic
At each minute, determine the fastest way to reach destination by:
1. Evaluating walking-only option
2. Evaluating all bus routes within 1 mile walking distance
3. Evaluating routes with 1 transfer (respecting 30min max wait)
4. Selecting the option that arrives soonest

### Location Score
- **Metric**: 80th percentile of the combined to/from time distribution
- Represents the "slower times" for evaluating true accessibility

## Geographic Analysis

### Grid Generation
- **Starting point**: Work location (from config)
- **Grid spacing**: 500 feet
- **Expansion strategy**: Start at work location and expand outward
- **Stop condition**: Stop expanding when grid points exceed configured max time threshold (e.g., 1 hour at 80th percentile)
- **Coverage area**: Pittsburgh Regional Transit service area (buses + T)

## Outputs

### 1. Interactive Heat Map (Browser)
- **Visualization**: Heat map overlay on street map
- **Color scheme**: Yellow (fast/close) to Blue (slow/far)
- **Data**: Show 80th percentile commute time for each grid point
- **Technology**: Web-based interactive map

### 2. Address Lookup Tool
For a given address, display:
- **Distribution graph**: Histogram/plot of all 1,560 travel times
- **Summary statistics**: Show 80th percentile, median, min, max
- **Bus service description**: LLM-generated summary (using Haiku model) of:
  - Nearby bus stops and routes
  - Frequency of service
  - Peak vs off-peak timing
  - Other relevant schedule information

## Configuration

### Config File Format
- **Format**: YAML
- **Location**: `config.yaml` (gitignored for privacy)

### Required Settings
```yaml
work_address: "123 Main St, Pittsburgh, PA 15213"  # Private, not committed
max_time_threshold: 60  # minutes - for heat map boundary
grid_spacing: 500  # feet
```

### Optional Settings
```yaml
walking_speed: 4.0  # mph
max_walk_to_stop: 1.0  # miles
max_transfers: 1
max_transfer_wait: 30  # minutes
max_trip_time: 60  # minutes
time_window_start: "06:00"
time_window_end: "19:00"
analysis_days: ["weekday"]  # vs weekend
```

## Technical Stack

### Backend
- **Language**: Python
- **Web Framework**: Flask
- **GTFS Processing**: Standard GTFS libraries
- **Routing**: Custom routing engine implementing the time calculation logic
- **LLM Integration**: Anthropic API (Haiku) for bus service descriptions

### Frontend
- **Map Visualization**: Folium, Plotly, or Leaflet
- **Charts**: Matplotlib or Plotly for distribution graphs
- **Interface**: Simple HTML/JavaScript served by Flask

### Project Structure
```
bustowork/
├── data/
│   └── gtfs/              # GTFS zip and extracted files (checked in)
├── config.yaml            # User configuration (gitignored)
├── config.example.yaml    # Example configuration (checked in)
├── src/
│   ├── gtfs_loader.py     # Load and parse GTFS data
│   ├── router.py          # Routing engine
│   ├── grid_analyzer.py   # Grid-based analysis
│   ├── heatmap.py         # Heat map generation
│   ├── address_lookup.py  # Address-specific analysis
│   └── app.py             # Flask web application
├── static/                # CSS, JS, generated maps
├── templates/             # HTML templates
├── requirements.txt       # Python dependencies
└── README.md             # Setup and usage instructions
```

## Key Features

### Performance Optimization
- Expanding outward from work location limits computation to relevant areas
- Grid-based approach provides good coverage without excessive computation
- Caching of GTFS schedule lookups

### User Privacy
- Work address stored in gitignored config file
- Only example config checked into repository

### Extensibility
- Configurable parameters for different user preferences
- Could extend to analyze weekend schedules
- Could add additional transit modes (bike, car)

## Success Criteria
1. Heat map correctly identifies neighborhoods with good transit access
2. 80th percentile metric accurately reflects "typical bad day" commute
3. Address lookup provides actionable information about transit service
4. Tool completes analysis in reasonable time (<5 minutes for full heat map)
5. Visualizations are clear and useful for housing decisions
