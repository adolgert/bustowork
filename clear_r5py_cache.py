#!/usr/bin/env python3
"""
Clear r5py cache to fix serialization errors.
"""

from pathlib import Path
import shutil
import os
import sys

# Find r5py cache directory
# Check common locations
possible_cache_dirs = [
    Path.home() / ".cache" / "r5py",  # Linux
    Path.home() / "Library" / "Caches" / "r5py",  # macOS
    Path(os.getenv("LOCALAPPDATA", "")) / "r5py" / "Cache" if os.name == 'nt' else None,  # Windows
]

cache_dir = None
for dir_path in possible_cache_dirs:
    if dir_path and dir_path.exists():
        cache_dir = dir_path
        break

if not cache_dir:
    # Try to import r5py and check if it has cache info
    try:
        # Just check default location
        cache_dir = Path.home() / ".cache" / "r5py"
    except:
        print("Could not determine r5py cache directory")
        sys.exit(1)

print(f"r5py cache directory: {cache_dir}")

if cache_dir.exists():
    print(f"Cache size: {sum(f.stat().st_size for f in cache_dir.glob('**/*') if f.is_file()) / 1024 / 1024:.1f} MB")

    response = input(f"\nDelete all cached transport networks? (yes/no): ")

    if response.lower() == 'yes':
        # Delete all .transport_network files
        deleted = 0
        for cache_file in cache_dir.glob('*.transport_network'):
            print(f"  Deleting: {cache_file.name}")
            cache_file.unlink()
            deleted += 1

        print(f"\n✓ Deleted {deleted} cached network(s)")
        print("Run your grid generator again - it will rebuild the network from scratch")
    else:
        print("Cancelled")
else:
    print("Cache directory does not exist - nothing to clean")
