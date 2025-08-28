# Financial Statement Color Schemes

## Default Behavior (Changed)
As of version 4.8.3, the **professional** scheme is now the default, providing better visibility for all financial items. The old dim text scheme is still available as "default" for backwards compatibility.

## Previous Problem (Fixed)
The old default scheme used dim/gray text for important financial items like "Total Revenue" and "Operating Income", making them hard to read in many terminals. This has been fixed by making "professional" the new default.

## Available Schemes

### professional (Now Default)
- **Primary items**: Bold bright white (Total Revenue, Net Income)
- **Section headers**: Bold blue
- **Regular items**: Normal white text
- **Low confidence**: Italic (instead of dim)
- **Values**: Green (positive) / Red (negative)
- **Best for**: Most terminal environments

### high_contrast
- **All colors**: Bright variants
- **Best for**: Terminals with poor dim text support
- **Note**: May be too bright for some users

### minimal
- **Focus**: Structure over colors
- **Colors**: Only red for negative values
- **Best for**: Users who prefer less color

### accessible
- **Colors**: Blue/Magenta instead of Green/Red
- **Best for**: Color-blind users
- **Feature**: Uses underline for emphasis

### default (Old Scheme)
- **Legacy**: Previous default implementation
- **Issue**: Dim text is hard to read
- **Use case**: Backwards compatibility only

## Usage

No configuration needed - **professional** is now the default!

### To use a different scheme:
```bash
# For current session
export EDGAR_FINANCIALS_COLOR_SCHEME=minimal  # or high_contrast, accessible, etc.
python your_script.py
```

### To revert to old behavior:
```bash
export EDGAR_FINANCIALS_COLOR_SCHEME=default  # Use old dim text scheme
```

### Set in Python:
```python
import os
# Only needed if you want a non-default scheme
os.environ["EDGAR_FINANCIALS_COLOR_SCHEME"] = "minimal"  # or any other scheme

from edgar import Company
# Uses professional by default if EDGAR_FINANCIALS_COLOR_SCHEME not set
```

## Testing Schemes

Run the test script to see all schemes:
```bash
python test_color_schemes.py
```

Or demo script for before/after:
```bash
python demo_color_schemes.py
```

## Implementation Details

The color schemes are defined in `edgar/entity/terminal_styles.py` and affect:
- `enhanced_statement.py` - Multi-period financial statements
- `statement.py` - Basic financial statement display

Each scheme is a dictionary mapping semantic elements to Rich text styles:
- `abstract_item`: Section headers
- `total_item`: Total/summary lines
- `regular_item`: Normal line items
- `low_confidence_item`: Items with confidence < 0.8
- `positive_value`: Positive numbers
- `negative_value`: Negative numbers
- `panel_border`: Statement border color

## Customization

To create your own scheme, add it to `terminal_styles.py`:

```python
MY_SCHEME = {
    "abstract_item": "bold magenta",
    "total_item": "bold underline",
    # ... etc
}

SCHEMES["my_scheme"] = MY_SCHEME
```

Then use: `export EDGAR_FINANCIALS_COLOR_SCHEME=my_scheme`