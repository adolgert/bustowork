"""
Flask web application for heat map visualization.
"""

from flask import Flask, render_template, jsonify
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from contours import build_contour_geojson

# Flask app with template folder pointing to project root
app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'))


@app.route('/')
def index():
    """Render the main heat map page."""
    return render_template('index.html')


@app.route('/api/heatmap')
def get_heatmap_data():
    """API endpoint to fetch heat map data."""
    # Look for heatmap_data.json in project root (parent of src/)
    project_root = Path(__file__).parent.parent
    heatmap_file = project_root / 'heatmap_data.json'

    if not heatmap_file.exists():
        return jsonify({
            'error': 'Heat map data not found',
            'message': 'Run src/generate_heatmap.py to generate heat map data first'
        }), 404

    with open(heatmap_file, 'r') as f:
        data = json.load(f)

    return jsonify(data)


@app.route('/api/contours')
def get_contours():
    """Filled contour bands as GeoJSON, cached next to the heat map data."""
    project_root = Path(__file__).parent.parent
    heatmap_file = project_root / 'heatmap_data.json'
    cache_file = project_root / 'contours.geojson'

    if not heatmap_file.exists():
        return jsonify({'error': 'Heat map data not found'}), 404

    if (not cache_file.exists()
            or cache_file.stat().st_mtime < heatmap_file.stat().st_mtime):
        geojson = build_contour_geojson(heatmap_file)
        with open(cache_file, 'w') as f:
            json.dump(geojson, f)
    else:
        with open(cache_file) as f:
            geojson = json.load(f)

    return jsonify(geojson)


@app.route('/api/stats')
def get_stats():
    """API endpoint to fetch heat map statistics."""
    # Look for heatmap_data.json in project root (parent of src/)
    project_root = Path(__file__).parent.parent
    heatmap_file = project_root / 'heatmap_data.json'

    if not heatmap_file.exists():
        return jsonify({'error': 'Heat map data not found'}), 404

    with open(heatmap_file, 'r') as f:
        data = json.load(f)

    # Calculate statistics
    scores = [p['score'] for p in data['points'] if p['score'] is not None]

    if not scores:
        return jsonify({'error': 'No valid scores in heat map data'}), 400

    import numpy as np

    stats = {
        'total_points': data['total_points'],
        'rings_analyzed': data['rings_analyzed'],
        'reachable_points': len(scores),
        'score_min': min(scores),
        'score_max': max(scores),
        'score_median': float(np.median(scores)),
        'score_mean': float(np.mean(scores)),
        'percentiles': {
            '25th': float(np.percentile(scores, 25)),
            '50th': float(np.percentile(scores, 50)),
            '75th': float(np.percentile(scores, 75)),
            '90th': float(np.percentile(scores, 90))
        }
    }

    return jsonify(stats)


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("Pittsburgh Commute Heat Map Viewer")
    print("=" * 70)
    print("\nStarting Flask server...")
    print("Open your browser to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
