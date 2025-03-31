# XBRL vs XBRL2 Chart Generation

This directory contains scripts and documentation for analyzing the XBRL2 rewrite compared to the original XBRL package.

## Documentation

- `docs/xbrl2-rewrite-analysis.md`: Main analysis comparing XBRL vs XBRL2 features and structure
- `docs/xbrl2-complexity-analysis.md`: Focused analysis of complexity, method size, and development speed

## Chart Generation Script

The `generate_xbrl2_charts.py` script creates visualizations for both markdown files.

### Installation Requirements

To generate the charts, you need the following Python packages:

```bash
pip install matplotlib numpy pandas seaborn
```

### Usage

Run the script from the project root directory:

```bash
python generate_xbrl2_charts.py
```

This will generate the following charts in the `docs/images/` directory:

1. **Basic Comparison Charts:**
   - `xbrl2-code-metrics.png` - Code size and structure metrics
   - `xbrl2-code-distribution.png` - Distribution of code across files
   - `xbrl2-api-functionality.png` - API functionality comparison
   - `xbrl2-feature-comparison.png` - Feature availability comparison
   - `xbrl2-code-quality.png` - Code quality metrics

2. **Complexity Analysis Charts:**
   - `xbrl2-development-timeline.png` - Development speed over time
   - `xbrl2-method-complexity.png` - Method-level complexity metrics
   - `xbrl2-method-size.png` - Method size distribution
   - `xbrl2-architectural-complexity.png` - Architectural design patterns

### Manual Chart Creation

If you're unable to run the script, you can manually create visualizations for the markdown files:

1. Use any visualization tool (Excel, Google Sheets, etc.) to create charts with the data
2. Save the charts in PNG format in `docs/images/` with the names listed above
3. The markdown files will automatically display these charts

## Data Sources

The statistics and metrics in this analysis were derived from:

- Git logs for commit statistics
- Line counts from `wc -l` command
- Code analysis using `grep` and other Unix tools
- Manual code analysis for architectural and design patterns