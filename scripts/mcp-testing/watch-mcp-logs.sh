#!/bin/bash
#
# Watch EdgarTools MCP Server Logs
#
# This script monitors Claude Desktop's MCP logs in real-time,
# showing color-coded output for easy debugging.
#
# Usage:
#   ./watch-mcp-logs.sh [options]
#
# Options:
#   --clear     Clear logs before watching
#   --errors    Show only errors
#   --both      Show both main and server-specific logs side by side
#

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Log file paths
LOGS_DIR="$HOME/Library/Logs/Claude"
MAIN_LOG="$LOGS_DIR/mcp.log"
SERVER_LOG="$LOGS_DIR/mcp-server-edgartools.log"

# Parse arguments
CLEAR_LOGS=false
ERRORS_ONLY=false
SHOW_BOTH=false

for arg in "$@"; do
    case $arg in
        --clear)
            CLEAR_LOGS=true
            ;;
        --errors)
            ERRORS_ONLY=true
            ;;
        --both)
            SHOW_BOTH=true
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --clear     Clear logs before watching"
            echo "  --errors    Show only errors"
            echo "  --both      Show both logs side by side"
            echo "  --help      Show this help message"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}EdgarTools MCP Log Monitor${NC}"
echo -e "${BLUE}==========================${NC}\n"

# Check if log directory exists
if [ ! -d "$LOGS_DIR" ]; then
    echo -e "${RED}✗ Claude logs directory not found: $LOGS_DIR${NC}"
    echo -e "${YELLOW}Make sure Claude Desktop is installed and has been run at least once${NC}"
    exit 1
fi

# Clear logs if requested
if [ "$CLEAR_LOGS" = true ]; then
    echo -e "${YELLOW}🗑️  Clearing logs...${NC}"
    > "$MAIN_LOG" 2>/dev/null || true
    > "$SERVER_LOG" 2>/dev/null || true
    echo -e "${GREEN}✓ Logs cleared${NC}\n"
fi

# Show log file info
echo -e "${BLUE}Monitoring:${NC}"
echo "  Main log: $MAIN_LOG"
echo "  Server log: $SERVER_LOG"
echo ""
echo -e "${GRAY}Press Ctrl+C to stop${NC}\n"
echo -e "${YELLOW}─────────────────────────────────${NC}\n"

# Function to colorize log output
colorize_log() {
    while IFS= read -r line; do
        if [[ $line == *"[error]"* ]]; then
            echo -e "${RED}$line${NC}"
        elif [[ $line == *"[warn"* ]]; then
            echo -e "${YELLOW}$line${NC}"
        elif [[ $line == *"[info]"* ]]; then
            echo -e "${BLUE}$line${NC}"
        elif [[ $line == *"Starting"* ]] || [[ $line == *"✓"* ]]; then
            echo -e "${GREEN}$line${NC}"
        else
            echo "$line"
        fi
    done
}

# Function to filter errors only
filter_errors() {
    grep --line-buffered -E '\[error\]|\[warn'
}

# Watch logs
if [ "$SHOW_BOTH" = true ]; then
    # Show both logs side by side (requires screen width)
    echo -e "${BLUE}Main Log${NC} | ${BLUE}Server Log${NC}"
    tail -f "$MAIN_LOG" "$SERVER_LOG" 2>/dev/null | colorize_log
elif [ "$ERRORS_ONLY" = true ]; then
    # Show only errors and warnings
    tail -f "$MAIN_LOG" "$SERVER_LOG" 2>/dev/null | filter_errors | colorize_log
else
    # Show server log by default (most relevant for debugging)
    if [ -f "$SERVER_LOG" ]; then
        tail -f "$SERVER_LOG" 2>/dev/null | colorize_log
    else
        echo -e "${YELLOW}⚠ Server log not found yet. Watching main log...${NC}\n"
        tail -f "$MAIN_LOG" 2>/dev/null | colorize_log
    fi
fi
