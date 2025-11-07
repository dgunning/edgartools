#!/bin/bash
#
# Test EdgarTools MCP Server Tools
#
# This script performs basic smoke tests of the MCP server to verify
# it's working correctly before release.
#
# Usage:
#   ./test-mcp-tools.sh [python_path]
#
# Arguments:
#   python_path - Path to Python executable (default: /tmp/edgartools-mcp-test/bin/python)
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

echo -e "${BLUE}EdgarTools MCP Server Tests${NC}"
echo -e "${BLUE}===========================${NC}\n"

# Check if Python path exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}✗ Python not found at: $PYTHON_PATH${NC}"
    echo -e "${YELLOW}Run ./install-local-mcp.sh first${NC}"
    exit 1
fi

# Test 1: Server configuration test
echo -e "${BLUE}Test 1: Server Configuration${NC}"
if "$PYTHON_PATH" -m edgar.ai --test; then
    echo -e "${GREEN}✓ Server configuration passed${NC}\n"
else
    echo -e "${RED}✗ Server configuration failed${NC}\n"
    exit 1
fi

# Test 2: Module imports
echo -e "${BLUE}Test 2: Module Imports${NC}"
if "$PYTHON_PATH" -c "from edgar.ai.mcp_server import app; print('✓ mcp_server imported')"; then
    echo -e "${GREEN}✓ MCP server module imports successfully${NC}\n"
else
    echo -e "${RED}✗ MCP server module import failed${NC}\n"
    exit 1
fi

# Test 3: Tool handlers
echo -e "${BLUE}Test 3: Tool Handlers${NC}"
if "$PYTHON_PATH" -c "
from edgar.ai.tools.company_research import handle_company_research
from edgar.ai.tools.financial_analysis import handle_analyze_financials
print('✓ Tool handlers imported')
"; then
    echo -e "${GREEN}✓ Tool handlers import successfully${NC}\n"
else
    echo -e "${RED}✗ Tool handler import failed${NC}\n"
    exit 1
fi

# Test 4: EdgarTools core functionality
echo -e "${BLUE}Test 4: EdgarTools Core Functionality${NC}"
if "$PYTHON_PATH" -c "
from edgar import Company
company = Company('AAPL')
print(f'✓ Retrieved company: {company.name}')
"; then
    echo -e "${GREEN}✓ Core EdgarTools functionality works${NC}\n"
else
    echo -e "${RED}✗ Core functionality test failed${NC}\n"
    exit 1
fi

# Test 5: Workflow tool test (async)
echo -e "${BLUE}Test 5: Workflow Tools${NC}"
if "$PYTHON_PATH" -c "
import asyncio
from edgar.ai.tools.company_research import handle_company_research

async def test():
    result = await handle_company_research({'identifier': 'AAPL', 'detail_level': 'minimal', 'include_financials': False, 'include_filings': False})
    if result and len(result) > 0:
        print('✓ Company research tool works')
        return True
    return False

if not asyncio.run(test()):
    exit(1)
"; then
    echo -e "${GREEN}✓ Workflow tools functional${NC}\n"
else
    echo -e "${RED}✗ Workflow tool test failed${NC}\n"
    exit 1
fi

# Summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ All tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${BLUE}Next steps:${NC}"
echo "1. Configure Claude Desktop with ./configure-claude-mcp.sh"
echo "2. Restart Claude Desktop"
echo "3. Test with these prompts:"
echo "   - 'Research Tesla with financials'"
echo "   - 'Analyze Apple's income statement for 4 years'"
echo "   - 'Show me the latest SEC filings'"
echo ""
echo -e "${GREEN}Ready for testing!${NC}"
