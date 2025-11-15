# Stage 2 Implementation Notes

## Status: Partially Complete

Stage 2 implements the core routing logic but has **significant performance issues** that need to be addressed before proceeding to Stage 3.

## What Works
- ✅ Geocoding with geopy (with fallback cache for known addresses)
- ✅ Street network module with OSMnx support (using fallback haversine × 1.3 for testing)
- ✅ Router class structure with walking-only and transit routing
- ✅ GTFS schedule querying

## Performance Problem

The `_find_direct_route()` function is too slow due to nested loops:
- For each origin stop (potentially 30-50 within 1 mile)
- For each destination stop (potentially 30-50 within 1 mile)
- For each trip from origin stop (potentially hundreds)
- Check if trip also visits destination stop

This creates O(origin_stops × dest_stops × trips) complexity = **tens of thousands of iterations**.

### Current Timing
- Simple route calculation: **>30 seconds** (times out)
- This makes Stage 3 infeasible (would need 1,560 × >30s = **13+ hours** per location!)

## Optimization Strategies Needed

### 1. Pre-compute Stop-to-Stop Connections
Build a graph of which stops are directly connected by routes:
```python
# One-time preprocessing
stop_pairs = {}  # (stop_id_1, stop_id_2) -> [list of trips]
for trip in trips:
    stops_on_trip = get_stops_for_trip(trip)
    for i, stop1 in enumerate(stops_on_trip):
        for stop2 in stops_on_trip[i+1:]:
            stop_pairs[(stop1, stop2)].append(trip)
```

### 2. Time-based Indexing
Index trips by departure time at each stop:
```python
# departure_index[stop_id][time_bucket] = [trips departing in this bucket]
```

### 3. Limit Search Space
- Only consider top N closest stops (e.g., 10 closest, not all within 1 mile)
- Use spatial clustering to reduce stop pairs to check
- Early termination once we find a route under target time

### 4. Caching
- Cache walking distances between grid points and stops
- Cache route calculations for repeated origin-destination pairs

### 5. Alternative: Use Existing Library
Consider using established routing libraries:
- **OpenTripPlanner** (OTP) - Java-based but has Python bindings
- **r5py** - Rapid Realistic Routing on Real-world and Reimagined networks
- **Valhalla** with GTFS integration

## Recommendation

Before proceeding to Stage 3, either:

1. **Implement optimizations 1-4** above (estimated 4-6 hours work)
2. **Switch to r5py or similar library** (estimated 2-3 hours to integrate)
3. **Simplify the metric** to make fewer route calculations (e.g., sample every 15 min instead of every minute)

Option 2 (r5py) is likely fastest path forward if the library works well with Pittsburgh's GTFS data.

## Files Created
- `src/geocoder.py` - Address to coordinate conversion
- `src/street_network.py` - Walking distance calculations
- `src/router.py` - Transit routing engine (needs optimization)
- `src/calculate_route.py` - CLI tool for testing

## Next Steps
1. Benchmark different optimization approaches
2. Test with simplified time sampling (every 10-15 minutes)
3. Consider r5py integration
4. Only proceed to Stage 3 once single route calculation is <2 seconds
