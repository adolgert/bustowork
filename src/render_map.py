"""
Render the commute heat map as a large static image (PNG / PDF / JPEG).

Draws the filled contour bands from contours.geojson over OpenStreetMap
basemap tiles, with a legend, work marker, and title - suitable for
printing or sharing with someone who just wants to look at a picture.

Usage:
    python src/render_map.py                       # commute_map.png + .pdf
    python src/render_map.py --formats png jpg pdf
    python src/render_map.py --width-inches 30 --dpi 200
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import contextily as cx
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import PathPatch, Patch
from matplotlib.path import Path as MPath
from pyproj import Transformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Same yellow -> royal blue -> dark blue ramp as the web viewer.
CMAP = LinearSegmentedColormap.from_list(
    'commute', ['#FFD700', '#4169E1', '#00008B'])


def main():
    parser = argparse.ArgumentParser(description='Render heat map to image')
    parser.add_argument('--contours',
                        default=str(PROJECT_ROOT / 'contours.geojson'))
    parser.add_argument('--output', default=str(PROJECT_ROOT / 'commute_map'),
                        help='Output path without extension')
    parser.add_argument('--formats', nargs='+', default=['png', 'pdf'],
                        choices=['png', 'jpg', 'pdf'])
    parser.add_argument('--width-inches', type=float, default=24)
    parser.add_argument('--dpi', type=int, default=150)
    parser.add_argument('--title', default=None)
    args = parser.parse_args()

    contours_path = Path(args.contours)
    if not contours_path.exists():
        print(f"{contours_path} not found - run src/generate_heatmap.py "
              f"first (or src/contours.py to rebuild contours).",
              file=sys.stderr)
        sys.exit(1)
    with open(contours_path) as f:
        gj = json.load(f)

    levels = gj['properties']['levels']
    top = levels[-1]
    work = gj['properties']['work_location']
    pct = gj['properties'].get('score_percentile', 80)

    # Web Mercator, to match basemap tiles.
    to_merc = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)

    bounds = [np.inf, np.inf, -np.inf, -np.inf]
    band_patches = []
    for ft in gj['features']:
        color = CMAP(ft['properties']['mid'] / top)
        verts, codes = [], []
        for poly in ft['geometry']['coordinates']:
            for ring in poly:
                lon, lat = zip(*ring)
                x, y = to_merc.transform(lon, lat)
                pts = np.column_stack([x, y])
                bounds = [min(bounds[0], pts[:, 0].min()),
                          min(bounds[1], pts[:, 1].min()),
                          max(bounds[2], pts[:, 0].max()),
                          max(bounds[3], pts[:, 1].max())]
                verts.extend(pts)
                codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(pts) - 1))
        band_patches.append((ft['properties']['band'], color,
                             PathPatch(MPath(verts, codes), facecolor=color,
                                       edgecolor=(0.2, 0.2, 0.2, 0.4),
                                       linewidth=0.4, alpha=0.55)))

    # Figure sized to the data's aspect ratio.
    span_x = bounds[2] - bounds[0]
    span_y = bounds[3] - bounds[1]
    pad = 0.03
    fig_w = args.width_inches
    fig_h = fig_w * span_y / span_x
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(bounds[0] - pad * span_x, bounds[2] + pad * span_x)
    ax.set_ylim(bounds[1] - pad * span_y, bounds[3] + pad * span_y)
    ax.set_axis_off()

    cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik,
                   crs='EPSG:3857', attribution_size=10)

    for _, _, patch in band_patches:
        ax.add_patch(patch)

    wx, wy = to_merc.transform(work['lon'], work['lat'])
    ax.plot(wx, wy, marker='*', markersize=38, color='red',
            markeredgecolor='white', markeredgewidth=2, zorder=10)

    # Legend in the corner: one swatch per band, plus the work star.
    handles = [Patch(facecolor=c, alpha=0.55, edgecolor='gray', label=b)
               for b, c, _ in band_patches]
    handles.append(plt.Line2D([], [], marker='*', markersize=22, color='red',
                              markeredgecolor='white', linestyle='none',
                              label='Work'))
    legend = ax.legend(handles=handles, loc='lower left',
                       title='Door-to-door commute time',
                       fontsize=18, title_fontsize=20,
                       framealpha=0.92, borderpad=1)
    legend.set_zorder(20)

    title = args.title or (
        f"Commute time to work by walking and/or transit\n"
        f"{pct}th percentile over departures 6am-7pm, "
        f"waiting for the bus included")
    ax.set_title(title, fontsize=26, pad=18)

    for fmt in args.formats:
        out = Path(f"{args.output}.{fmt}")
        fig.savefig(out, dpi=args.dpi, bbox_inches='tight',
                    facecolor='white')
        size_mb = out.stat().st_size / 1e6
        print(f"wrote {out} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()
