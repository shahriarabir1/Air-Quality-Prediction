"""
Module to fetch reference air quality data from Bangladesh Department of Environment (DoE)
Website: http://180.211.164.219:85/
"""
import httpx
import json
import re
from typing import Dict, Optional, List
from datetime import datetime
from bs4 import BeautifulSoup


class DoEReferenceData:
    """Fetch and parse reference AQI data from Bangladesh DoE"""
    
    BASE_URL = "http://180.211.164.219:85"
    
    # Location mapping between common names and DoE station names
    LOCATION_MAP = {
        "dhaka": "CAMS-DOE",
        "doe": "CAMS-DOE",
        "buet": "CAMS-BUET",
        "barc": "CAMS-BARC",
        "darussalam": "CAMS-DARUSSALAM",
        "savar": "CAMS-SAVAR",
        "gazipur": "CAMS-GAZIPUR",
        "narayanganj": "CAMS-NARAYANGANJ",
        "narsingdi": "CAMS-NARSINGDI",
        "mymensingh": "CAMS-MYMENSINGH",
        "agrabad": "CAMS-CDA_AGRABAD",
        "chittagong": "CAMS-CDA_AGRABAD",
        "sylhet": "CAMS-SYLHET",
        "cumilla": "CAMS-CUMILLA",
        "rangpur": "CAMS-RANGPUR",
        "tv_center": "CAMS-TV_CENTER",
        "rajshahi": "CAMS-RAJSHAHI",
        "barishal": "CAMS-BARISHAL",
        "khulna": "CAMS-KHULNA"
    }
    
    async def fetch_station_data(self, station_name: str) -> Optional[Dict]:
        """
        Fetch real-time data for a specific station
        
        Args:
            station_name: Name of the DoE station (e.g., "CAMS-DOE", "CAMS-CDA_AGRABAD")
            
        Returns:
            Dictionary containing PM2.5, PM10, NO2, AQI, and other pollutant data
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First get the main page to find station links
                response = await client.get(self.BASE_URL)
                if response.status_code != 200:
                    return None
                
                # Parse HTML to extract data
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all station data
                # The data is typically in JavaScript or embedded in HTML
                # We'll look for specific patterns
                
                # Try to find JSON data embedded in page
                scripts = soup.find_all('script')
                station_data = None
                
                for script in scripts:
                    if script.string and station_name in script.string:
                        # Extract data from JavaScript
                        text = script.string
                        # Look for patterns like PM2.5: 123, PM10: 456, etc.
                        station_data = self._extract_pollutant_data(text, station_name)
                        if station_data:
                            break
                
                if not station_data:
                    # Try alternative method: look in the HTML directly
                    station_data = self._extract_from_html(soup, station_name)
                
                return station_data
                
        except Exception as e:
            print(f"Error fetching DoE data: {e}")
            return None
    
    def _extract_pollutant_data(self, text: str, station_name: str) -> Optional[Dict]:
        """Extract pollutant data from JavaScript or text"""
        try:
            data = {}
            
            # Common patterns to search for
            patterns = {
                'pm25': r'PM2\.5["\s:]+(\d+\.?\d*)',
                'pm10': r'PM10["\s:]+(\d+\.?\d*)',
                'no2': r'NO2["\s:]+(\d+\.?\d*)',
                'nox': r'NOx["\s:]+(\d+\.?\d*)',
                'so2': r'SO2["\s:]+(\d+\.?\d*)',
                'co': r'CO["\s:]+(\d+\.?\d*)',
                'o3': r'O3["\s:]+(\d+\.?\d*)',
                'aqi': r'AQI["\s:]+(\d+\.?\d*)'
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data[key] = float(match.group(1))
            
            if data:
                data['station'] = station_name
                data['timestamp'] = datetime.utcnow().isoformat()
                data['source'] = 'DoE Bangladesh'
                return data
            
            return None
            
        except Exception as e:
            print(f"Error extracting data: {e}")
            return None
    
    def _extract_from_html(self, soup: BeautifulSoup, station_name: str) -> Optional[Dict]:
        """Extract data directly from HTML elements"""
        try:
            # This method depends on the actual HTML structure
            # You may need to inspect the page and adjust selectors
            
            # Look for divs or tables containing station data
            station_elements = soup.find_all(['div', 'td', 'span'], text=re.compile(station_name, re.I))
            
            data = {
                'station': station_name,
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'DoE Bangladesh'
            }
            
            for elem in station_elements:
                # Look for nearby elements with pollutant values
                parent = elem.parent
                if parent:
                    text = parent.get_text()
                    # Try to extract numeric values
                    extracted = self._extract_pollutant_data(text, station_name)
                    if extracted:
                        data.update(extracted)
            
            return data if len(data) > 3 else None
            
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            return None
    
    async def get_location_data(self, location: str) -> Optional[Dict]:
        """
        Get reference data for a location (user-friendly wrapper)
        
        Args:
            location: User-friendly location name (e.g., "dhaka", "chittagong", "agrabad")
            
        Returns:
            Dictionary with pollutant concentrations
        """
        location_lower = location.lower().strip()
        station_name = self.LOCATION_MAP.get(location_lower, location)
        
        return await self.fetch_station_data(station_name)
    
    async def get_all_stations(self) -> List[Dict]:
        """Fetch data for all available stations"""
        results = []
        for location, station in self.LOCATION_MAP.items():
            data = await self.fetch_station_data(station)
            if data:
                results.append(data)
        return results


# Alternative API-based approach if DoE has an API endpoint
class DoEAPIClient:
    """Direct API client if DoE provides JSON endpoints"""
    
    BASE_URL = "http://180.211.164.219:85"
    
    async def fetch_station_json(self, station_id: str) -> Optional[Dict]:
        """
        Try to fetch JSON data directly from API endpoints
        
        Common API patterns to try:
        - /api/station/{station_id}
        - /data/{station_id}.json
        - /current/{station_id}
        """
        endpoints = [
            f"{self.BASE_URL}/api/station/{station_id}",
            f"{self.BASE_URL}/data/{station_id}.json",
            f"{self.BASE_URL}/current/{station_id}",
            f"{self.BASE_URL}/api/current?station={station_id}"
        ]
        
        async with httpx.AsyncClient(timeout=30) as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            return data
                        except:
                            continue
                except:
                    continue
        
        return None


async def get_reference_data(location: str) -> Optional[Dict]:
    """
    Main function to get reference data from DoE
    Tries multiple methods to fetch data
    """
    # Try API first
    api_client = DoEAPIClient()
    data = await api_client.fetch_station_json(location)
    
    if data:
        return data
    
    # Fall back to HTML scraping
    doe = DoEReferenceData()
    data = await doe.get_location_data(location)
    
    return data


# Mock data for testing (when DoE site is unavailable)
MOCK_REFERENCE_DATA = {
    "dhaka": {"pm25": 125.5, "pm10": 185.2, "no2": 65.3, "aqi": 245},
    "agrabad": {"pm25": 98.3, "pm10": 152.6, "no2": 48.7, "aqi": 185},
    "chittagong": {"pm25": 98.3, "pm10": 152.6, "no2": 48.7, "aqi": 185},
    "savar": {"pm25": 110.2, "pm10": 165.8, "no2": 52.1, "aqi": 210},
    "sylhet": {"pm25": 72.5, "pm10": 108.3, "no2": 38.5, "aqi": 155}
}


async def get_reference_data_with_fallback(location: str) -> Dict:
    """
    Get reference data with fallback to mock data if DoE site is unavailable
    """
    data = await get_reference_data(location)
    
    if not data:
        print(f"Warning: Could not fetch live data, using mock data for {location}")
        location_lower = location.lower().strip()
        
        # Use mock data
        if location_lower in MOCK_REFERENCE_DATA:
            mock = MOCK_REFERENCE_DATA[location_lower]
            return {
                **mock,
                'station': location,
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'Mock Data (DoE unavailable)',
                'is_mock': True
            }
    
    return data
