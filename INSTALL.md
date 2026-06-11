# Installation Guide

Complete installation instructions for the Pittsburgh Commute Analysis Tool.

## System Requirements

- **Python**: 3.9 or higher
- **Java**: JRE 11 or higher (required for r5py routing engine)
- **Operating System**: Linux, macOS, or Windows
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Disk Space**: ~2GB for dependencies and data

## Installation Steps

### 1. Install Java Runtime Environment (JRE)

r5py requires Java to run the R5 routing engine.

#### Ubuntu/Debian Linux
```bash
sudo apt-get update
sudo apt-get install default-jre
```

Verify installation:
```bash
java -version
```

You should see something like:
```
openjdk version "11.0.x" ...
```

#### macOS
Using Homebrew:
```bash
brew install openjdk@11
```

Or download from [Adoptium](https://adoptium.net/) (Eclipse Temurin).

Verify installation:
```bash
java -version
```

#### Windows
1. Download Java JRE from [java.com](https://www.java.com/)
2. Run the installer
3. Add Java to your PATH:
   - Search for "Environment Variables" in Windows
   - Add Java bin directory to PATH (e.g., `C:\Program Files\Java\jre-11\bin`)

Verify installation (in Command Prompt or PowerShell):
```
java -version
```

### 2. Clone Repository

```bash
cd bustowork
```

### 3. Create Virtual Environment (Recommended)

#### Linux/macOS
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Windows
```cmd
python -m venv venv
venv\Scripts\activate
```

### 4. Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- **Core**: pandas, numpy, pyyaml
- **Geospatial**: geopandas, shapely, osmnx, rtree
- **Routing**: r5py (requires Java)
- **Geocoding**: geopy
- **Visualization**: plotly, folium, matplotlib
- **Web**: flask
- **LLM**: anthropic (for Claude API)

**Note**: Some packages (especially geopandas and osmnx) may take several minutes to install.

### 5. Download Map and Transit Data

Two data files are needed in `data/`:

**GTFS transit feed** (expires every few months - re-download when stale):
```bash
curl -L -o data/GTFS.zip "https://www.rideprt.org/developerresources/GTFS.zip"
```
If R5 later complains about empty tables (`EmptyTableError`), remove the
header-only `.txt` files (typically `frequencies.txt`, `fare_rules.txt`)
from the zip.

**OpenStreetMap extract**: download the Pennsylvania PBF from
[Geofabrik](https://download.geofabrik.de/north-america/us/pennsylvania.html)
to `data/pennsylvania.osm.pbf`, then crop it to the Pittsburgh area:

```bash
python src/crop_osm.py   # writes data/pittsburgh.osm.pbf (~45 MB)
```

### 6. Create Configuration File

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your work address:

```yaml
work_address: "Your Work Address, Pittsburgh, PA"
```

**Important**: `config.yaml` is gitignored to keep your work address private.

## Verify Installation

Test that everything is working:

```bash
# Test GTFS loader
python src/find_stops.py --lat 40.4435 --lon -79.9455 --radius 0.5

# Test routing end-to-end (builds the network on first run, ~30 s)
python src/query.py --latlon 40.4520 -79.9280
```

If both commands succeed, you're ready to go!

## Troubleshooting

### "Java not found" or "java: command not found"

**Solution**: Java is not installed or not in your PATH.

- **Linux/macOS**: Install Java using commands above
- **Windows**: Add Java to PATH (see Step 1)
- Restart your terminal after installing

### "No module named 'r5py'"

**Solution**: r5py failed to install.

```bash
pip install r5py
```

If this fails, check that Java is installed first.

### "OSM extract not found"

**Solution**: download the Pennsylvania PBF from
[Geofabrik](https://download.geofabrik.de/north-america/us/pennsylvania.html)
to `data/pennsylvania.osm.pbf` and run `python src/crop_osm.py`.

### "ImportError: No module named 'rtree'"

**Solution**: rtree requires libspatialindex.

**Ubuntu/Debian**:
```bash
sudo apt-get install libspatialindex-dev
pip install rtree
```

**macOS**:
```bash
brew install spatialindex
pip install rtree
```

**Windows**:
Download pre-built wheel from [Christoph Gohlke's site](https://www.lfd.uci.edu/~gohlke/pythonlibs/#rtree)

### "GEOS error" or geopandas issues

**Solution**: Install GEOS library.

**Ubuntu/Debian**:
```bash
sudo apt-get install libgeos-dev
```

**macOS**:
```bash
brew install geos
```

### r5py is slow or hangs

**Symptoms**: First routing calculation takes >5 minutes or appears to hang.

**Solution**: This is normal on first run. r5py builds the transport network, which can take several minutes. Subsequent runs are much faster (network is cached).

If it truly hangs (>10 minutes with no output):
- Check Java heap size: r5py may need more memory
- Try with a smaller area first
- Check that GTFS and OSM files are valid

### "MemoryError" during analysis

**Solution**: Increase available memory.

For Java/r5py:
```bash
export _JAVA_OPTIONS="-Xmx4g"  # Use 4GB heap
```

For Python:
- Process grid in chunks (modify grid generator)
- Use a machine with more RAM
- Reduce grid resolution (increase grid_spacing in config)

## Platform-Specific Notes

### Linux
Most dependencies install smoothly. Use system package manager for native libraries (GEOS, spatialindex, Java).

### macOS
Homebrew is recommended for installing dependencies. M1/M2 Macs may need Rosetta for some packages.

### Windows
- Use WSL2 (Windows Subsystem for Linux) for easier installation
- Or install native dependencies via conda: `conda install geopandas osmnx`
- Visual C++ Build Tools may be required for some packages

## Alternative: Using Conda

If you prefer conda:

```bash
conda create -n bustowork python=3.11
conda activate bustowork
conda install -c conda-forge geopandas osmnx geopy plotly flask pyyaml tqdm
pip install r5py anthropic
```

## Development Installation

For development (includes testing tools):

```bash
pip install -r requirements.txt
pip install pytest black flake8 mypy
```

## Uninstall

To completely remove:

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment and cached data
rm -rf venv/
rm -rf cache/
rm -rf data/pittsburgh.osm*

# Keep GTFS data and your config
# Delete those manually if desired
```

## Getting Help

If you encounter issues not covered here:

1. Check that Java is installed: `java -version`
2. Check that Python is 3.9+: `python --version`
3. Check the [r5py documentation](https://r5py.readthedocs.io/)

## Next Steps

After successful installation, see [README.md](README.md) for usage instructions.
