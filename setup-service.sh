#!/bin/bash

# Script to automate systemd service setup and worker count management for Midnight Miner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="midnight-miner"
ENV_FILE="${SCRIPT_DIR}/${SERVICE_NAME}.env"
SERVICE_FILE="${SCRIPT_DIR}/${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"
SYSTEMD_SERVICE="${SYSTEMD_DIR}/${SERVICE_NAME}.service"
MINER_SCRIPT="${SCRIPT_DIR}/miner.py"
VENV_DIR="${SCRIPT_DIR}/venv"
REQUIREMENTS_FILE="${SCRIPT_DIR}/requirements.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Enable exit on error after OS check
set -e

# Detect and validate Python 3 executable
detect_python3() {
    local python_cmd=""

    # Try python3 first
    if command -v python3 &> /dev/null; then
        python_cmd="python3"
    # Try python as fallback
    elif command -v python &> /dev/null; then
        python_cmd="python"
    fi

    # If we found a Python command, verify it's version 3.x
    if [ -n "$python_cmd" ]; then
        local version_output=$($python_cmd --version 2>&1)
        local major_version=$(echo "$version_output" | awk '{print $2}' | cut -d. -f1)

        if [ "$major_version" -ge 3 ] 2>/dev/null; then
            echo "$python_cmd"
            return 0
        fi
    fi

    return 1
}

# Validate Python 3 is available
PYTHON_CMD=$(detect_python3)
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3 or greater is required but not found${NC}"
    echo -e "${YELLOW}Please install Python 3 and ensure it's available in your PATH${NC}"
    echo -e "${YELLOW}You can check with: python3 --version${NC}"
    exit 1
fi

# Verify Python version one more time and get full path
PYTHON_FULL_PATH=$(command -v "$PYTHON_CMD" || echo "$PYTHON_CMD")
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --workers N          Set the number of workers (required for setup)"
    echo "  --user USER          Set the user to run the service as (default: current user)"
    echo "  --defensio           Enable Defensio API mode (mines DFO instead of NIGHT)"
    echo "  --install            Install and enable the systemd service"
    echo "  --update             Update existing service file and reload systemd"
    echo "  --uninstall          Stop, disable, and remove the systemd service"
    echo "  --status             Show service status"
    echo "  --logs               Show service logs (follow mode)"
    echo "  --restart            Restart the service"
    echo "  --stop               Stop the service"
    echo "  --start              Start the service"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --workers 4                    # Set worker count to 4"
    echo "  $0 --workers 4 --install         # Set workers to 4 and install service"
    echo "  $0 --workers 4 --defensio        # Set workers to 4 with Defensio API"
    echo "  $0 --workers 8 --update          # Update workers to 8 and reload service"
    echo "  $0 --update                      # Update service with existing config"
    echo "  $0 --workers 8 --user myuser     # Set workers to 8 with specific user"
    echo "  $0 --status                      # Check service status"
    echo "  $0 --logs                        # View service logs"
}

