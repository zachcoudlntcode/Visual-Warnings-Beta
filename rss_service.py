import re
import logging
import requests
import json
import os
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from warning_service import WarningService

class RSSService:
    """Service to monitor NWS RSS feeds for new weather alerts"""
    
    # Base URL for NWS alerts RSS feeds
    RSS_BASE_URL = "https://alerts.weather.gov/cap"
    
    def __init__(self, data_dir: str = "data", custom_feed_url: str = None):
        """
        Initialize the RSS service
        
        Args:
            data_dir: Directory to store processed alert IDs
            custom_feed_url: Custom RSS feed URL to monitor
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        self.processed_file = os.path.join(data_dir, "processed_alerts.json")
        
        # Store custom feed URL if provided
        self.custom_feed_url = custom_feed_url
        
        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # Load previously processed alerts
        self.processed_alerts = self._load_processed_alerts()
        
        # Initialize warning service for fetching full alert details
        self.warning_service = WarningService()
    
    def get_new_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetch new alerts from the monitored RSS feed
        
        Returns:
            List of new alerts that haven't been processed yet
        """
        all_new_alerts = []
        
        # If we have a custom feed URL, only check that
        if self.custom_feed_url:
            self.logger.info(f"Checking alerts from custom URL: {self.custom_feed_url}")
            try:
                # Use the alerts API directly instead of RSS if possible
                if "api.weather.gov/alerts" in self.custom_feed_url:
                    # If it's an atom feed, convert to JSON endpoint
                    json_url = self.custom_feed_url.replace(".atom", "")
                    self.logger.info(f"Using JSON API endpoint: {json_url}")
                    new_alerts = self._process_json_api(json_url)
                else:
                    # Fallback to RSS feed parsing
                    new_alerts = self._process_rss_feed(self.custom_feed_url)
                
                all_new_alerts.extend(new_alerts)
                self.logger.info(f"Found {len(new_alerts)} new alerts from custom feed")
            except Exception as e:
                self.logger.error(f"Error fetching alerts from custom feed: {e}")
        
        # Save the updated processed alerts
        self._save_processed_alerts()
        
        return all_new_alerts
    
    def _process_json_api(self, api_url: str) -> List[Dict[str, Any]]:
        """
        Process alerts directly from the NWS JSON API
        
        Args:
            api_url: URL of the NWS alerts API
            
        Returns:
            List of new alerts from this API
        """
        new_alerts = []
        
        # Make the API request with proper headers
        headers = {
            "Accept": "application/geo+json",
            "User-Agent": "VisualWarningsBeta/1.0 (zachmiller3292@gmail.com)"
        }
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Process the alerts
        self.logger.info(f"API returned {len(data.get('features', []))} total alerts")
        
        # Extract warnings using the warning service
        warnings = self.warning_service._extract_warnings(data)
        
        # Filter for alerts we haven't processed yet
        for warning in warnings:
            alert_id = warning.get('id')
            if alert_id and alert_id not in self.processed_alerts:
                self.logger.info(f"Found new alert: {alert_id} - {warning.get('event', 'Unknown')}")
                new_alerts.append(warning)
                
                # Mark as processed
                self.processed_alerts[alert_id] = {
                    'processed_at': datetime.now().isoformat(),
                    'event': warning.get('event', 'Unknown')
                }
        
        return new_alerts
    
    def _process_rss_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """
        Process a single RSS feed and extract new alerts
        
        Args:
            feed_url: URL of the RSS feed to process
            
        Returns:
            List of new alerts from this feed
        """
        new_alerts = []
        
        # Request the RSS feed
        response = requests.get(feed_url)
        response.raise_for_status()
        
        # Debug: Log the first part of the response to see what we're dealing with
        self.logger.debug(f"RSS Feed Response: {response.content[:500]}...")
        
        # Parse the RSS feed using ElementTree instead of feedparser
        try:
            # Use ElementTree to parse XML
            root = ET.fromstring(response.content)
            
            # Debug: Log the root tag and available tags
            self.logger.debug(f"XML Root tag: {root.tag}")
            self.logger.debug(f"Available child tags: {[child.tag for child in root]}")
            
            # RSS feeds have different namespaces, so we need to handle them
            # Get namespaces from the root element
            namespaces = {}
            for prefix, uri in root.attrib.items():
                if prefix.startswith('xmlns:'):
                    ns_prefix = prefix.split(':')[1]
                    namespaces[ns_prefix] = uri
            
            # Add common namespaces if not found
            if 'atom' not in namespaces:
                namespaces['atom'] = 'http://www.w3.org/2005/Atom'
            if 'cap' not in namespaces:
                namespaces['cap'] = 'urn:oasis:names:tc:emergency:cap:1.1'
            
            self.logger.debug(f"Detected namespaces: {namespaces}")
            
            # Try multiple methods to find entries
            entries = []
            
            # Method 1: Search with namespaces
            for ns_prefix, uri in namespaces.items():
                ns_dict = {ns_prefix: uri}
                found_entries = root.findall(f'.//{{{uri}}}entry')
                if found_entries:
                    entries.extend(found_entries)
                    self.logger.debug(f"Found {len(found_entries)} entries using namespace {ns_prefix}")
            
            # Method 2: Search with full tag
            if not entries:
                # Try to find entries by full tag name
                for tag in ['{http://www.w3.org/2005/Atom}entry']:
                    found_entries = root.findall(f'.//{tag}')
                    if found_entries:
                        entries.extend(found_entries)
                        self.logger.debug(f"Found {len(found_entries)} entries using full tag {tag}")
            
            # Method 3: Search without namespace
            if not entries:
                # Try without namespace
                found_entries = root.findall('.//entry')
                if found_entries:
                    entries.extend(found_entries)
                    self.logger.debug(f"Found {len(found_entries)} entries without namespace")
            
            self.logger.info(f"Found a total of {len(entries)} entries in the feed")
            
            # Process each entry
            for entry in entries:
                # Try to extract ID from different possible elements
                alert_id = None
                
                # Try with namespace
                for ns, uri in namespaces.items():
                    id_elem = entry.find(f'{{{uri}}}id')
                    if id_elem is not None and id_elem.text:
                        alert_id = id_elem.text.split('/')[-1]
                        break
                
                # Try without namespace
                if not alert_id:
                    id_elem = entry.find('id')
                    if id_elem is not None and id_elem.text:
                        alert_id = id_elem.text.split('/')[-1]
                
                # If we still can't find an ID, check for link elements
                if not alert_id:
                    for link_elem in entry.findall('.//{http://www.w3.org/2005/Atom}link') or entry.findall('.//link'):
                        if link_elem.get('rel') == 'alternate' and link_elem.get('href'):
                            alert_id = link_elem.get('href').split('/')[-1]
                            break
                
                # Skip if we couldn't find an ID
                if not alert_id:
                    self.logger.warning("Could not extract alert ID from entry")
                    continue
                
                self.logger.debug(f"Processing alert ID: {alert_id}")
                
                # Check if we've already processed this alert
                if alert_id in self.processed_alerts:
                    self.logger.debug(f"Alert {alert_id} already processed, skipping")
                    continue
                
                # Get the full alert details directly by ID
                try:
                    alert_data = self.warning_service.get_warning_by_id(alert_id)
                    if alert_data:
                        # Extract the main feature/alert
                        if 'features' in alert_data and alert_data['features']:
                            feature = alert_data['features'][0]
                            # Process the warning
                            warning = self.warning_service._extract_warnings({'features': [feature]})[0]
                            new_alerts.append(warning)
                            # Mark as processed
                            self.processed_alerts[alert_id] = {
                                'processed_at': datetime.now().isoformat(),
                                'event': warning.get('event', 'Unknown')
                            }
                            self.logger.info(f"Successfully processed alert: {alert_id} - {warning.get('event', 'Unknown')}")
                except Exception as e:
                    self.logger.error(f"Error processing alert {alert_id}: {e}")
        
        except ET.ParseError as e:
            self.logger.error(f"Error parsing RSS feed: {e}")
        
        return new_alerts
    
    def _extract_coordinates(self, text: str) -> Optional[Tuple[float, float]]:
        """Extract latitude and longitude from a text description"""
        # Look for patterns like "33.92,-87.3" in the text
        coord_pattern = r'(\d+\.\d+),\s*(-?\d+\.\d+)'
        match = re.search(coord_pattern, text)
        
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return (lat, lon)
            except ValueError:
                return None
        
        return None
    
    def _load_processed_alerts(self) -> Dict[str, Dict[str, str]]:
        """Load the list of previously processed alerts"""
        if os.path.exists(self.processed_file):
            try:
                with open(self.processed_file, 'r') as f:
                    data = json.load(f)
                
                # Clean up old alerts (older than 24 hours)
                now = datetime.now()
                cleaned_data = {}
                for alert_id, info in data.items():
                    try:
                        processed_time = datetime.fromisoformat(info['processed_at'])
                        if now - processed_time < timedelta(hours=24):
                            cleaned_data[alert_id] = info
                    except Exception:
                        # Keep alert if we can't parse the time
                        cleaned_data[alert_id] = info
                
                return cleaned_data
            except Exception as e:
                self.logger.error(f"Error loading processed alerts: {e}")
                return {}
        else:
            return {}
    
    def _save_processed_alerts(self):
        """Save the list of processed alerts"""
        try:
            with open(self.processed_file, 'w') as f:
                json.dump(self.processed_alerts, f)
        except Exception as e:
            self.logger.error(f"Error saving processed alerts: {e}")
