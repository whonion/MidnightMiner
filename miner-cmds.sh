#!/bin/bash

# Midnight Miner Command Shortcuts
# Simple wrapper script for common systemd service operations

SERVICE_NAME="midnight-miner"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verify OS is Linux (systemd is Linux-specific)
check_linux_os() {
    if [[ "$OSTYPE" != "linux-gnu"* ]] && [[ "$OSTYPE" != "linux-musl"* ]]; then
        echo -e "${RED}Error: This script requires Linux (systemd is not available on Windows or macOS)${NC}"
        echo -e "${YELLOW}Detected OS: $OSTYPE${NC}"
        echo -e "${YELLOW}Please run the miner manually using: python miner.py${NC}"
        exit 1
    fi

    # Additional check: verify systemd is available
    # Use || true to prevent script exit if command not found (we handle it below)
    if ! command -v systemctl &> /dev/null 2>&1 || [ ! -d "/etc/systemd" ]; then
        echo -e "${RED}Error: systemd is not available on this system.${NC}"
        echo -e "${YELLOW}Please run the miner manually using: python miner.py${NC}"
        exit 1
    fi
}

# Check OS before proceeding
check_linux_os

usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  status      Show service status"
    echo "  start       Start the service"
    echo "  stop        Stop the service"
    echo "  restart     Restart the service"
    echo "  logs        Show service logs (follow mode)"
    echo "  logs-tail   Show last 100 lines of logs"
    echo "  enable      Enable service to start on boot"
    echo "  disable     Disable service from starting on boot"
    echo "  config      Show current configuration (workers, defensio mode)"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 status      # Check if service is running"
    echo "  $0 config      # Show current configuration"
    echo "  $0 logs        # Follow service logs"
    echo "  $0 restart     # Restart the service"
}

check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        return 1
    fi
    return 0
}

show_status() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Checking service status requires sudo privileges${NC}"
    fi
    echo -e "${BLUE}Service Status:${NC}"
    sudo systemctl status "${SERVICE_NAME}.service" || true
}

start_service() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Starting service requires sudo privileges${NC}"
    fi
    echo -e "${GREEN}Starting ${SERVICE_NAME} service...${NC}"
    if sudo systemctl start "${SERVICE_NAME}.service"; then
        echo -e "${GREEN}✓ Service started${NC}"
    else
        echo -e "${RED}✗ Failed to start service${NC}"
        exit 1
    fi
}

stop_service() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Stopping service requires sudo privileges${NC}"
    fi
    echo -e "${YELLOW}Stopping ${SERVICE_NAME} service...${NC}"
    if sudo systemctl stop "${SERVICE_NAME}.service"; then
        echo -e "${GREEN}✓ Service stopped${NC}"
    else
        echo -e "${RED}✗ Failed to stop service${NC}"
        exit 1
    fi
}

restart_service() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Restarting service requires sudo privileges${NC}"
    fi
    echo -e "${YELLOW}Restarting ${SERVICE_NAME} service...${NC}"
    if sudo systemctl restart "${SERVICE_NAME}.service"; then
        echo -e "${GREEN}✓ Service restarted${NC}"
    else
        echo -e "${RED}✗ Failed to restart service${NC}"
        exit 1
    fi
}

show_logs() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Viewing logs requires sudo privileges${NC}"
    fi
    echo -e "${BLUE}Following service logs (Ctrl+C to exit):${NC}"
    sudo journalctl -u "${SERVICE_NAME}.service" -f
}

show_logs_tail() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Viewing logs requires sudo privileges${NC}"
    fi
    echo -e "${BLUE}Last 100 lines of service logs:${NC}"
    sudo journalctl -u "${SERVICE_NAME}.service" -n 100 --no-pager
}

enable_service() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Enabling service requires sudo privileges${NC}"
    fi
    echo -e "${GREEN}Enabling ${SERVICE_NAME} service to start on boot...${NC}"
    if sudo systemctl enable "${SERVICE_NAME}.service"; then
        echo -e "${GREEN}✓ Service enabled${NC}"
    else
        echo -e "${RED}✗ Failed to enable service${NC}"
        exit 1
    fi
}

disable_service() {
    if ! check_sudo; then
        echo -e "${YELLOW}Note: Disabling service requires sudo privileges${NC}"
    fi
    echo -e "${YELLOW}Disabling ${SERVICE_NAME} service from starting on boot...${NC}"
    if sudo systemctl disable "${SERVICE_NAME}.service"; then
        echo -e "${GREEN}✓ Service disabled${NC}"
    else
        echo -e "${RED}✗ Failed to disable service${NC}"
        exit 1
    fi
}

show_config() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ENV_FILE="${SCRIPT_DIR}/midnight-miner.env"

    if [ ! -f "${ENV_FILE}" ]; then
        echo -e "${RED}Error: Environment file not found at ${ENV_FILE}${NC}"
        echo -e "${YELLOW}Run setup-service.sh --workers N to create it${NC}"
        exit 1
    fi

    WORKERS=$(grep "^WORKERS=" "${ENV_FILE}" | cut -d'=' -f2)
    DEFENSIO=$(grep "^DEFENSIO=" "${ENV_FILE}" | cut -d'=' -f2)

    if [ -z "$WORKERS" ]; then
        echo -e "${RED}Error: WORKERS not found in ${ENV_FILE}${NC}"
        exit 1
    fi

    echo -e "${BLUE}Current Configuration:${NC}"
    echo -e "  Workers:  ${GREEN}${WORKERS}${NC}"

    if [ "$DEFENSIO" = "true" ]; then
        echo -e "  Mode:     ${GREEN}Defensio (DFO mining)${NC}"
    else
        echo -e "  Mode:     ${GREEN}Midnight (NIGHT mining)${NC}"
    fi
}

# Parse command
COMMAND="${1:-help}"

case "$COMMAND" in
    status)
        show_status
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    logs)
        show_logs
        ;;
    logs-tail)
        show_logs_tail
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    config|workers)
        show_config
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo ""
        usage
        exit 1
        ;;
esac