setup_venv() {
    echo -e "${GREEN}Setting up Python virtual environment...${NC}"

    # Check if venv already exists
    if [ -d "${VENV_DIR}" ]; then
        echo -e "${YELLOW}Virtual environment already exists at ${VENV_DIR}${NC}"
        echo -e "${YELLOW}Updating dependencies...${NC}"
    else
        echo -e "${GREEN}Creating virtual environment at ${VENV_DIR}...${NC}"
        "$PYTHON_CMD" -m venv "${VENV_DIR}"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error: Failed to create virtual environment${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi

    # Activate venv and install/upgrade pip
    echo -e "${GREEN}Upgrading pip...${NC}"
    "${VENV_DIR}/bin/pip" install --upgrade pip --quiet

    # Install requirements
    if [ -f "${REQUIREMENTS_FILE}" ]; then
        echo -e "${GREEN}Installing requirements from ${REQUIREMENTS_FILE}...${NC}"
        "${VENV_DIR}/bin/pip" install -r "${REQUIREMENTS_FILE}" --quiet
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error: Failed to install requirements${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Requirements installed${NC}"
    else
        echo -e "${YELLOW}Warning: requirements.txt not found at ${REQUIREMENTS_FILE}${NC}"
        echo -e "${YELLOW}Installing basic dependencies...${NC}"
        "${VENV_DIR}/bin/pip" install pycardano wasmtime requests cbor2 portalocker --quiet
        echo -e "${GREEN}✓ Basic dependencies installed${NC}"
    fi
}

create_env_file() {
    local workers=$1
    local defensio=$2
    echo -e "${GREEN}Creating/updating environment file: ${ENV_FILE}${NC}"
    cat > "${ENV_FILE}" << EOF
# Midnight Miner Environment Configuration
# Set the number of workers to use
WORKERS=${workers}
# Enable Defensio API mode (true/false)
DEFENSIO=${defensio}
EOF
    echo -e "${GREEN}✓ Environment file created with WORKERS=${workers}, DEFENSIO=${defensio}${NC}"
}

create_service_file() {
    local user=${1:-$(whoami)}

    # Validate that miner.py exists
    if [ ! -f "${MINER_SCRIPT}" ]; then
        echo -e "${RED}Error: miner.py not found at ${MINER_SCRIPT}${NC}"
        echo -e "${RED}Please run this script from the MidnightMiner directory${NC}"
        exit 1
    fi

    # Ensure venv exists
    if [ ! -d "${VENV_DIR}" ]; then
        echo -e "${RED}Error: Virtual environment not found at ${VENV_DIR}${NC}"
        echo -e "${RED}Please run setup with --workers first to create the venv${NC}"
        exit 1
    fi

    # Get venv Python path
    VENV_PYTHON="${VENV_DIR}/bin/python"
    if [ ! -f "${VENV_PYTHON}" ]; then
        echo -e "${RED}Error: Python interpreter not found in venv at ${VENV_PYTHON}${NC}"
        exit 1
    fi

    echo -e "${GREEN}Creating/updating service file: ${SERVICE_FILE}${NC}"
    echo -e "${YELLOW}  Using Python: ${VENV_PYTHON} (from venv)${NC}"
    echo -e "${YELLOW}  Using User: ${user}${NC}"
    echo -e "${YELLOW}  Working Directory: ${SCRIPT_DIR}${NC}"

    cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Midnight Miner Service
After=network.target

[Service]
Type=simple
User=${user}
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStartPre=-/usr/bin/git pull
ExecStart=/bin/bash -c 'if [ "\${DEFENSIO}" = "true" ]; then exec ${VENV_PYTHON} ${MINER_SCRIPT} --workers \${WORKERS} --defensio; else exec ${VENV_PYTHON} ${MINER_SCRIPT} --workers \${WORKERS}; fi'
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    echo -e "${GREEN}✓ Service file created${NC}"
}

install_service() {
    if [ ! -f "${SERVICE_FILE}" ]; then
        echo -e "${RED}Error: Service file not found. Run with --workers first.${NC}"
        exit 1
    fi

    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Installing systemd service requires sudo privileges${NC}"
    fi

    # Check if service already exists
    if [ -f "${SYSTEMD_SERVICE}" ]; then
        echo -e "${YELLOW}Service already exists. Updating...${NC}"
    else
        echo -e "${GREEN}Installing systemd service...${NC}"
    fi

    sudo cp "${SERVICE_FILE}" "${SYSTEMD_SERVICE}"
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}.service" 2>/dev/null || true
    echo -e "${GREEN}✓ Service installed/updated and enabled${NC}"

    # Check if service is running and offer to restart
    if sudo systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        echo -e "${YELLOW}Service is currently running. Restart with: sudo systemctl restart ${SERVICE_NAME}${NC}"
    else
        echo -e "${YELLOW}Start the service with: sudo systemctl start ${SERVICE_NAME}${NC}"
    fi
}

update_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Updating systemd service requires sudo privileges${NC}"
    fi

    # Check if service is installed
    if [ ! -f "${SYSTEMD_SERVICE}" ]; then
        echo -e "${RED}Error: Service is not installed. Use --install instead.${NC}"
        exit 1
    fi

    # Ensure venv exists (create if missing)
    if [ ! -d "${VENV_DIR}" ]; then
        echo -e "${YELLOW}Virtual environment not found. Creating it...${NC}"
        setup_venv
    fi

    # If workers, user, or defensio are provided, update the service file
    if [ -n "$WORKERS" ] || [ -n "$USER" ] || [ "$DEFENSIO" != "false" ]; then
        if [ -z "$WORKERS" ]; then
            # Load existing workers from env file if it exists
            if [ -f "${ENV_FILE}" ]; then
                WORKERS=$(grep "^WORKERS=" "${ENV_FILE}" | cut -d'=' -f2)
            else
                echo -e "${RED}Error: --workers is required when updating service file${NC}"
                exit 1
            fi
        fi

        # Load existing DEFENSIO setting if not explicitly set
        if [ "$DEFENSIO" = "false" ] && [ -f "${ENV_FILE}" ]; then
            EXISTING_DEFENSIO=$(grep "^DEFENSIO=" "${ENV_FILE}" | cut -d'=' -f2)
            if [ -n "$EXISTING_DEFENSIO" ]; then
                DEFENSIO="$EXISTING_DEFENSIO"
            fi
        fi

        create_env_file "$WORKERS" "$DEFENSIO"
        create_service_file "${USER:-$(whoami)}"
    elif [ ! -f "${SERVICE_FILE}" ]; then
        echo -e "${RED}Error: Service file not found. Provide --workers or ensure service file exists.${NC}"
        exit 1
    fi

    echo -e "${GREEN}Updating systemd service...${NC}"
    sudo cp "${SERVICE_FILE}" "${SYSTEMD_SERVICE}"
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Service updated and systemd reloaded${NC}"

    # Check if service is running and offer to restart
    if sudo systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        echo -e "${YELLOW}Service is currently running. Restart with: sudo systemctl restart ${SERVICE_NAME}${NC}"
    fi
}

