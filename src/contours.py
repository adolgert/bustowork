"""
Build filled contour bands from heatmap_data.json.

The heat map points lie on a regular grid in PA State Plane South
(EPSG:2272). This reconstructs that grid, runs contourpy's filled-contour
algorithm on it, and returns the bands as a GeoJSON FeatureCollection
(one MultiPolygon feature per travel-time band) for Plotly's
choroplethmapbox layer.
"""

import json
from pathlib import Path

import numpy as np
from contourpy import contour_generator
from pyproj import Transformer

BAND_MINUTES = 10  # contour level spacing


def _grid_from_points(data):
    """Rebuild the regular 2272-feet grid of scores from the point list."""
    spacing = float(data['grid_spacing_feet'])
    work = data['work_location']

    to_plane = Transformer.from_crs('EPSG:4326', 'EPSG:2272', always_xy=True)
    lons = np.array([p['lon'] for p in data['points']])
    lats = np.array([p['lat'] for p in data['points']])
    scores = np.array([p['score'] if p['score'] is not None else np.nan
                       for p in data['points']], dtype=float)

    x, y = to_plane.transform(lons, lats)
    wx, wy = to_plane.transform(work['lon'], work['lat'])
    i = np.rint((x - wx) / spacing).astype(int)
    j = np.rint((y - wy) / spacing).astype(int)

    z = np.full((j.max() - j.min() + 1, i.max() - i.min() + 1), np.nan)
    z[j - j.min(), i - i.min()] = scores
    xs = wx + np.arange(i.min(), i.max() + 1) * spacing
    ys = wy + np.arange(j.min(), j.max() + 1) * spacing
    return xs, ys, z


def build_contour_geojson(heatmap_path) -> dict:
    with open(heatmap_path) as f:
        data = json.load(f)

    xs, ys, z = _grid_from_points(data)
    top = np.nanmax(z)
    levels = list(range(0, int(np.ceil(top / BAND_MINUTES)) * BAND_MINUTES + 1,
                        BAND_MINUTES))

    gen = contour_generator(x=xs, y=ys, z=np.ma.masked_invalid(z),
                            fill_type='OuterOffset')
    to_wgs = Transformer.from_crs('EPSG:2272', 'EPSG:4326', always_xy=True)

    features = []
    for k, (lo, hi) in enumerate(zip(levels[:-1], levels[1:])):
        points_list, offsets_list = gen.filled(lo, hi)
        polygons = []
        for verts, offsets in zip(points_list, offsets_list):
            lon, lat = to_wgs.transform(verts[:, 0], verts[:, 1])
            ring_pts = np.column_stack([np.round(lon, 6), np.round(lat, 6)])
            rings = [ring_pts[a:b].tolist()
                     for a, b in zip(offsets[:-1], offsets[1:])]
            for ring in rings:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
            polygons.append(rings)
        if not polygons:
            continue
        features.append({
            'type': 'Feature',
            'id': k,
            'properties': {
                'band': f'{lo}–{hi} min',
                'mid': (lo + hi) / 2,
            },
            'geometry': {'type': 'MultiPolygon', 'coordinates': polygons},
        })

    return {
        'type': 'FeatureCollection',
        'features': features,
        'properties': {
            'levels': levels,
            'band_minutes': BAND_MINUTES,
            'work_location': data['work_location'],
            'score_percentile': data.get('score_percentile', 80),
        },
    }


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    geojson = build_contour_geojson(root / 'heatmap_data.json')
    out = root / 'contours.geojson'
    with open(out, 'w') as f:
        json.dump(geojson, f)
    sizes = [len(json.dumps(ft)) for ft in geojson['features']]
    print(f"{len(geojson['features'])} bands -> {out} "
          f"({sum(sizes)/1e6:.1f} MB)")
