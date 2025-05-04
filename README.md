# Visual Warnings Service

A 24/7 service that monitors NWS weather warnings, generates visual maps, and sends them to a webhook.

## Features

- Automatic monitoring of NWS alerts via RSS feed
- Visual map generation for active warnings
- Webhook integration for automatic notification delivery
- Runs as a background service that starts automatically on boot
- Minute-by-minute updates for timely warning notifications
- Automatic cleanup of old files to prevent disk space issues

## Setup Instructions

### Prerequisites

1. Make sure you have all required dependencies installed:
   ```
   pip install -r requirements.txt
   ```

2. Chrome or Chromium must be installed for Selenium (used for image generation)

### Setting up the Service

1. Make the setup script executable:
   ```
   chmod +x setup_service.sh
   ```

2. Run the setup script:
   ```
   ./setup_service.sh
   ```

3. When prompted, enter your webhook URL (Discord, Slack, or other webhook service)

The service will now be installed as a Launch Agent and will start automatically.

### Manual Configuration

If you need to manually configure the service:

1. Edit the `com.zacharymiller.visualwarnings.plist` file
2. Update the webhook URL and any other parameters
3. Copy the file to `~/Library/LaunchAgents/`
4. Load the service with: `launchctl load ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist`

## Command Line Options

You can run the service manually with various options:

```
python automation.py [options]
```

Options:
- `--feed-url URL`: RSS feed URL to monitor (defaults to Kentucky counties)
- `--output DIR`: Output directory for images (default: output)
- `--interval MINUTES`: Check interval in minutes (default: 1)
- `--webhook URL`: Webhook URL to send images to
- `--max-age HOURS`: Maximum age of files in hours before cleanup (default: 48)
- `--run-once`: Run once and exit (for testing)

## Monitoring the Service

- View logs: Check `~/Library/Logs/VisualWarnings/` for output and error logs
- Check status: `launchctl list | grep visualwarnings`
- Stop service: `launchctl unload ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist`
- Start service: `launchctl load ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist`

## Customizing Warning Areas

You can customize the monitored counties by modifying the default RSS feed URL in `automation.py`. 
The default URL monitors Kentucky counties, but you can change it to monitor your desired counties/zones.

## Webhook Integration

The service can send warning images and detailed warning text to:
- Discord webhooks
- Slack webhooks
- Any webhook service that accepts POST requests with file attachments

## Troubleshooting

If the service isn't working properly:
1. Check the log files in `~/Library/Logs/VisualWarnings/`
2. Ensure all requirements are installed correctly
3. Make sure Chrome/Chromium is installed for Selenium
4. Verify that the webhook URL is correct
5. Check that your Mac has internet access

If needed, restart the service with:
```
launchctl unload ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist
launchctl load ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist
```

## License

MIT