uninstall_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Uninstalling systemd service requires sudo privileges${NC}"
    fi

    echo -e "${YELLOW}Stopping and removing service...${NC}"
    sudo systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
    sudo rm -f "${SYSTEMD_SERVICE}"
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Service uninstalled${NC}"
}

show_status() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Checking service status requires sudo privileges${NC}"
    fi
    sudo systemctl status "${SERVICE_NAME}.service" || true
}

show_logs() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Viewing logs requires sudo privileges${NC}"
    fi
    sudo journalctl -u "${SERVICE_NAME}.service" -f
}

restart_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Restarting service requires sudo privileges${NC}"
    fi
    echo -e "${GREEN}Restarting service...${NC}"
    sudo systemctl restart "${SERVICE_NAME}.service"
    echo -e "${GREEN}✓ Service restarted${NC}"
}

stop_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Stopping service requires sudo privileges${NC}"
    fi
    echo -e "${GREEN}Stopping service...${NC}"
    sudo systemctl stop "${SERVICE_NAME}.service"
    echo -e "${GREEN}✓ Service stopped${NC}"
}

start_service() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Starting service requires sudo privileges${NC}"
    fi
    echo -e "${GREEN}Starting service...${NC}"
    sudo systemctl start "${SERVICE_NAME}.service"
    echo -e "${GREEN}✓ Service started${NC}"
}

# Parse arguments
WORKERS=""
USER=""
DEFENSIO="false"
INSTALL=false
UPDATE=false
UNINSTALL=false
SHOW_STATUS=false
SHOW_LOGS=false
RESTART=false
STOP=false
START=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --user)
            USER="$2"
            shift 2
            ;;
        --defensio)
            DEFENSIO="true"
            shift
            ;;
        --install)
            INSTALL=true
            shift
            ;;
        --update)
            UPDATE=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --logs)
            SHOW_LOGS=true
            shift
            ;;
        --restart)
            RESTART=true
            shift
            ;;
        --stop)
            STOP=true
            shift
            ;;
        --start)
            START=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Handle uninstall
if [ "$UNINSTALL" = true ]; then
    uninstall_service
    exit 0
fi

# Handle update
if [ "$UPDATE" = true ]; then
    update_service
    exit 0
fi

# Handle status
if [ "$SHOW_STATUS" = true ]; then
    show_status
    exit 0
fi

# Handle logs
if [ "$SHOW_LOGS" = true ]; then
    show_logs
    exit 0
fi

# Handle restart
if [ "$RESTART" = true ]; then
    restart_service
    exit 0
fi

# Handle stop
if [ "$STOP" = true ]; then
    stop_service
    exit 0
fi

# Handle start
if [ "$START" = true ]; then
    start_service
    exit 0
fi

# Handle workers/service creation
if [ -n "$WORKERS" ]; then
    if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [ "$WORKERS" -lt 1 ]; then
        echo -e "${RED}Error: Workers must be a positive integer${NC}"
        exit 1
    fi

    setup_venv
    create_env_file "$WORKERS" "$DEFENSIO"
    create_service_file "${USER:-$(whoami)}"

    if [ "$INSTALL" = true ]; then
        install_service
    elif [ "$UPDATE" = true ]; then
        update_service
    else
        echo -e "${YELLOW}Service files created. Install with: $0 --install or update with: $0 --update${NC}"
    fi
else
    if [ "$INSTALL" = true ]; then
        # If install is requested without workers, check if files exist
        if [ -f "${SERVICE_FILE}" ] && [ -f "${ENV_FILE}" ]; then
            install_service
        else
            echo -e "${RED}Error: Service files not found. Run with --workers first.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: --workers is required for setup${NC}"
        usage
        exit 1
    fi
fi

