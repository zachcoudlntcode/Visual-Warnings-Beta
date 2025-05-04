import argparse
import logging
import os
import sys
from typing import List, Dict, Any

from warning_service import WarningService
from map_service import MapService

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("visual_warnings.log")
        ]
    )
    return logging.getLogger(__name__)

def process_location(lat: float, lon: float, logger: logging.Logger) -> List[str]:
    """
    Process a location to get warnings and generate maps
    
    Args:
        lat: Latitude of the location
        lon: Longitude of the location
        logger: Logger instance
        
    Returns:
        List of paths to generated images
    """
    warning_service = WarningService()
    map_service = MapService()
    
    logger.info(f"Fetching warnings for location: {lat}, {lon}")
    warnings = warning_service.get_active_warnings(lat, lon)
    
    if not warnings:
        logger.info(f"No active warnings found for location: {lat}, {lon}")
        return []
    
    logger.info(f"Found {len(warnings)} active warnings")
    
    image_paths = []
    for warning in warnings:
        logger.info(f"Processing warning: {warning.get('event')} ({warning.get('id')})")
        
        if 'polygon' in warning and warning['polygon']:
            image_path = map_service.create_warning_map(warning)
            if image_path:
                image_paths.append(image_path)
                logger.info(f"Generated map for warning: {warning.get('id')}")
            else:
                logger.warning(f"Failed to generate map for warning: {warning.get('id')}")
        else:
            logger.warning(f"No polygon data for warning: {warning.get('id')}")
    
    return image_paths

def main():
    """Main function to run the Visual Warnings tool"""
    logger = setup_logging()
    
    parser = argparse.ArgumentParser(description='Generate visual maps of NWS warnings')
    parser.add_argument('--lat', type=float, help='Latitude of location to check')
    parser.add_argument('--lon', type=float, help='Longitude of location to check')
    parser.add_argument('--locations', type=str, help='Path to CSV file with lat,lon pairs')
    parser.add_argument('--output', type=str, default='output', help='Output directory for images')
    
    args = parser.parse_args()
    
    # Process single location if provided
    if args.lat is not None and args.lon is not None:
        image_paths = process_location(args.lat, args.lon, logger)
        
        if image_paths:
            logger.info(f"Generated {len(image_paths)} warning maps: {', '.join(image_paths)}")
        else:
            logger.info("No warning maps were generated")
    
    # Process multiple locations from file
    elif args.locations:
        if not os.path.exists(args.locations):
            logger.error(f"Locations file not found: {args.locations}")
            sys.exit(1)
            
        all_image_paths = []
        with open(args.locations, 'r') as f:
            for line in f:
                try:
                    lat, lon = map(float, line.strip().split(','))
                    image_paths = process_location(lat, lon, logger)
                    all_image_paths.extend(image_paths)
                except Exception as e:
                    logger.error(f"Error processing location {line.strip()}: {e}")
        
        if all_image_paths:
            logger.info(f"Generated {len(all_image_paths)} warning maps in total")
        else:
            logger.info("No warning maps were generated")
    
    else:
        logger.error("Please provide either --lat and --lon or --locations")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
