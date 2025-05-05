#!/bin/bash

# Visual Warnings Service Setup Script for Debian-based systems
# This script sets up the Visual Warnings service to run 24/7 on your Debian server

echo "=== Visual Warnings Service Setup for Debian ==="
echo "This script will set up the Visual Warnings service to run 24/7 on your server."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root to set up the systemd service."
  echo "Please run with: sudo ./setup_debian.sh"
  exit 1
fi

# Get the actual username (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
INSTALL_DIR="/opt/visual-warnings"

# Create installation directory
echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p $INSTALL_DIR

# Copy all necessary files
echo "Copying files to installation directory..."
cp -R "$(dirname "$0")"/* $INSTALL_DIR/

# Set ownership
echo "Setting proper ownership..."
chown -R $ACTUAL_USER:$ACTUAL_USER $INSTALL_DIR

# Make automation.py executable
echo "Making automation.py executable..."
chmod +x "$INSTALL_DIR/automation.py"

# Prompt for webhook URL
read -p "Enter your webhook URL (press Enter to skip): " webhook_url

# Create logs directory
echo "Creating logs directory..."
mkdir -p /var/log/visual-warnings
chown -R $ACTUAL_USER:$ACTUAL_USER /var/log/visual-warnings

# Update webhook URL and username in service file
if [ -n "$webhook_url" ]; then
    echo "Updating webhook URL in systemd service configuration..."
    sed -i "s|YOUR_WEBHOOK_URL_HERE|$webhook_url|g" "$INSTALL_DIR/visual-warnings.service"
else
    echo "No webhook URL provided. You'll need to update the service file manually later."
fi

# Update username in service file
sed -i "s|YOUR_USERNAME|$ACTUAL_USER|g" "$INSTALL_DIR/visual-warnings.service"

# Set up virtual environment
echo "Setting up Python virtual environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
    
    echo "Installing required packages..."
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    # Additional Debian-specific packages for Chrome/Selenium
    echo "Installing system dependencies for Chrome/Selenium..."
    apt-get update
    apt-get install -y chromium-driver chromium-browser
else
    echo "Using existing virtual environment."
fi

# Install and enable the systemd service
echo "Installing systemd service..."
cp "$INSTALL_DIR/visual-warnings.service" /etc/systemd/system/
chmod 644 /etc/systemd/system/visual-warnings.service

echo "Reloading systemd configuration..."
systemctl daemon-reload

echo "Enabling and starting the service..."
systemctl enable visual-warnings.service
systemctl start visual-warnings.service

echo ""
echo "=== Setup Complete ==="
echo "The Visual Warnings service is now running in the background."
echo "It will automatically start when the system boots."
echo ""

# Check if the service is running
sleep 2
if systemctl is-active --quiet visual-warnings.service; then
    echo "✅ Service is running successfully!"
else
    echo "⚠️ Service may not be running. Check the logs for details."
fi

echo ""
echo "To check status: systemctl status visual-warnings.service"
echo "To stop the service: systemctl stop visual-warnings.service"
echo "To restart the service: systemctl restart visual-warnings.service"
echo "To view logs: journalctl -u visual-warnings.service"
echo ""
echo "Log files:"
echo "- /var/log/visual-warnings/output.log"
echo "- /var/log/visual-warnings/error.log"
echo ""

# Manual run option
echo "Would you like to run the service manually once to test it? (y/n): "
read run_test
if [[ "$run_test" == "y" || "$run_test" == "Y" ]]; then
    echo "Running service manually with --run-once flag..."
    sudo -u $ACTUAL_USER "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/automation.py" --run-once
    echo "Manual test completed. Check output for any errors."
fi