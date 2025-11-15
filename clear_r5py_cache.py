#!/usr/bin/env python3
"""
Clear r5py cache to fix serialization errors.
"""

from pathlib import Path
import shutil
import r5py

# Get r5py cache directory
cache_dir = r5py.config.Config().CACHE_DIR

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
