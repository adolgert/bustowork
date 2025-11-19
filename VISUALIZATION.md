# Heat Map Visualization

Interactive web interface to view your Pittsburgh commute heat map.

## Quick Start

```bash
# Start the web server
python src/app.py

# Open your browser to:
http://localhost:5000
```

## Testing with Sample Data

If your heat map is still generating, test the visualization with sample data:

```bash
# Copy sample data to expected location
cp heatmap_sample.json heatmap_data.json

# Start the server
python src/app.py
```

## Using Your Real Data

Once `grid_generator.py` completes, it will create `heatmap_data.json`. The visualization will automatically load it.

## Features

### Interactive Map
- **Yellow points** = Fast commute (close to work)
- **Blue points** = Slower commute (farther from work)
- **Red star** = Your work location
- **Click any point** to see detailed stats

### Statistics Dashboard
- Total points analyzed
- Number of rings explored
- Reachable points
- Best/median/90th percentile scores

### Point Details (on hover)
- 80th percentile score (overall location quality)
- Exact coordinates
- Ring number (distance from work)
- Reachability percentage
- Min/median/max travel times

## Understanding the Colors

The color scale represents the **80th percentile commute time**:

- **Yellow** (#FFD700): Fast - typically 5-15 minutes
- **Royal Blue** (#4169E1): Medium - typically 15-35 minutes
- **Dark Blue** (#00008B): Slow - typically 35+ minutes

## API Endpoints

If you want to build custom visualizations:

### `GET /api/heatmap`
Returns complete heat map data as JSON.

### `GET /api/stats`
Returns summary statistics:
```json
{
  "total_points": 49,
  "rings_analyzed": 3,
  "reachable_points": 47,
  "score_min": 5.2,
  "score_max": 45.7,
  "score_median": 24.3,
  "score_mean": 25.1,
  "percentiles": {
    "25th": 18.5,
    "50th": 24.3,
    "75th": 32.1,
    "90th": 38.4
  }
}
```

## Customization

### Change Port
Edit `src/app.py` line 74:
```python
app.run(debug=True, host='0.0.0.0', port=5000)  # Change 5000 to your port
```

### Change Color Scale
Edit `templates/index.html` around line 214:
```javascript
colorscale: [
    [0, '#FFD700'],     // Yellow (fast)
    [0.5, '#4169E1'],   // Royal Blue (medium)
    [1, '#00008B']      // Dark Blue (slow)
]
```

### Change Map Style
Edit `templates/index.html` around line 262:
```javascript
mapbox: {
    style: 'open-street-map',  // Or: 'carto-positron', 'stamen-terrain'
    // ...
}
```

## Troubleshooting

### "Heat map data not found"
- Make sure `heatmap_data.json` exists in the project root
- Or use sample data: `cp heatmap_sample.json heatmap_data.json`

### Map not loading
- Check browser console for errors (F12)
- Verify internet connection (loads OpenStreetMap tiles)
- Make sure Flask is running: `python src/app.py`

### Points not showing
- Verify `heatmap_data.json` has valid points with scores
- Check that points have non-null `score` values
- Look at `/api/stats` endpoint to see if data loaded

## Next Steps

After viewing your heat map:
- Identify neighborhoods with good scores
- Click points to compare travel time distributions
- Look for clusters of yellow points (good transit access)
- Consider visiting high-scoring locations in person!
