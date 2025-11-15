#!/usr/bin/env python3
"""
Setup script for r5py routing.

Downloads OSM data and checks dependencies.
"""

import subprocess
import sys
from pathlib import Path


def check_java():
    """Check if Java is installed."""
    print("Checking for Java...")
    try:
        result = subprocess.run(
            ['java', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        print("  ✓ Java is installed")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  ✗ Java is NOT installed")
        print("\nr5py requires Java Runtime Environment (JRE)")
        print("Install with:")
        print("  Ubuntu/Debian: sudo apt-get install default-jre")
        print("  macOS: brew install openjdk")
        print("  Windows: Download from https://www.java.com/")
        return False


def check_osm_data():
    """Check if OSM data exists."""
    print("\nChecking for OSM data...")

    pbf_path = Path("data/pittsburgh.osm.pbf")
    osm_path = Path("data/pittsburgh.osm")

    if pbf_path.exists():
        print(f"  ✓ Found PBF file: {pbf_path}")
        return pbf_path
    elif osm_path.exists():
        print(f"  ✓ Found OSM file: {osm_path}")
        print("  → For better performance, convert to PBF:")
        print(f"     osmconvert {osm_path} -o={pbf_path}")
        return osm_path
    else:
        print("  ✗ OSM data not found")
        return None


def download_osm_data():
    """Download OSM data for Pittsburgh."""
    print("\nDownloading OSM data for Pittsburgh...")
    print("(This may take several minutes)")

    try:
        import osmnx as ox

        # Download Pittsburgh street network
        print("  Downloading street network...")
        graph = ox.graph_from_place(
            "Pittsburgh, Pennsylvania, USA",
            network_type='walk'
        )

        # Save as OSM XML
        osm_path = Path("data/pittsburgh.osm")
        osm_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"  Saving to {osm_path}...")
        ox.save_graph_xml(graph, filepath=str(osm_path))

        print(f"  ✓ Downloaded to {osm_path}")
        print(f"  Size: {osm_path.stat().st_size / 1024 / 1024:.1f} MB")

        return osm_path

    except ImportError:
        print("  ✗ osmnx not installed")
        print("  Install with: pip install osmnx")
        return None
    except Exception as e:
        print(f"  ✗ Error downloading: {e}")
        return None


def check_gtfs_data():
    """Check if GTFS data exists."""
    print("\nChecking for GTFS data...")

    gtfs_path = Path("data/GTFS.zip")
    if gtfs_path.exists():
        print(f"  ✓ Found GTFS file: {gtfs_path}")
        print(f"  Size: {gtfs_path.stat().st_size / 1024 / 1024:.1f} MB")
        return True
    else:
        print("  ✗ GTFS data not found at data/GTFS.zip")
        return False


def install_r5py():
    """Install r5py if not already installed."""
    print("\nChecking r5py installation...")

    try:
        import r5py
        print("  ✓ r5py is installed")
        return True
    except ImportError:
        print("  → Installing r5py...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'r5py'],
                check=True
            )
            print("  ✓ r5py installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("  ✗ Failed to install r5py")
            return False


def main():
    """Run setup checks and downloads."""
    print("=" * 70)
    print("r5py Router Setup")
    print("=" * 70)

    all_good = True

    # Check Java
    if not check_java():
        all_good = False

    # Check/install r5py
    if not install_r5py():
        all_good = False

    # Check GTFS data
    if not check_gtfs_data():
        all_good = False

    # Check/download OSM data
    osm_path = check_osm_data()
    if not osm_path:
        print("\nAttempting to download OSM data...")
        osm_path = download_osm_data()
        if not osm_path:
            all_good = False

    print("\n" + "=" * 70)
    if all_good:
        print("✓ Setup complete! Ready to use r5py router.")
        print("\nNext steps:")
        print("  1. Create config.yaml from config.example.yaml")
        print("  2. Test routing: python src/r5py_router.py")
    else:
        print("✗ Setup incomplete. Please fix the issues above.")
        sys.exit(1)
    print("=" * 70)


if __name__ == '__main__':
    main()
