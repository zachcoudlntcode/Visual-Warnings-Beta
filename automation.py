import argparse
import logging
import os
import sys
import time
import schedule
import requests
import traceback
from typing import List, Optional
from datetime import datetime
from rss_service import RSSService
from map_service import MapService

def setup_logging(log_file: Optional[str] = None):
    """Configure logging"""
    if log_file is None:
        log_file = f"visual_warnings_automation_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    return logging.getLogger(__name__)

def send_image_webhook(image_path: str, webhook_url: str, alert: dict, logger: logging.Logger) -> bool:
    """
    Send an image to a webhook URL
    
    Args:
        image_path: Path to the image file
        webhook_url: The webhook URL to send images to
        alert: Alert data dictionary
        logger: Logger instance
        
    Returns:
        Boolean indicating success
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        # Get the alert details for metadata
        event_type = alert.get('event', 'Unknown')
        alert_id = alert.get('id', 'unknown')
        headline = alert.get('headline', '')
        
        # Get detailed warning text
        description = alert.get('description', '')
        instruction = alert.get('instruction', '')
        nws_headline = alert.get('NWSheadline', '')
        area_desc = alert.get('areaDesc', '')
        
        # Format the full warning text
        full_warning = f"""
**{event_type}: {headline}**
**Areas Affected:** {area_desc}
**NWS Headline:** {nws_headline}
**Description:**
{description}
**Instructions:**
{instruction}
"""
        
        # Create a payload with the full warning text
        payload = {
            "content": full_warning,
            "username": "Visual Warnings Bot"
        }
        
        # Create multipart form data with the image file
        with open(image_path, 'rb') as img_file:
            files = {
                'file': (os.path.basename(image_path), img_file, 'image/png')
            }
            
            # Send the request
            logger.info(f"Sending {event_type} image and text to webhook: {os.path.basename(image_path)}")
            response = requests.post(webhook_url, data=payload, files=files)
            response.raise_for_status()
        
        logger.info(f"Webhook delivery successful for {alert_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending webhook: {e}")
        logger.error(traceback.format_exc())
        return False

def check_and_generate_warnings(custom_feed_url: str, output_dir: str, webhook_url: Optional[str], logger: logging.Logger):
    """
    Check for new warnings and generate images
    
    Args:
        custom_feed_url: RSS feed URL to monitor
        output_dir: Directory to save generated images
        webhook_url: Optional webhook URL to send images to
        logger: Logger instance
    """
    try:
        logger.info("Starting warning check...")
        
        # Initialize services with the custom feed URL
        rss_service = RSSService(custom_feed_url=custom_feed_url)
        map_service = MapService(output_dir=output_dir)
        
        # Get new alerts
        new_alerts = rss_service.get_new_alerts()
        logger.info(f"Found {len(new_alerts)} new alerts")
        
        # Process each alert
        image_paths = []
        for alert in new_alerts:
            alert_id = alert.get('id', 'unknown')
            event_type = alert.get('event', 'Unknown')
            logger.info(f"Processing {event_type} alert: {alert_id}")
            
            # Check if we have polygon data
            if 'polygon' in alert and alert['polygon']:
                # Generate the warning map
                try:
                    image_path = map_service.create_warning_map(alert)
                    if image_path:
                        image_paths.append(image_path)
                        logger.info(f"Generated map for {event_type}: {image_path}")
                        
                        # Send to webhook if URL provided
                        if webhook_url:
                            send_image_webhook(image_path, webhook_url, alert, logger)
                    else:
                        logger.warning(f"Failed to generate map for {alert_id}")
                except Exception as e:
                    logger.error(f"Error generating map for {alert_id}: {e}")
                    logger.error(traceback.format_exc())
            else:
                logger.warning(f"No polygon data for {alert_id}")
        
        logger.info(f"Generated {len(image_paths)} warning maps")
        return image_paths
    
    except Exception as e:
        logger.error(f"Error in check_and_generate_warnings: {e}")
        logger.error(traceback.format_exc())
        return []

def run_scheduled_job(custom_feed_url: str, output_dir: str, webhook_url: Optional[str], logger: logging.Logger):
    """Run the scheduled job and log results"""
    logger.info("Running scheduled warning check...")
    try:
        image_paths = check_and_generate_warnings(custom_feed_url, output_dir, webhook_url, logger)
        logger.info(f"Scheduled job completed. Generated {len(image_paths)} images.")
    except Exception as e:
        logger.error(f"Scheduled job failed with exception: {e}")
        logger.error(traceback.format_exc())
        logger.info("Continuing to run despite error...")

def cleanup_old_files(output_dir: str, max_age_hours: int, logger: logging.Logger):
    """
    Remove old files from the output directory to prevent disk space issues
    
    Args:
        output_dir: The directory to clean
        max_age_hours: Maximum age of files in hours before removal
        logger: Logger instance
    """
    try:
        if not os.path.exists(output_dir):
            return
            
        now = time.time()
        count = 0
        
        for filename in os.listdir(output_dir):
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                file_age_hours = (now - os.path.getmtime(filepath)) / 3600
                if file_age_hours > max_age_hours:
                    os.remove(filepath)
                    count += 1
        
        if count > 0:
            logger.info(f"Cleaned up {count} files older than {max_age_hours} hours")
    except Exception as e:
        logger.error(f"Error cleaning up old files: {e}")

def main():
    """Main function to run the automation"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Automate NWS warning image generation')
    parser.add_argument('--feed-url', type=str, default="https://api.weather.gov/alerts/active.atom?zone=KYC105,KYC075,KYC039,KYC007,KYC145,KYC083,KYC157,KYC035,KYC139,KYC221,KYC143,KYC055,KYC033,KYC047,KYC107,KYC233,KYC225,KYC101,KYC059,KYC149,KYC177,KYC219,KYC141,KYC213,KYC031,KYC183,KYC091,KYC227", 
                        help='RSS feed URL to monitor')
    parser.add_argument('--output', type=str, default='output', help='Output directory for images')
    parser.add_argument('--interval', type=int, default=1, help='Check interval in minutes (default: 1 minute)')
    parser.add_argument('--run-once', action='store_true', help='Run once and exit')
    parser.add_argument('--webhook', type=str, help='Webhook URL to send images to')
    parser.add_argument('--max-age', type=int, default=48, help='Maximum age of files in hours before cleanup (default: 48 hours)')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    logger.info("====== Visual Warnings Service Starting ======")
    logger.info(f"Monitoring RSS feed: {args.feed_url}")
    logger.info(f"Update interval: {args.interval} minute(s)")
    if args.webhook:
        logger.info("Webhook integration enabled")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    # Run once or schedule
    if args.run_once:
        logger.info("Running single check...")
        check_and_generate_warnings(args.feed_url, args.output, args.webhook, logger)
        logger.info("Check completed")
    else:
        # Schedule the job to run at the specified interval
        logger.info(f"Scheduling checks every {args.interval} minute(s)")
        schedule.every(args.interval).minutes.do(
            run_scheduled_job, custom_feed_url=args.feed_url, output_dir=args.output, webhook_url=args.webhook, logger=logger
        )
        
        # Schedule cleanup job to run daily
        schedule.every().day.at("03:00").do(
            cleanup_old_files, output_dir=args.output, max_age_hours=args.max_age, logger=logger
        )
        
        # Run once immediately
        logger.info("Running initial check...")
        check_and_generate_warnings(args.feed_url, args.output, args.webhook, logger)
        
        # Keep running the scheduler with robust error handling
        logger.info("Starting scheduler. Press Ctrl+C to exit.")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while True:
                try:
                    schedule.run_pending()
                    time.sleep(1)
                    consecutive_errors = 0  # Reset error counter on successful iteration
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Error in scheduler loop: {e}")
                    logger.error(traceback.format_exc())
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(f"Too many consecutive errors ({consecutive_errors}). Restarting scheduler...")
                        # Reset scheduler and reschedule jobs
                        schedule.clear()
                        schedule.every(args.interval).minutes.do(
                            run_scheduled_job, custom_feed_url=args.feed_url, output_dir=args.output, webhook_url=args.webhook, logger=logger
                        )
                        schedule.every().day.at("03:00").do(
                            cleanup_old_files, output_dir=args.output, max_age_hours=args.max_age, logger=logger
                        )
                        consecutive_errors = 0
                    
                    # Sleep briefly to avoid tight error loops
                    time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in scheduler: {e}")
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
