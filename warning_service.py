import requests
import json
from typing import Dict, List, Any, Optional
import logging

class WarningService:
    """Service to interact with the NWS API and retrieve active warnings"""
    
    BASE_URL = "https://api.weather.gov"
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.headers = {
            "Accept": "application/geo+json",
            "User-Agent": "VisualWarningsBeta/1.0 (zachmiller3292@gmail.com)"
        }
    
    def get_active_warnings(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """
        Get active warnings for a specific location
        
        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            
        Returns:
            List of active warnings with their details
        """
        try:
            # First get the zone for this location
            point_url = f"{self.BASE_URL}/points/{lat},{lon}"
            point_response = requests.get(point_url, headers=self.headers)
            point_response.raise_for_status()
            point_data = point_response.json()
            
            county_zone = point_data.get('properties', {}).get('county')
            if not county_zone:
                self.logger.error(f"Could not find county zone for location: {lat}, {lon}")
                return []
            
            # Extract zone ID from the county_zone URL if it's a full URL
            if county_zone.startswith('http'):
                # Extract just the zone ID (e.g., "KYC107" from "https://api.weather.gov/zones/county/KYC107")
                zone_id = county_zone.split('/')[-1]
            else:
                zone_id = county_zone
            
            # Get active alerts for this zone - correct URL format
            alerts_url = f"{self.BASE_URL}/alerts/active?zone={zone_id}"
            self.logger.info(f"Fetching alerts from: {alerts_url}")
            alerts_response = requests.get(alerts_url, headers=self.headers)
            alerts_response.raise_for_status()
            alerts_data = alerts_response.json()
            
            return self._extract_warnings(alerts_data)
        except requests.RequestException as e:
            self.logger.error(f"Error fetching warnings: {e}")
            return []
    
    def get_warning_by_id(self, warning_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific warning by its ID
        
        Args:
            warning_id: The NWS warning ID
            
        Returns:
            Warning details or None if not found
        """
        try:
            url = f"{self.BASE_URL}/alerts/{warning_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Error fetching warning by ID: {e}")
            return None
    
    def _extract_warnings(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relevant warning data from the API response"""
        warnings = []
        
        for feature in alerts_data.get('features', []):
            props = feature.get('properties', {})
            
            # Only include actual warnings (not watches, advisories, etc.) if needed
            # Uncomment to filter by event type
            # if props.get('messageType') != 'Alert':
            #     continue
            
            warning = {
                'id': props.get('id'),
                'event': props.get('event'),
                'headline': props.get('headline'),
                'description': props.get('description'),
                'instruction': props.get('instruction'),
                'severity': props.get('severity'),
                'certainty': props.get('certainty'), 
                'urgency': props.get('urgency'),
                'effective': props.get('effective'),
                'expires': props.get('expires'),
                'sent': props.get('sent'),
                'areaDesc': props.get('areaDesc', ''),
                # Add NWSheadline for use in the image title
                'NWSheadline': props.get('parameters', {}).get('NWSheadline', [''])[0] if props.get('parameters', {}).get('NWSheadline') else ''
            }
            
            # Extract affected areas from affectedZones if areaDesc is not provided
            if not warning['areaDesc'] and 'affectedZones' in props:
                try:
                    # Fetch county names for each affected zone
                    affected_zones = []
                    for zone_url in props.get('affectedZones', []):
                        zone_response = requests.get(zone_url, headers=self.headers)
                        zone_response.raise_for_status()
                        zone_data = zone_response.json()
                        zone_name = zone_data.get('properties', {}).get('name', '')
                        if zone_name:
                            affected_zones.append(zone_name)
                    
                    if affected_zones:
                        warning['areaDesc'] = ', '.join(affected_zones)
                except Exception as e:
                    self.logger.error(f"Error fetching affected zones: {e}")
            
            # Extract polygon data if available
            if feature.get('geometry') and feature['geometry'].get('type') == 'Polygon':
                warning['polygon'] = feature['geometry'].get('coordinates', [[]])[0]
            else:
                # Sometimes the polygon is in the properties
                polygon_str = props.get('polygon')
                if polygon_str:
                    polygon_points = []
                    for point_str in polygon_str.split(' '):
                        try:
                            lat, lon = map(float, point_str.split(','))
                            polygon_points.append([lon, lat])  # Note: GeoJSON uses [lon, lat] order
                        except ValueError:
                            continue
                    warning['polygon'] = polygon_points
            
            warnings.append(warning)
        
        return warnings
