#!/bin/bash

# Run Visual Warnings with elevated permissions
# This script runs the automation directly with sudo privileges to bypass permission issues

echo "=== Running Visual Warnings with elevated permissions ==="

# Directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create output directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/output"

# Run the Python script with sudo
echo "Running automation.py with administrative privileges..."
# This will prompt for your admin password
sudo python3 "$SCRIPT_DIR/automation.py" --run-once

echo ""
echo "=== Execution Completed ==="
echo "Check the output above for any errors or warnings."
echo ""
echo "If this succeeded but the Launch Agent version doesn't work:"
echo "The issue is likely related to permissions in the Launch Agent context."
echo "Follow the Full Disk Access instructions in the setup_service.sh script."