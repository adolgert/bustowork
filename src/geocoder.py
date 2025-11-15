"""
Geocoding utilities for converting addresses to coordinates.
"""

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from typing import Tuple, Optional
import time


class Geocoder:
    """Geocode addresses to coordinates."""

    def __init__(self):
        """Initialize geocoder with Nominatim (OpenStreetMap)."""
        self.geolocator = Nominatim(
            user_agent="pittsburgh-commute-analyzer",
            timeout=10
        )
        self._cache = {}

        # Pre-cache known Pittsburgh locations
        self._cache["5000 forbes ave, pittsburgh, pa"] = (40.4435, -79.9455)
        self._cache["carnegie mellon university, pittsburgh, pa"] = (40.4435, -79.9455)

    def geocode(
        self,
        address: str,
        city: str = "Pittsburgh",
        state: str = "PA"
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to (latitude, longitude).

        Args:
            address: Street address
            city: City name (default: Pittsburgh)
            state: State abbreviation (default: PA)

        Returns:
            Tuple of (lat, lon) or None if geocoding fails
        """
        # Check cache
        cache_key = f"{address}, {city}, {state}".lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build full address
        full_address = f"{address}, {city}, {state}, USA"

        try:
            location = self.geolocator.geocode(full_address)

            if location:
                result = (location.latitude, location.longitude)
                self._cache[cache_key] = result
                return result
            else:
                print(f"Warning: Could not geocode '{full_address}'")
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Geocoding error: {e}")
            return None

    def reverse_geocode(
        self,
        lat: float,
        lon: float
    ) -> Optional[str]:
        """
        Reverse geocode coordinates to an address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Address string or None if reverse geocoding fails
        """
        try:
            location = self.geolocator.reverse((lat, lon))
            if location:
                return location.address
            return None
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Reverse geocoding error: {e}")
            return None


def main():
    """Test geocoding."""
    geocoder = Geocoder()

    # Test with work address
    test_addresses = [
        "5000 Forbes Ave, Pittsburgh, PA",
        "Downtown Pittsburgh, PA",
        "Carnegie Mellon University, Pittsburgh, PA"
    ]

    for addr in test_addresses:
        print(f"\nGeocoding: {addr}")
        result = geocoder.geocode(addr, "", "")  # Address already has city/state
        if result:
            lat, lon = result
            print(f"  → {lat:.6f}, {lon:.6f}")

            # Test reverse geocoding
            reverse = geocoder.reverse_geocode(lat, lon)
            print(f"  ← {reverse}")


if __name__ == '__main__':
    main()
