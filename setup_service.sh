#!/bin/bash

# Visual Warnings Service Setup Script
# This script sets up the Visual Warnings service to run 24/7 on your Mac Mini M4

echo "=== Visual Warnings Service Setup ==="
echo "This script will set up the Visual Warnings service to run 24/7 on your Mac."
echo ""

# Make sure virtual environment is set up
if [ ! -d "$(dirname "$0")/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$(dirname "$0")/venv"
    
    echo "Installing required packages..."
    "$(dirname "$0")/venv/bin/pip" install -r "$(dirname "$0")/requirements.txt"
else
    echo "Using existing virtual environment."
fi

# Make automation.py executable
echo "Making automation.py executable..."
chmod +x "$(dirname "$0")/automation.py"

# Prompt for webhook URL
read -p "Enter your webhook URL (press Enter to skip): " webhook_url

# Create logs directory
echo "Creating logs directory..."
mkdir -p ~/Library/Logs/VisualWarnings

# Update webhook URL in plist file
if [ -n "$webhook_url" ]; then
    echo "Updating webhook URL in Launch Agent configuration..."
    sed -i "" "s|YOUR_WEBHOOK_URL_HERE|$webhook_url|g" "$(dirname "$0")/com.zacharymiller.visualwarnings.plist"
else
    echo "No webhook URL provided. You'll need to update the plist file manually later."
fi

# Copy Launch Agent to user's LaunchAgents directory
echo "Installing Launch Agent..."
mkdir -p ~/Library/LaunchAgents
cp "$(dirname "$0")/com.zacharymiller.visualwarnings.plist" ~/Library/LaunchAgents/

# Set proper permissions
chmod 644 ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist

# Display permission instructions
echo ""
echo "=== IMPORTANT: Full Disk Access Required ==="
echo "You may need to grant Python 'Full Disk Access' in System Settings:"
echo "1. Open System Settings (or System Preferences)"
echo "2. Go to Privacy & Security > Full Disk Access"
echo "3. Click the + button and add your Python interpreter:"
echo "   - $(dirname "$0")/venv/bin/python3"
echo "4. Make sure the checkbox next to Python is enabled"
echo ""
read -p "Have you granted Full Disk Access if needed? (y/n): " granted_access

if [[ "$granted_access" != "y" && "$granted_access" != "Y" ]]; then
    echo "Please grant Full Disk Access to Python before proceeding."
    echo "Run this script again after granting access."
    exit 1
fi

# Load the Launch Agent
echo "Loading Launch Agent..."
launchctl unload ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist

echo ""
echo "=== Setup Complete ==="
echo "The Visual Warnings service is now running in the background."
echo "It will automatically start when you log in."
echo ""

# Check if the service is running
sleep 2
if launchctl list | grep -q "com.zacharymiller.visualwarnings"; then
    echo "✅ Service is running successfully!"
else
    echo "⚠️ Service may not be running. Check the logs for details."
fi

echo ""
echo "To check status: launchctl list | grep visualwarnings"
echo "To stop the service: launchctl unload ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist"
echo "To start the service: launchctl load ~/Library/LaunchAgents/com.zacharymiller.visualwarnings.plist"
echo ""
echo "Log files:"
echo "- ~/Library/Logs/VisualWarnings/output.log"
echo "- ~/Library/Logs/VisualWarnings/error.log"
echo ""

# Manual run option
echo "Would you like to run the service manually once to test it? (y/n): "
read run_test
if [[ "$run_test" == "y" || "$run_test" == "Y" ]]; then
    echo "Running service manually with --run-once flag..."
    "$(dirname "$0")/venv/bin/python3" "$(dirname "$0")/automation.py" --run-once
    echo "Manual test completed. Check output for any errors."
fi