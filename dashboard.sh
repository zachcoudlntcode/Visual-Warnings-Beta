#!/bin/bash

# Visual Warnings Status Dashboard
# This script shows the real-time status of the Visual Warnings service

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Clear screen
clear

echo -e "${BLUE}=============================================${NC}"
echo -e "${BLUE}    VISUAL WARNINGS SERVICE DASHBOARD    ${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""

# Check if service is running
if launchctl list | grep -q "com.zacharymiller.visualwarnings"; then
    echo -e "${GREEN}✅ Service Status: RUNNING${NC}"
    pid=$(launchctl list | grep "com.zacharymiller.visualwarnings" | awk '{print $1}')
    echo -e "   Process ID: ${pid}"
else
    echo -e "${RED}❌ Service Status: NOT RUNNING${NC}"
fi

# Get info about last run
if [ -f ~/Library/Logs/VisualWarnings/error.log ]; then
    last_check=$(grep "Running scheduled warning check" ~/Library/Logs/VisualWarnings/error.log | tail -n 1)
    last_time=$(echo $last_check | cut -d' ' -f1,2)
    echo -e "${YELLOW}Last Check:${NC} $last_time"
    
    # Get count of warnings
    last_alert_count=$(grep "API returned" ~/Library/Logs/VisualWarnings/error.log | tail -n 1 | grep -o '[0-9]\+ total alerts' | cut -d' ' -f1)
    echo -e "${YELLOW}Active Alerts:${NC} $last_alert_count"
    
    # Get new alerts
    last_new_alerts=$(grep "Found [0-9]\+ new alerts" ~/Library/Logs/VisualWarnings/error.log | tail -n 1 | grep -o '[0-9]\+ new alerts' | cut -d' ' -f1)
    if [ "$last_new_alerts" != "0" ] && [ ! -z "$last_new_alerts" ]; then
        echo -e "${GREEN}New Alerts:${NC} $last_new_alerts"
    else
        echo -e "${YELLOW}New Alerts:${NC} 0"
    fi
else
    echo -e "${RED}❌ No log file found${NC}"
fi

echo ""
echo -e "${BLUE}--------- RECENT ACTIVITY ---------${NC}"
echo ""

# Show the last 10 significant log entries
if [ -f ~/Library/Logs/VisualWarnings/error.log ]; then
    grep -E "(Starting warning check|Found.*new alerts|Generated.*warning maps|Processing.*alert|Error)" ~/Library/Logs/VisualWarnings/error.log | tail -n 10
fi

echo ""
echo -e "${BLUE}--------- OUTPUT DIRECTORY ---------${NC}"
echo ""

# List recent output files
ls -lt "$(dirname "$0")/output" | head -n 10

echo ""
echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
echo ""

# Keep running and showing real-time updates
while true; do
    sleep 10
    clear
    $0
done