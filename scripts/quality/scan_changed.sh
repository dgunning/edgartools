#!/usr/bin/env bash
# Scan only git-changed Python files for quick feedback during development
# Usage: ./scripts/quality/scan_changed.sh [branch]
# Default branch: main

set -euo pipefail

BRANCH="${1:-main}"

echo "🔍 Code Quality Scan - Changed Files"
echo "===================================="
echo "Comparing against: $BRANCH"
echo ""

# Get changed Python files
CHANGED_FILES=$(git diff --name-only --diff-filter=ACM "$BRANCH"...HEAD | grep '\.py$' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "✅ No Python files changed"
    exit 0
fi

echo "📝 Changed files:"
echo "$CHANGED_FILES" | sed 's/^/  - /'
echo ""

# Count files
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | xargs)
echo "Total: $FILE_COUNT file(s)"
echo ""

# Ruff check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Running Ruff (linter + formatter)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if echo "$CHANGED_FILES" | xargs uvx ruff check --fix 2>&1; then
    echo "  ✅ No issues found"
else
    echo "  ⚠️  Issues found (some auto-fixed)"
fi
echo ""

# Type check (if pyright is available)
if command -v pyright &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔤 Running Pyright (type checker)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if echo "$CHANGED_FILES" | xargs pyright 2>&1 | head -20; then
        echo "  ✅ No type errors"
    else
        echo "  ⚠️  Type issues found"
    fi
    echo ""
fi

# Complexity check (warn only)
if command -v uvx &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 Checking complexity (warnings only)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    COMPLEX_FUNCS=$(echo "$CHANGED_FILES" | xargs uvx radon cc --min=C -nc 2>/dev/null || true)
    if [ -z "$COMPLEX_FUNCS" ]; then
        echo "  ✅ All functions have good complexity (A-B)"
    else
        echo "$COMPLEX_FUNCS"
        echo ""
        echo "  ⚠️  Found functions with complexity ≥ C"
        echo "     Consider refactoring D/F grade functions"
    fi
    echo ""
else
    echo "💡 Install uv for tool management: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
fi

# Dead code check (warn only)
if command -v uvx &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧹 Checking for dead code (warnings only)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    DEAD_CODE=$(echo "$CHANGED_FILES" | xargs uvx vulture --min-confidence 80 2>/dev/null || true)
    if [ -z "$DEAD_CODE" ]; then
        echo "  ✅ No obvious dead code detected"
    else
        echo "$DEAD_CODE" | head -10
        echo ""
        echo "  ⚠️  Possible unused code detected"
        echo "     Review carefully (may be false positives)"
    fi
    echo ""
else
    echo "💡 Install uv for tool management: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
fi

# Security scan
if command -v uvx &> /dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔒 Security scan (HIGH severity only)..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if echo "$CHANGED_FILES" | xargs uvx bandit -ll -iii 2>&1 | grep -E "Issue:|Severity: High" || true; then
        echo "  ⚠️  Security issues found - review above"
    else
        echo "  ✅ No high-severity security issues"
    fi
    echo ""
else
    echo "💡 Install uv for tool management: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Scan complete!"
echo ""
echo "💡 Next steps:"
echo "   - Fix any HIGH priority issues"
echo "   - Review warnings (optional)"
echo "   - Run full scan before PR: ./scripts/quality/scan_full.sh"
echo ""
