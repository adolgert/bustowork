# Data Directory

This directory contains transit data for the Pittsburgh commute analysis tool.

## GTFS Data

Place the Pittsburgh Regional Transit GTFS static data in `gtfs/`:

### Where to Download
Download the latest GTFS static feed from one of these sources:

1. **Mobility Database** (recommended): https://mobilitydatabase.org/
   - Search for "Pittsburgh Regional Transit" or "Port Authority of Allegheny County"
   - Download the GTFS Static feed

2. **Pittsburgh Regional Transit Developer Resources**: https://www.rideprt.org/business-center/developer-resources/
   - May require creating a free developer account

3. **Western PA Regional Data Center**: https://data.wprdc.org/group/transportation

### File Placement
- Download the GTFS zip file
- Either:
  - Place the zip file as `gtfs/gtfs.zip`, OR
  - Extract the zip and place the contents in `gtfs/` directory

### Expected GTFS Files
The GTFS feed should contain these files:
- `agency.txt` - Transit agency information
- `stops.txt` - Bus and rail stops
- `routes.txt` - Transit routes
- `trips.txt` - Individual trip schedules
- `stop_times.txt` - Stop times for each trip
- `calendar.txt` - Service calendar (weekday/weekend patterns)
- `calendar_dates.txt` - Service exceptions (holidays, etc.)
- `shapes.txt` - Route path geometries (optional)

## OpenStreetMap Data

Street network data will be downloaded automatically by the tool using OSMnx when needed.
