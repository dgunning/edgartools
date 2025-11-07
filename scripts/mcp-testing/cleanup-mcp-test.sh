#!/bin/bash
#
# Cleanup EdgarTools MCP Test Environment
#
# This script removes test artifacts and optionally restores your
# previous Claude Desktop configuration.
#
# Usage:
#   ./cleanup-mcp-test.sh [options]
#
# Options:
#   --all           Remove everything (venv, logs, config)
#   --venv          Remove only the test virtual environment
#   --logs          Clear only the MCP logs
#   --config        Restore previous Claude Desktop config
#   --keep-config   Keep current config (default)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH="/tmp/edgartools-mcp-test"
LOGS_DIR="$HOME/Library/Logs/Claude"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# Parse arguments
REMOVE_VENV=false
CLEAR_LOGS=false
RESTORE_CONFIG=false

if [ $# -eq 0 ]; then
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --all           Remove everything"
    echo "  --venv          Remove test virtual environment"
    echo "  --logs          Clear MCP logs"
    echo "  --config        Restore previous Claude config"
    echo "  --keep-config   Keep current config (default)"
    exit 0
fi

for arg in "$@"; do
    case $arg in
        --all)
            REMOVE_VENV=true
            CLEAR_LOGS=true
            RESTORE_CONFIG=true
            ;;
        --venv)
            REMOVE_VENV=true
            ;;
        --logs)
            CLEAR_LOGS=true
            ;;
        --config)
            RESTORE_CONFIG=true
            ;;
        --keep-config)
            RESTORE_CONFIG=false
            ;;
    esac
done

echo -e "${BLUE}EdgarTools MCP Cleanup${NC}"
echo -e "${BLUE}=====================${NC}\n"

# Remove virtual environment
if [ "$REMOVE_VENV" = true ]; then
    if [ -d "$VENV_PATH" ]; then
        echo -e "${YELLOW}🗑️  Removing virtual environment...${NC}"
        rm -rf "$VENV_PATH"
        echo -e "${GREEN}✓ Virtual environment removed${NC}\n"
    else
        echo -e "${GRAY}⊘ Virtual environment not found${NC}\n"
    fi
fi

# Clear logs
if [ "$CLEAR_LOGS" = true ]; then
    echo -e "${YELLOW}🗑️  Clearing MCP logs...${NC}"
    if [ -f "$LOGS_DIR/mcp.log" ]; then
        > "$LOGS_DIR/mcp.log"
        echo -e "${GREEN}✓ Main log cleared${NC}"
    fi
    if [ -f "$LOGS_DIR/mcp-server-edgartools.log" ]; then
        > "$LOGS_DIR/mcp-server-edgartools.log"
        echo -e "${GREEN}✓ Server log cleared${NC}"
    fi
    echo ""
fi

# Restore configuration
if [ "$RESTORE_CONFIG" = true ]; then
    # Find most recent backup
    BACKUP_FILE=$(ls -t "$CONFIG_FILE.backup."* 2>/dev/null | head -1)

    if [ -n "$BACKUP_FILE" ]; then
        echo -e "${YELLOW}📋 Restoring previous configuration...${NC}"
        echo "Backup: $(basename "$BACKUP_FILE")"

        # Show what will be restored
        echo -e "\n${BLUE}Previous configuration:${NC}"
        echo -e "${YELLOW}─────────────────────────────────${NC}"
        cat "$BACKUP_FILE" | head -20
        echo -e "${YELLOW}─────────────────────────────────${NC}\n"

        # Confirm restoration
        read -p "Restore this configuration? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp "$BACKUP_FILE" "$CONFIG_FILE"
            echo -e "${GREEN}✓ Configuration restored${NC}\n"

            # Remove all backups
            read -p "Remove all backup files? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -f "$CONFIG_FILE.backup."*
                echo -e "${GREEN}✓ Backup files removed${NC}\n"
            fi
        else
            echo -e "${YELLOW}⊘ Configuration restore cancelled${NC}\n"
        fi
    else
        echo -e "${YELLOW}⊘ No backup configuration found${NC}\n"
    fi
fi

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Cleanup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Show what's left
echo -e "${BLUE}Current state:${NC}"
if [ -d "$VENV_PATH" ]; then
    echo "  Virtual environment: Present"
else
    echo "  Virtual environment: Removed"
fi

if [ -f "$LOGS_DIR/mcp.log" ]; then
    LOG_SIZE=$(wc -l < "$LOGS_DIR/mcp.log" 2>/dev/null || echo "0")
    echo "  MCP logs: $LOG_SIZE lines"
else
    echo "  MCP logs: Not present"
fi

if [ -f "$CONFIG_FILE" ]; then
    if grep -q "edgartools" "$CONFIG_FILE" 2>/dev/null; then
        echo "  Claude config: EdgarTools configured"
    else
        echo "  Claude config: EdgarTools not configured"
    fi
else
    echo "  Claude config: Not present"
fi

echo ""
echo -e "${BLUE}If you restored config, remember to restart Claude Desktop${NC}"
