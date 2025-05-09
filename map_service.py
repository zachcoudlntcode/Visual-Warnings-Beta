import folium
import io
from typing import List, Dict, Any, Tuple
import logging
import time
import os
import pathlib
import requests
import zipfile
import tempfile
import geopandas as gpd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re  # Added for hazard extraction
from datetime import datetime  # Added for time conversion
import pytz  # Added for time conversion


class MapService:
    """Service to generate maps with warning polygons"""

    def __init__(self, output_dir: str = "output"):
        self.logger = logging.getLogger(__name__)
        self.output_dir = output_dir
        self.shapefile_dir = os.path.join('data', 'shapefiles')
        self.county_shapefile_path = os.path.join(
            self.shapefile_dir, 'counties.geojson')
        # Using your actual logo file
        self.logo_path = os.path.join('assets', 'WKYW Logo (White Text).png')

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create shapefile directory if it doesn't exist
        if not os.path.exists(self.shapefile_dir):
            os.makedirs(self.shapefile_dir)

        # Create assets directory if it doesn't exist
        assets_dir = os.path.dirname(self.logo_path)
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)

    def download_county_shapefile(self) -> bool:
        """
        Download county shapefile from Census Bureau if not already present

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if we already have the processed geojson file
        if os.path.exists(self.county_shapefile_path):
            self.logger.info(
                f"County shapefile already exists at {self.county_shapefile_path}")
            return True

        try:
            # URL to the Census Bureau county shapefile (using 2021 data, 500k resolution for a good balance)
            shapefile_url = "https://www2.census.gov/geo/tiger/GENZ2021/shp/cb_2021_us_county_500k.zip"

            self.logger.info(
                f"Downloading county shapefile from {shapefile_url}")

            # Create a temporary directory to store the downloaded zip file
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "counties.zip")

                # Download the shapefile
                response = requests.get(shapefile_url, stream=True)
                response.raise_for_status()

                # Save the zip file
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                self.logger.info(f"Downloaded shapefile to {zip_path}")

                # Extract the zip file
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)

                self.logger.info(f"Extracted shapefile to {temp_dir}")

                # Find the .shp file
                shapefile_path = None
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.shp'):
                            shapefile_path = os.path.join(root, file)
                            break

                if not shapefile_path:
                    self.logger.error(
                        "No .shp file found in downloaded archive")
                    return False

                # Read the shapefile into a GeoDataFrame
                gdf = gpd.read_file(shapefile_path)

                # Simplify the geometries slightly to reduce file size
                gdf['geometry'] = gdf['geometry'].simplify(0.01)

                # Save as GeoJSON for easier use with Folium
                gdf.to_file(self.county_shapefile_path, driver='GeoJSON')

                self.logger.info(
                    f"Converted shapefile to GeoJSON: {self.county_shapefile_path}")

                return True

        except Exception as e:
            self.logger.error(
                f"Error downloading or processing county shapefile: {e}")
            return False

    def get_nearby_counties(self, polygon: List[List[float]], buffer_degrees: float = 0.5) -> gpd.GeoDataFrame:
        """
        Get counties that are nearby the warning polygon

        Args:
            polygon: Warning polygon coordinates in [lon, lat] format
            buffer_degrees: Buffer around the polygon in degrees

        Returns:
            GeoDataFrame of nearby counties
        """
        import shapely.geometry as sg

        # Ensure county shapefile is downloaded
        if not os.path.exists(self.county_shapefile_path):
            if not self.download_county_shapefile():
                self.logger.warning(
                    "Failed to download county shapefile, nearby counties will not be shown")
                return gpd.GeoDataFrame()

        try:
            # Load the county shapefile
            counties = gpd.read_file(self.county_shapefile_path)

            # Create a shapely polygon from the warning polygon coordinates
            # Warning polygons are in [lon, lat] format
            warning_poly = sg.Polygon([(p[0], p[1]) for p in polygon])

            # Create a buffer around the warning polygon
            buffered_poly = warning_poly.buffer(buffer_degrees)

            # Find counties that intersect with the buffered polygon
            nearby_counties = counties[counties.intersects(buffered_poly)]

            self.logger.info(
                f"Found {len(nearby_counties)} counties near the warning polygon")

            return nearby_counties

        except Exception as e:
            self.logger.error(f"Error getting nearby counties: {e}")
            return gpd.GeoDataFrame()

    def create_warning_map(self, warning: Dict[str, Any]) -> str:
        """
        Create a map with the warning polygon

        Args:
            warning: Warning data including polygon coordinates

        Returns:
            Path to the generated HTML file
        """
        try:
            if 'polygon' not in warning or not warning['polygon']:
                self.logger.error(
                    f"No polygon data found for warning: {warning.get('id')}")
                return ""

            # Calculate center based on polygon
            center_lat, center_lon = self._calculate_polygon_center(
                warning['polygon'])

            # Create a map centered on the warning area with no default tiles
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=6,
                tiles=None  # Start with no tiles, we'll add them manually
            )

            # Add custom Jawg map tile layer with the custom style ID provided
            jawg_custom = folium.TileLayer(
                tiles='https://tile.jawg.io/850101de-05d1-4fde-8d58-507e955b20fd/{z}/{x}/{y}{r}.png?access-token=4iSiQAQoAktA9VHz0fuoPkFcJ2G87mUq8CUx5aPO1BJ6FzxWkrizEuhXcXAykvao',
                attr='<a href="https://www.jawg.io?utm_medium=map&utm_source=attribution" target="_blank">&copy; Jawg</a> - <a href="https://www.openstreetmap.org?utm_medium=map-attribution&utm_source=jawg" target="_blank">&copy; OpenStreetMap</a>&nbsp;contributors',
                name='Jawg Custom',
                overlay=False,
                control=True
            ).add_to(m)

            # Set the custom Jawg map as the default visible tile layer
            jawg_custom.options.update({'opacity': 1.0})

            # Format polygon for folium (it expects [lat, lon] but we may have [lon, lat])
            formatted_polygon = []
            for point in warning['polygon']:
                # Check if point is in [lon, lat] format and convert to [lat, lon]
                if len(point) >= 2:
                    formatted_polygon.append([point[1], point[0]])

            # Calculate bounds to fit the polygon
            if formatted_polygon:
                min_lat = min(point[0] for point in formatted_polygon)
                max_lat = max(point[0] for point in formatted_polygon)
                min_lon = min(point[1] for point in formatted_polygon)
                max_lon = max(point[1] for point in formatted_polygon)

                # Add padding to ensure the polygon is fully visible
                padding = 0.1  # degrees (adjust as needed)
                bounds = [
                    [min_lat - padding, min_lon - padding],
                    [max_lat + padding, max_lon + padding]
                ]

                # Fit map to the bounds
                m.fit_bounds(bounds)

            # Get nearby counties to display on the map
            nearby_counties_gdf = self.get_nearby_counties(
                warning['polygon'])  # Renamed to avoid conflict

            # Add county boundaries to the map if available
            if not nearby_counties_gdf.empty:
                folium.GeoJson(
                    nearby_counties_gdf,  # Use renamed variable
                    name='County Boundaries',
                    style_function=lambda x: {
                        'fillColor': 'transparent',
                        'color': '#FFFFFF',
                        'weight': 1,
                        'opacity': 0.7
                    },
                    tooltip=folium.features.GeoJsonTooltip(
                        fields=['NAME'],
                        aliases=['County:'],
                        style=(
                            "background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
                    )
                ).add_to(m)

            # Add polygon to map with color based on warning event type
            event_type = warning.get(
                'event', 'Unknown Warning')  # Default text
            color = self._get_warning_color(event_type)

            folium.Polygon(
                locations=formatted_polygon,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.4,
                popup=folium.Popup(
                    f"<b>{event_type}</b><br>{warning.get('headline', '')}", max_width=300)
            ).add_to(m)

            # Add a layer control to allow toggling between map providers
            folium.LayerControl().add_to(m)

            # Extract information for the overlay
            affected_areas = self._extract_affected_areas(warning)
            hazards = self._extract_hazards_from_description(
                warning.get('description', ''))

            # Convert and format expiration time
            expires_str = warning.get('expires', 'Not available')
            formatted_expires_time = 'Not available'
            if expires_str and expires_str != 'Not available':
                try:
                    # Parse the ISO format string
                    # Example: 2024-07-21T19:00:00-05:00 or 2024-07-21T19:00:00Z
                    if expires_str.endswith('Z'):
                        dt_utc = datetime.strptime(
                            expires_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
                    else:
                        # Handle timezone offset like -05:00
                        if ':' in expires_str[-6:]:
                            dt_aware = datetime.fromisoformat(expires_str)
                        else:  # if no colon in offset, add it for fromisoformat
                            dt_aware = datetime.fromisoformat(
                                expires_str[:-2] + ':' + expires_str[-2:])
                        dt_utc = dt_aware.astimezone(pytz.utc)

                    # Convert to CDT
                    cdt_tz = pytz.timezone('America/Chicago')
                    dt_cdt = dt_utc.astimezone(cdt_tz)
                    formatted_expires_time = dt_cdt.strftime(
                        "%b %d, %Y, %I:%M %p %Z")
                except ValueError as e:
                    self.logger.warning(
                        f"Could not parse expires time '{expires_str}': {e}")
                    # Fallback to original string if parsing fails
                    formatted_expires_time = expires_str

            # Format the main title
            main_title_text = f"A {event_type} has been issued"

            # Create HTML for the title banner - updated with new layout
            title_html = f'''
                <div style="position: fixed; 
                            top: 0; 
                            left: 0; 
                            width: 100%; 
                            background-color: rgb(0, 0, 0); /* Changed to solid black */
                            color: white; 
                            padding: 10px 15px; 
                            font-family: 'Roboto', 'Segoe UI', Helvetica, Arial, sans-serif; 
                            z-index: 9999;
                            box-sizing: border-box;
                            border-bottom: 3px solid {color};
                            text-align: center; /* Center the main title */
                            ">
                    <h2 style="margin: 0 0 10px 0; font-size: 24px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">{main_title_text}</h2>
                    <div style="display: flex; justify-content: space-around; align-items: flex-start; width: 100%; margin-top: 10px;">
                        <div style="background-color: rgba(20, 20, 20, 0.8); padding: 8px 12px; border-radius: 5px; margin: 0 5px; flex: 1; min-width: 0;"> <!-- Added flex: 1 and min-width: 0 -->
                            <h3 style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; border-bottom: 1px solid {color}; padding-bottom: 3px;">EXPIRES</h3>
                            <p style="margin: 0; font-size: 13px; line-height: 1.4;">{formatted_expires_time}</p>
                        </div>
                        <div style="background-color: rgba(20, 20, 20, 0.8); padding: 8px 12px; border-radius: 5px; margin: 0 5px; flex: 1; min-width: 0;"> <!-- Added flex: 1 and min-width: 0 -->
                            <h3 style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; border-bottom: 1px solid {color}; padding-bottom: 3px;">AFFECTED COUNTIES</h3>
                            <p style="margin: 0; font-size: 13px; line-height: 1.4; word-wrap: break-word; overflow-wrap: break-word;">{affected_areas}</p> <!-- Added word-wrap -->
                        </div>
                        <div style="background-color: rgba(20, 20, 20, 0.8); padding: 8px 12px; border-radius: 5px; margin: 0 5px; flex: 1; min-width: 0;"> <!-- Added flex: 1 and min-width: 0 -->
                            <h3 style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600; text-transform: uppercase; border-bottom: 1px solid {color}; padding-bottom: 3px;">HAZARDS</h3>
                            <p style="margin: 0; font-size: 13px; line-height: 1.4; word-wrap: break-word; overflow-wrap: break-word;">{hazards}</p> <!-- Added word-wrap -->
                        </div>
                    </div>
                </div>
            '''

            # Add the title HTML to the map
            m.get_root().html.add_child(folium.Element(title_html))

            # Add logo to bottom left corner if it exists
            if os.path.exists(self.logo_path):
                logo_html = f'''
                    <div style="position: fixed; 
                                bottom: -60px; 
                                left: -40px; 
                                z-index: 9999; 
                                background-color: transparent; 
                                padding: 0;">
                        <img src="data:image/png;base64,{self._get_image_base64(self.logo_path)}" 
                             style="height: 360px; width: auto;" alt="Logo" />
                    </div>
                '''
                m.get_root().html.add_child(folium.Element(logo_html))
            else:
                self.logger.warning(f"Logo file not found at {self.logo_path}")

            # Add some JavaScript to indicate when the map is fully loaded (for Selenium)
            load_complete_script = '''
                <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // Wait for tiles to load
                    setTimeout(function() {
                        // Create an element to signal load completion
                        var loadComplete = document.createElement('div');
                        loadComplete.id = 'map-load-complete';
                        loadComplete.style.display = 'none';
                        document.body.appendChild(loadComplete);
                    }, 3000);  // Adjust timeout as needed for map loading
                });
                </script>
            '''
            m.get_root().html.add_child(folium.Element(load_complete_script))

            # Generate metadata for the map
            metadata_html = f'''
                <div style="display:none" id="warning-metadata">
                    <span id="warning-id">{warning.get('id', 'unknown')}</span>
                    <span id="warning-event">{event_type}</span>
                    <span id="warning-headline">{warning.get('headline', '')}</span>
                    <span id="warning-effective">{warning.get('effective', '')}</span>
                    <span id="warning-expires">{warning.get('expires', '')}</span>
                </div>
            '''
            m.get_root().html.add_child(folium.Element(metadata_html))

            # Save the map as HTML
            warning_id = warning.get('id', 'unknown')
            html_path = os.path.join(
                self.output_dir, f"warning_{warning_id}.html")
            m.save(html_path)

            # Return the path to the HTML file
            self.logger.info(f"Created warning map HTML: {html_path}")

            # Convert HTML to image
            png_path = self.html_to_image(html_path)
            if png_path:
                # Clean up the HTML file
                try:
                    os.remove(html_path)
                    self.logger.info(f"Cleaned up HTML file: {html_path}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to remove HTML file {html_path}: {e}")
                return png_path
            else:
                # Fall back to HTML if image conversion fails
                return html_path

        except Exception as e:
            self.logger.error(f"Error creating warning map: {e}")
            return ""

    def html_to_image(self, html_path: str) -> str:
        """
        Convert an HTML file to a PNG image using Selenium

        Args:
            html_path: Path to the HTML file

        Returns:
            Path to the generated PNG file, or empty string if failed
        """
        try:
            abs_path = os.path.abspath(html_path)
            file_url = pathlib.Path(abs_path).as_uri()

            # Generate PNG filename from HTML path
            png_path = os.path.splitext(html_path)[0] + ".png"

            self.logger.info(
                f"Converting HTML to image: {html_path} → {png_path}")

            # Set up Chrome options with higher resolution for social media
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            # Increase resolution to 1920x1080 for higher quality social media images
            chrome_options.add_argument("--window-size=720,900")

            # Initialize Chrome driver based on platform
            import platform
            system = platform.system()

            try:
                if system == 'Linux':
                    # On Debian/Linux systems, use chromium-browser directly
                    self.logger.info("Using Chromium for Debian/Linux")
                    driver = webdriver.Chrome(options=chrome_options)
                elif system == 'Darwin' and platform.machine() == 'arm64':
                    # On Mac ARM64, use the default Chrome driver directly
                    driver = webdriver.Chrome(options=chrome_options)
                else:
                    # On other platforms, try to use webdriver_manager
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(
                        service=service, options=chrome_options)
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize primary Chrome driver: {e}")
                self.logger.info(
                    "Falling back to default Chrome/Chromium driver")
                # Fall back to default Chrome/Chromium driver path
                driver = webdriver.Chrome(options=chrome_options)

            try:
                # Navigate to the HTML file
                driver.get(file_url)

                # Wait for map to load
                wait_time = 10
                self.logger.info(
                    f"Waiting up to {wait_time} seconds for map to load...")

                # Wait for the map to load - increase to ensure all map tiles load at high resolution
                try:
                    # Give the page time to load (for the map tiles and JavaScript)
                    # Increased from 5 to 7 seconds for better loading
                    time.sleep(7)
                except Exception as wait_ex:
                    self.logger.warning(
                        f"Wait error (continuing anyway): {wait_ex}")

                # Take screenshot and save to file with high quality
                driver.save_screenshot(png_path)
                self.logger.info(
                    f"High-resolution screenshot saved to: {png_path}")

                return png_path

            finally:
                # Always close the driver
                driver.quit()

        except WebDriverException as e:
            self.logger.error(f"Selenium WebDriverException: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Error converting HTML to image: {e}")
            return ""

    def _calculate_polygon_center(self, polygon: List[List[float]]) -> Tuple[float, float]:
        """Calculate the center point of a polygon"""
        if not polygon:
            return 0, 0

        # For GeoJSON polygons, coordinates are [lon, lat]
        lats = [point[1] for point in polygon if len(point) >= 2]
        lons = [point[0] for point in polygon if len(point) >= 2]

        if not lats or not lons:
            return 0, 0

        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

        return center_lat, center_lon

    def _get_warning_color(self, event_type: str) -> str:
        """
        Get appropriate color based on warning event type using the F5 Data color scheme
        https://www.f5data.com/colors/colors.htm
        """
        # Standard NWS warning colors based on F5 Data's color scheme
        warning_colors = {
            # Tornado Warnings
            "Tornado Warning": "#FF0000",  # Red
            "Tornado Emergency": "#FF00FF",  # Magenta

            # Severe Thunderstorm Warnings
            "Severe Thunderstorm Warning": "#FFFF00",  # Yellow

            # Flash Flood Warnings
            "Flash Flood Warning": "#00FF00",  # Green
            "Flash Flood Emergency": "#00FFFF",  # Cyan

            # Other Flood Warnings
            "Flood Warning": "#00A000",  # Dark Green
            "Areal Flood Warning": "#00A0A0",  # Dark Cyan
            "Flood Advisory": "#00A000",  # Dark Green

            # Winter Warnings
            "Winter Storm Warning": "#FF69B4",  # Hot Pink
            "Ice Storm Warning": "#FF69B4",  # Hot Pink
            "Blizzard Warning": "#FF69B4",  # Hot Pink
            "Lake Effect Snow Warning": "#FF69B4",  # Hot Pink

            # Winter Advisories
            "Winter Weather Advisory": "#FFC0CB",  # Pink
            "Freezing Rain Advisory": "#FFC0CB",  # Pink

            # Wind Warnings and Advisories
            "High Wind Warning": "#A52A2A",  # Brown
            "Wind Advisory": "#DEB887",  # Burlywood

            # Marine and Coastal Warnings
            "Hurricane Warning": "#FD6347",  # Tomato Red
            "Tropical Storm Warning": "#FD6347",  # Tomato Red
            "Storm Surge Warning": "#FD6347",  # Tomato Red
            "Coastal Flood Warning": "#6495ED",  # Cornflower Blue

            # Fire Weather Warnings
            "Red Flag Warning": "#FF4500",  # Orange Red
            "Fire Weather Warning": "#FF4500",  # Orange Red

            # Heat and Cold Warnings
            "Excessive Heat Warning": "#8B0000",  # Dark Red
            "Heat Advisory": "#CD5C5C",  # Indian Red
            "Wind Chill Warning": "#9400D3",  # Dark Violet
            "Extreme Cold Warning": "#9400D3",  # Dark Violet

            # Air Quality
            "Air Quality Alert": "#808080",  # Gray

            # Other Warnings
            "Dust Storm Warning": "#D2691E",  # Chocolate
            "Dense Fog Advisory": "#F0E68C",  # Khaki
        }

        # Return the color for the event type, or use severity-based fallback
        color = warning_colors.get(event_type)
        if color:
            return color

        # Fallback based on portions of the name
        for key_part in ["Tornado", "Severe", "Flash Flood", "Flood", "Winter", "Wind",
                         "Hurricane", "Tropical", "Heat", "Cold", "Fire"]:
            if key_part.lower() in event_type.lower():
                for warning_type, warning_color in warning_colors.items():
                    if key_part.lower() in warning_type.lower():
                        return warning_color

        # Default fallback based on severity terms in the event name
        if "warning" in event_type.lower():
            return "#FF0000"  # Red for warnings
        elif "watch" in event_type.lower():
            return "#FFA500"  # Orange for watches
        elif "advisory" in event_type.lower():
            return "#FFFF00"  # Yellow for advisories

        # Final default
        return "#808080"  # Gray for unknown

    def _extract_affected_areas(self, warning: Dict[str, Any]) -> str:
        """
        Extract affected areas (counties) from warning data

        Args:
            warning: Warning data

        Returns:
            String with affected areas
        """
        # Try to find affected areas in different parts of the warning
        affected_areas = ""

        # Check if there's a specific field for affected areas
        if 'areaDesc' in warning:
            return warning['areaDesc']

        # Try to extract from headline
        headline = warning.get('headline', '')
        if 'county' in headline.lower() or 'counties' in headline.lower():
            # Extract county information from headline
            counties_start = headline.lower().find('county')
            if counties_start > 0:
                # Look for the preceding text that likely contains county names
                possible_counties = headline[:counties_start].strip()
                return possible_counties

        # Try to extract from description
        description = warning.get('description', '')
        if description:
            # Look for patterns like "This includes the counties of..."
            includes_idx = description.lower().find('includes the count')
            if includes_idx > 0:
                # Extract the text after this phrase until the next period
                start_idx = includes_idx + 18  # Length of "includes the count"
                end_idx = description.find('.', start_idx)
                if end_idx > start_idx:
                    return description[start_idx:end_idx].strip()

        # If we can't find specific county information, return a generic message
        return "See warning details for specific locations"

    def _extract_hazards_from_description(self, description: str) -> str:
        """
        Extracts hazard information from the warning description.
        NWS descriptions often have a "HAZARD..." section.
        """
        if not description:
            return "Not specified"

        # Try to find "HAZARD..." section
        hazard_match = re.search(
            r"HAZARD\\.\\.\\.([^\\n\\n]+)", description, re.IGNORECASE)
        if hazard_match:
            hazards = hazard_match.group(1).strip()
            # Clean up common extra phrases
            hazards = hazards.replace("...", "").strip()
            # Limit length if necessary
            return hazards[:250] + "..." if len(hazards) > 250 else hazards

        # Fallback: look for common keywords if specific section not found
        # This can be expanded
        potential_hazards = []
        if "hail" in description.lower():
            potential_hazards.append("Hail")
        if "wind gusts" in description.lower():
            potential_hazards.append("Wind Gusts")
        if "tornado" in description.lower():
            potential_hazards.append("Tornado")
        if "flooding" in description.lower():
            potential_hazards.append("Flooding")

        if potential_hazards:
            return ", ".join(potential_hazards)

        return "See description for details"

    def _get_image_base64(self, image_path: str) -> str:
        """
        Convert an image file to base64 encoding for embedding in HTML

        Args:
            image_path: Path to the image file

        Returns:
            Base64 encoded string representation of the image
        """
        import base64
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(
                    image_file.read()).decode('utf-8')
            return encoded_string
        except Exception as e:
            self.logger.error(f"Error encoding image {image_path}: {e}")
            return ""
