# Pittsburgh Commute Analysis Tool - Project Overview

## Project Summary
A personalized commute analysis tool that evaluates residential locations in Pittsburgh based on a custom transit accessibility metric. The tool calculates travel times for every minute of the day (6am-7pm) in both directions, then uses the 80th percentile as a location quality score.

## Tech Stack

### Backend
- **Python 3.9+** - Core language
- **Flask** - Web framework for serving UI and API
- **gtfs-kit** - GTFS parsing and schedule queries (handles edge cases)
- **OSMnx** - OpenStreetMap street network for accurate walking distances
- **geopy** - Geocoding (address → lat/lon) using Nominatim
- **NetworkX** - Graph algorithms for routing
- **NumPy/Pandas** - Data manipulation and statistics

### Visualization
- **Plotly** - Interactive heat maps and distribution graphs (handles large datasets)
- **Folium** - Alternative for map visualization (if needed)
- **Matplotlib** - Static charts and graphs

### LLM Integration
- **Anthropic API (Claude Haiku)** - Generate human-readable bus service descriptions

### Data
- **GTFS Static** - Port Authority of Allegheny County transit data
- **OpenStreetMap** - Pittsburgh street network data

## Top Technical Risks

### 1. Performance / Computation Time ⚠️ HIGH RISK
**Problem**: Calculating 1,560 routes per grid point × hundreds of grid points = hundreds of thousands of route calculations could take hours or days.

**Mitigations**:
- Use mature routing libraries instead of building from scratch
- Heavy caching (GTFS lookups, stop-to-stop walking times)
- Multi-threading/parallel processing
- Start with coarser grid for testing
- Pre-compute common patterns

**Fallback**: Reduce time sampling (every 5-10 minutes instead of every minute)

### 2. Walking Distance Calculations ⚠️ MEDIUM-HIGH RISK
**Problem**: "1 mile to bus stop" must be walking distance on streets, not straight-line. Need street network routing for accuracy.

**Mitigations**:
- Use OSMnx library for Pittsburgh street network from OpenStreetMap
- Pre-compute walking distances between grid points and all bus stops
- Cache walking distance matrix

**Fallback**: Use straight-line × 1.3 multiplier as approximation (less accurate but faster)

### 3. Geocoding Addresses ⚠️ MEDIUM RISK
**Problem**: Converting addresses to coordinates; free APIs have rate limits and varying accuracy.

**Mitigations**:
- Use geopy with OpenStreetMap's Nominatim (free, no API key)
- Add caching for geocoded addresses
- Validate results against known locations

**Fallback**: Support lat/lon input in config instead of address

### 4. GTFS Complexity ⚠️ MEDIUM RISK
**Problem**: GTFS has many edge cases (calendar exceptions, service patterns, midnight-spanning trips, stop time interpolation).

**Mitigations**:
- Use mature library (gtfs-kit) that handles edge cases
- Validate GTFS data on load
- Focus on typical weekdays, ignore exceptions initially

**Fallback**: Simplify to "average weekday" schedule

### 5. Memory Usage ⚠️ LOW-MEDIUM RISK
**Problem**: Loading entire GTFS + street network + route calculations could use significant RAM.

**Mitigations**:
- Stream/lazy-load GTFS where possible
- Don't store all intermediate calculations
- Generate heat map incrementally

**Fallback**: Process grid in chunks, save intermediate results

### 6. Browser Heat Map Rendering ⚠️ LOW RISK
**Problem**: Thousands of grid points might be slow to render in browser.

**Mitigations**:
- Use Plotly (handles large datasets with WebGL)
- Consider aggregation/clustering for display

**Fallback**: Export static image instead of fully interactive map

## High-Level Implementation Stages

### Stage 1: GTFS Foundation
**Goal**: Prove we can access transit data

**Deliverables**:
- Download Pittsburgh GTFS to `data/`
- Load and parse GTFS files
- Spatial index of bus stops
- Query stops within radius of a point

**Working Prototype**: CLI tool
```bash
python src/find_stops.py --lat 40.4406 --lon -79.9959 --radius 0.5
```
Output: Lists nearby stops with routes and basic schedule info

**Validation**: Can we see reasonable bus stops near known locations?

---

### Stage 2: Single Route Calculator
**Goal**: Prove routing algorithm works for one trip

**Deliverables**:
- Geocoding (address → lat/lon)
- Walking time calculator using street network
- Single-time routing engine: origin + destination + time → fastest route
- Handle: walking-only, direct bus, one-transfer routes

**Working Prototype**: CLI calculates one route
```bash
python src/calculate_route.py \
  --from "123 Main St" \
  --to "456 Work Ave" \
  --time "08:30"
```
Output: Detailed route with times and transit info

