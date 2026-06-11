#!/usr/bin/env bash
# Bundle code + data + results for transfer to another machine.
#
# Includes: git-tracked files (with history), config.yaml, the cropped OSM
# extract, and the generated heat map, so nothing needs recomputing on the
# target. Excludes: venv (rebuild there), the 323 MB pennsylvania.osm.pbf
# (only needed to re-crop), and r5py's network cache (rebuilds in ~30 s).
set -euo pipefail
cd "$(dirname "$0")"

OUT=${1:-bustowork-transfer.tar.gz}

tar czf "$OUT" \
    --exclude='data/pennsylvania.osm.pbf' \
    --exclude='data/pittsburgh.osm' \
    --exclude='data/GTFS_original.zip' \
    --exclude='data/GTFS_2025fall.zip' \
    .git \
    $(git ls-files) \
    config.yaml \
    data/pittsburgh.osm.pbf \
    heatmap_data.json \
    contours.geojson

du -h "$OUT"
echo "
On the target machine:
  tar xzf $OUT -C bustowork && cd bustowork
  # install Java 21+, then:
  python -m venv venv && venv/bin/pip install -r requirements.txt
  venv/bin/python src/query.py --latlon 40.452 -79.928   # smoke test
"
