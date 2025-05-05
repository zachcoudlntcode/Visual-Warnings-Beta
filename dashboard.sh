#!/bin/bash

# Visual Warnings Service Dashboard for Linux
# This script provides a simple dashboard to manage the Visual Warnings service

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Service name
SERVICE_NAME="visual-warnings.service"
LOG_DIR="/var/log/visual-warnings"
INSTALL_DIR="/opt/visual-warnings"

# Function to check if the script is run with sudo
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Please run with sudo privileges to manage the service${NC}"
        echo "Usage: sudo ./dashboard.sh"
        exit 1
    fi
}

# Function to display service status
show_status() {
    echo -e "${BLUE}=== Visual Warnings Service Status ===${NC}"
    
    # Check if service exists
    if systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
        # Check if service is running
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}● Service is running${NC}"
        else
            echo -e "${RED}○ Service is stopped${NC}"
        fi
        
        # Check if service is enabled at boot
        if systemctl is-enabled --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}● Service is enabled at boot${NC}"
        else
            echo -e "${YELLOW}○ Service is not enabled at boot${NC}"
        fi
        
        # Show service details
        echo
        echo -e "${BLUE}Service details:${NC}"
        systemctl status "$SERVICE_NAME" -n 5
    else
        echo -e "${RED}Service is not installed${NC}"
    fi
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}=== Recent Logs ===${NC}"
    if [ -d "$LOG_DIR" ]; then
        LATEST_LOG=$(find "$LOG_DIR" -name "visual_warnings_automation_*.log" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
        if [ -n "$LATEST_LOG" ]; then
            echo -e "${GREEN}Showing last 20 lines from ${LATEST_LOG}${NC}"
            echo
            tail -n 20 "$LATEST_LOG"
        else
            echo -e "${YELLOW}No log files found in $LOG_DIR${NC}"
        fi
    else
        echo -e "${RED}Log directory $LOG_DIR does not exist${NC}"
    fi
}

# Function to start the service
start_service() {
    echo -e "${BLUE}Starting service...${NC}"
    systemctl start "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Service started successfully${NC}"
    else
        echo -e "${RED}Failed to start service. Check logs for details.${NC}"
    fi
}

# Function to stop the service
stop_service() {
    echo -e "${BLUE}Stopping service...${NC}"
    systemctl stop "$SERVICE_NAME"
    sleep 2
    if ! systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Service stopped successfully${NC}"
    else
        echo -e "${RED}Failed to stop service${NC}"
    fi
}

# Function to restart the service
restart_service() {
    echo -e "${BLUE}Restarting service...${NC}"
    systemctl restart "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}Service restarted successfully${NC}"
    else
        echo -e "${RED}Failed to restart service. Check logs for details.${NC}"
    fi
}

# Function to enable/disable service at boot
toggle_boot() {
    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
        echo -e "${BLUE}Disabling service at boot...${NC}"
        systemctl disable "$SERVICE_NAME"
        echo -e "${YELLOW}Service will not start at boot${NC}"
    else
        echo -e "${BLUE}Enabling service at boot...${NC}"
        systemctl enable "$SERVICE_NAME"
        echo -e "${GREEN}Service will start automatically at boot${NC}"
    fi
}

# Function to run service once manually
run_once() {
    echo -e "${BLUE}Running service once...${NC}"
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${GREEN}Executing: $INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/automation.py --run-once${NC}"
        "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/automation.py" --run-once
        echo -e "${GREEN}Manual run completed${NC}"
    else
        echo -e "${RED}Installation directory $INSTALL_DIR not found${NC}"
    fi
}

# Main menu function
show_menu() {
    clear
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}     Visual Warnings Service Dashboard${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo
    show_status
    echo
    echo -e "${BLUE}Options:${NC}"
    echo "1. Start service"
    echo "2. Stop service"
    echo "3. Restart service"
    echo "4. Enable/Disable at boot"
    echo "5. Show logs"
    echo "6. Run service once manually"
    echo "7. Exit"
    echo
    read -p "Select an option (1-7): " choice
    
    case $choice in
        1) start_service ;;
        2) stop_service ;;
        3) restart_service ;;
        4) toggle_boot ;;
        5) show_logs ;;
        6) run_once ;;
        7) exit 0 ;;
        *) echo -e "${RED}Invalid option${NC}" ;;
    esac
    
    echo
    read -p "Press Enter to return to menu..."
}

# Main execution
check_sudo

while true; do
    show_menu
done