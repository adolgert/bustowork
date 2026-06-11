"""
Crop a large OSM PBF file to a bounding box.

The full Pennsylvania extract makes r5py network builds slow. This crops it
to the greater Pittsburgh area so the network builds in seconds instead of
minutes. Keeps every way that has at least one node inside the box, plus all
nodes those ways reference, so streets are not clipped mid-segment.

Usage:
    python src/crop_osm.py [input.pbf] [output.pbf]
"""

import sys
from pathlib import Path

import osmium

# Greater Pittsburgh / Allegheny County, padded so 90-minute trips
# that dip outside the county still route.
BBOX = {
    'min_lon': -80.45,
    'min_lat': 40.10,
    'max_lon': -79.55,
    'max_lat': 40.75,
}


class BboxNodeCollector(osmium.SimpleHandler):
    """Pass 1: collect ids of nodes inside the bounding box."""

    def __init__(self):
        super().__init__()
        self.in_box = set()

    def node(self, n):
        if (BBOX['min_lon'] <= n.location.lon <= BBOX['max_lon']
                and BBOX['min_lat'] <= n.location.lat <= BBOX['max_lat']):
            self.in_box.add(n.id)


class WayCollector(osmium.SimpleHandler):
    """Pass 2: find ways touching the box and all node ids they need."""

    def __init__(self, nodes_in_box):
        super().__init__()
        self.nodes_in_box = nodes_in_box
        self.way_ids = set()
        self.needed_nodes = set()

    def way(self, w):
        refs = [n.ref for n in w.nodes]
        if any(r in self.nodes_in_box for r in refs):
            self.way_ids.add(w.id)
            self.needed_nodes.update(refs)


class NodeWriter(osmium.SimpleHandler):
    """Pass 3: write needed nodes."""

    def __init__(self, writer, needed_nodes):
        super().__init__()
        self.writer = writer
        self.needed_nodes = needed_nodes

    def node(self, n):
        if n.id in self.needed_nodes:
            self.writer.add_node(n)


class WayWriter(osmium.SimpleHandler):
    """Pass 4: write kept ways."""

    def __init__(self, writer, way_ids):
        super().__init__()
        self.writer = writer
        self.way_ids = way_ids

    def way(self, w):
        if w.id in self.way_ids:
            self.writer.add_way(w)


def crop(input_path: str, output_path: str):
    input_path = Path(input_path)
    output_path = Path(output_path)
    if output_path.exists():
        output_path.unlink()

    print(f"Pass 1/4: scanning nodes in bbox ...")
    collector = BboxNodeCollector()
    collector.apply_file(str(input_path))
    print(f"  {len(collector.in_box):,} nodes inside bbox")

    print(f"Pass 2/4: scanning ways ...")
    ways = WayCollector(collector.in_box)
    ways.apply_file(str(input_path))
    print(f"  {len(ways.way_ids):,} ways kept, {len(ways.needed_nodes):,} nodes needed")
    del collector

    writer = osmium.SimpleWriter(str(output_path))
    try:
        print(f"Pass 3/4: writing nodes ...")
        NodeWriter(writer, ways.needed_nodes).apply_file(str(input_path))
        print(f"Pass 4/4: writing ways ...")
        WayWriter(writer, ways.way_ids).apply_file(str(input_path))
    finally:
        writer.close()

    size_mb = output_path.stat().st_size / 1e6
    print(f"Done: {output_path} ({size_mb:.0f} MB)")


if __name__ == '__main__':
    input_pbf = sys.argv[1] if len(sys.argv) > 1 else 'data/pennsylvania.osm.pbf'
    output_pbf = sys.argv[2] if len(sys.argv) > 2 else 'data/pittsburgh.osm.pbf'
    crop(input_pbf, output_pbf)
