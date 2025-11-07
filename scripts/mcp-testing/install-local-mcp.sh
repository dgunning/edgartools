#!/bin/bash
#
# Install EdgarTools MCP Server from Local Distribution
#
# This script builds and installs EdgarTools with MCP support in a test
# virtual environment, simulating the user installation experience.
#
# Usage:
#   ./install-local-mcp.sh [venv_path]
#
# Arguments:
#   venv_path - Path to virtual environment (default: /tmp/edgartools-mcp-test)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH="${1:-/tmp/edgartools-mcp-test}"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo -e "${BLUE}EdgarTools MCP Local Installation${NC}"
echo -e "${BLUE}=================================${NC}\n"

# Step 1: Clean up old venv if it exists
if [ -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}⚠ Removing existing virtual environment...${NC}"
    rm -rf "$VENV_PATH"
fi

# Step 2: Build distribution
echo -e "${BLUE}📦 Building distribution...${NC}"
cd "$PROJECT_ROOT"
hatch build

# Find the most recent wheel
WHEEL_FILE=$(ls -t dist/edgartools-*.whl | head -1)
if [ -z "$WHEEL_FILE" ]; then
    echo -e "${RED}✗ No wheel file found in dist/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Built: $(basename "$WHEEL_FILE")${NC}\n"

# Step 3: Create virtual environment
echo -e "${BLUE}🔨 Creating virtual environment at: $VENV_PATH${NC}"
python3 -m venv "$VENV_PATH"
echo -e "${GREEN}✓ Virtual environment created${NC}\n"

# Step 4: Install package
echo -e "${BLUE}📥 Installing EdgarTools with AI extras...${NC}"
"$VENV_PATH/bin/pip" install --quiet --upgrade pip
"$VENV_PATH/bin/pip" install "$WHEEL_FILE[ai]"
echo -e "${GREEN}✓ Installation complete${NC}\n"

# Step 5: Verify installation
echo -e "${BLUE}🔍 Verifying installation...${NC}"
"$VENV_PATH/bin/python" -m edgar.ai --test
echo ""

# Step 6: Show configuration info
echo -e "${GREEN}✓ Installation successful!${NC}\n"
echo -e "${BLUE}Configuration for Claude Desktop:${NC}"
echo -e "${YELLOW}─────────────────────────────────${NC}"
echo "Python path: $VENV_PATH/bin/python"
echo ""
echo "Add this to your claude_desktop_config.json:"
echo ""
cat <<EOF
{
  "mcpServers": {
    "edgartools": {
      "command": "$VENV_PATH/bin/python",
      "args": ["-m", "edgar.ai"],
      "env": {
        "EDGAR_IDENTITY": "Your Name your.email@example.com"
      }
    }
  }
}
EOF
echo ""
echo -e "${YELLOW}─────────────────────────────────${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Update your Claude Desktop config (or run ./configure-claude-mcp.sh)"
echo "2. Restart Claude Desktop"
echo "3. Monitor logs with ./watch-mcp-logs.sh"
echo ""
echo -e "${GREEN}Done!${NC}"