**Validation**: Compare results to Google Maps for known routes

---

### Stage 3: Time Distribution Engine (CORE VALUE)
**Goal**: Implement custom metric for one location

**Deliverables**:
- Loop through every minute 6am-7pm
- Calculate route in both directions (to work, from work)
- Collect 1,560 travel times
- Calculate percentiles (50th, 80th, 90th, etc.)

**Working Prototype**: CLI shows distribution for one address
```bash
python src/analyze_address.py --address "789 Potential Home St"
```
Output:
- Distribution graph (PNG)
- Percentile statistics
- Min/max times

**Validation**: Does the metric match intuition for known locations? **CRITICAL STAGE** - performance here determines feasibility of Stage 4.

---

### Stage 4: Grid Heat Map Generator
**Goal**: Scale to many locations

**Deliverables**:
- Grid generation (500ft spacing, expand from work location)
- Apply Stage 3 analysis to each grid point
- Stop expansion when scores exceed threshold
- Export results to JSON/CSV
- Performance optimization (caching, parallelization)

**Working Prototype**: CLI generates heat map data
```bash
python src/generate_heatmap.py --config config.yaml
```
Output:
- Progress indicator
- Saved heat map data file
- Performance statistics

**Validation**: Reasonable computation time? Scores make spatial sense?

---

### Stage 5: Web Visualization
**Goal**: Make data explorable

**Deliverables**:
- Flask web server
- Load pre-computed heat map data
- Interactive map with yellow-to-blue color gradient
- Click interaction for detailed point stats
- Legend and controls

**Working Prototype**: Web app at `http://localhost:5000`
- Heat map overlay on Pittsburgh street map
- Click any point → see score and stats
- Color legend with time scale

**Validation**: Is the heat map useful for identifying good neighborhoods?

---

### Stage 6: Address Lookup + LLM Integration
**Goal**: Complete tool with both interfaces

**Deliverables**:
- Address search form in web UI
- On-demand calculation for arbitrary addresses
- LLM integration with Anthropic API (Haiku)
- Generate human-readable bus service descriptions
- Display distribution graph for searched address

**Working Prototype**: Full web application
- Heat map view (from Stage 5)
- Address lookup form
  - Input: Any Pittsburgh address
  - Output: Distribution graph + 80th percentile score
  - LLM-generated description of nearby transit service

**Validation**: Does the complete tool provide actionable housing decision data?

---

## Architectural Principles

### Separation of Concerns
```
src/
├── gtfs_loader.py       # GTFS data loading and parsing
├── geocoder.py          # Address to coordinate conversion
├── street_network.py    # Walking distance calculations
├── router.py            # Core routing algorithm
├── analyzer.py          # Time distribution analysis
├── grid_generator.py    # Grid creation and expansion
├── heatmap.py           # Heat map data generation
├── llm_service.py       # LLM integration for descriptions
└── app.py               # Flask web application
```

### Data Flow
```
GTFS Data + Street Network
    ↓
Router (single trip calculation)
    ↓
Analyzer (1,560 trips per location)
    ↓
Grid Generator (apply to many locations)
    ↓
JSON/CSV Data
    ↓
Web Visualizer (Plotly maps + Flask)

Parallel Flow:
Address Input → Analyzer → LLM Service → Description
```

### Testing Strategy
- Each stage produces inspectable output
- Stage 3 is critical - validate thoroughly before scaling
- Performance testing at Stage 3 determines Stage 4 feasibility
- Benchmark targets:
  - Stage 3 (one address): < 10 seconds → feasible
  - Stage 3 (one address): > 2 minutes → need optimization
  - Stage 4 (400 grid points): < 2 hours → acceptable

### Performance Strategy
- Optimize at Stage 3, not Stage 4
- Key optimizations:
  1. Cache GTFS schedule lookups (same queries repeated)
  2. Pre-compute walking distance matrix (grid ↔ stops)
  3. Parallelize grid point calculations (embarrassingly parallel)
  4. Use spatial indexing for stop lookups
  5. Consider compiled extensions (Cython/Numba) if needed

## Success Criteria
1. Heat map identifies neighborhoods with good transit access
2. 80th percentile metric reflects "typical bad day" commute
3. Address lookup provides actionable transit information
4. Full heat map completes in < 2 hours
5. Visualizations are clear and useful for housing decisions
6. Tool handles edge cases gracefully (no transit nearby, etc.)

## Development Approach
- Build incrementally: each stage is a working prototype
- Validate thoroughly at Stage 3 before scaling to grid
- Commit and push after each major stage
- Keep work address in gitignored config file
- Check in GTFS data and example config
