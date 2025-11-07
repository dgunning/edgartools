#!/bin/bash
#
# Configure Claude Desktop for EdgarTools MCP Server
#
# This script updates the Claude Desktop configuration to use your
# EdgarTools MCP test environment.
#
# Usage:
#   ./configure-claude-mcp.sh [python_path] [identity]
#
# Arguments:
#   python_path - Path to Python executable (default: /tmp/edgartools-mcp-test/bin/python)
#   identity    - Your SEC identity (default: from environment or prompt)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
PYTHON_PATH="${1:-/tmp/edgartools-mcp-test/bin/python}"
IDENTITY="${2:-${EDGAR_IDENTITY}}"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}EdgarTools MCP Configuration for Claude Desktop${NC}"
echo -e "${BLUE}===============================================${NC}\n"

# Check if Python path exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}✗ Python not found at: $PYTHON_PATH${NC}"
    echo -e "${YELLOW}Run ./install-local-mcp.sh first${NC}"
    exit 1
fi

# Get identity if not provided
if [ -z "$IDENTITY" ]; then
    echo -e "${YELLOW}Enter your SEC identity (e.g., \"John Doe john@example.com\"):${NC}"
    read -r IDENTITY
    if [ -z "$IDENTITY" ]; then
        echo -e "${RED}✗ Identity is required${NC}"
        exit 1
    fi
fi

# Create config directory if it doesn't exist
CONFIG_DIR="$(dirname "$CONFIG_FILE")"
if [ ! -d "$CONFIG_DIR" ]; then
    echo -e "${YELLOW}⚠ Creating Claude config directory...${NC}"
    mkdir -p "$CONFIG_DIR"
fi

# Backup existing config
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${BLUE}📋 Backing up existing configuration...${NC}"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✓ Backup saved to: $(basename "$BACKUP_FILE")${NC}\n"
fi

# Read existing config or create new one
if [ -f "$CONFIG_FILE" ]; then
    EXISTING_CONFIG=$(cat "$CONFIG_FILE")
else
    EXISTING_CONFIG='{}'
fi

# Generate new config
echo -e "${BLUE}✏️  Updating configuration...${NC}"
cat > "$CONFIG_FILE" <<EOF
{
  "mcpServers": {
    "edgartools": {
      "command": "$PYTHON_PATH",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "$IDENTITY"
      }
    }
  }
}
EOF

echo -e "${GREEN}✓ Configuration updated${NC}\n"

# Show current config
echo -e "${BLUE}Current configuration:${NC}"
echo -e "${YELLOW}─────────────────────────────────${NC}"
cat "$CONFIG_FILE"
echo -e "${YELLOW}─────────────────────────────────${NC}\n"

# Verify Python can run the server
echo -e "${BLUE}🔍 Verifying server can start...${NC}"
if "$PYTHON_PATH" -m edgar.ai --test > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server verification passed${NC}\n"
else
    echo -e "${RED}✗ Server verification failed${NC}"
    echo -e "${YELLOW}Check that EdgarTools is installed with AI extras${NC}\n"
    exit 1
fi

# Next steps
echo -e "${BLUE}Next steps:${NC}"
echo "1. Restart Claude Desktop"
echo "2. Look for the MCP indicator (🔨) in Claude Desktop"
echo "3. Monitor logs with ./watch-mcp-logs.sh"
echo ""
echo -e "${YELLOW}To restore previous config:${NC}"
echo "cp \"$BACKUP_FILE\" \"$CONFIG_FILE\""
echo ""
echo -e "${GREEN}Done!${NC}"
