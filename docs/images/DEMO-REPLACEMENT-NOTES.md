# Demo Asset Replacement Notes

## Phase 4: Replace Demo Asset

### Current Asset
- `docs/images/edgartools-demo.gif` - Console output GIF

### Requirement
Replace with a more compelling demo that showcases:
1. EdgarTools' rich terminal output (using `rich` library)
2. Multiple capabilities in one visual
3. Professional, polished appearance
4. Brand colors where possible

### Options

#### Option 1: Jupyter Notebook Screenshot (Recommended)
Create a Jupyter notebook that demonstrates:
```python
from edgar import *
set_identity("demo@edgartools.io")

# Show company lookup with rich output
company = Company("AAPL")
display(company)

# Show filings with rich table
filings = company.get_filings(form="10-K").latest(3)
display(filings)

# Show financials with rich formatting
financials = company.get_financials()
display(financials.balance_sheet())
```

**Steps:**
1. Create notebook with code above
2. Execute cells to generate rich output
3. Take high-quality screenshot (1200-1600px wide)
4. Save as `docs/images/edgartools-demo-rich.png`
5. Update README to use new image

#### Option 2: Terminal Recording → GIF
Use `terminalizer` or `asciinema` to record:
```bash
# Record terminal session
terminalizer record demo

# Convert to optimized GIF
terminalizer render demo
```

Show sequence:
1. Import and identity setup
2. Company lookup
3. Filing retrieval
4. Financial data extraction
5. Rich table display

#### Option 3: Before/After Comparison
Create side-by-side comparison SVG showing:
- Left: Messy HTML/web scraping code
- Right: Clean EdgarTools code with rich output

### Manual Work Required
This phase requires manual execution:
- [ ] Create demo notebook or script
- [ ] Run code to generate output
- [ ] Capture high-quality screenshot
- [ ] Optimize image size (<500KB preferred)
- [ ] Update README with new asset path
- [ ] Remove or archive old demo.gif

### Recommended Dimensions
- Width: 1200-1600px (GitHub README optimal)
- Format: PNG (for screenshots) or GIF (for animations)
- Optimize with tools like ImageOptim or TinyPNG

---
**Note:** This phase marked as requiring manual work. Proceeding to Phase 5 (Mermaid diagrams) which can be completed without code execution.