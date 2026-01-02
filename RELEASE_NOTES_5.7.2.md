# Release Notes v5.7.2

## Bug Fixes

### Dimension Filtering Improvements

This release fixes several issues with the `include_dimensions=False` default introduced in v5.7.0.

- **Statement of Equity and Comprehensive Income NaN values** (#571): Fixed a regression where these statements showed NaN values after the dimension filtering changes. Statement-type aware filtering now correctly handles equity statements that require certain dimensional data.

- **Missing Balance Sheet line items** (#568, #569): Fixed issues where some balance sheet items were incorrectly filtered out:
  - Contra accounts (like Treasury Stock) now correctly apply `preferred_sign`
  - Equity Method Investment breakdowns are properly filtered
  - Presentation-linkbase validation ensures face values are shown while hiding unnecessary breakdowns

### Enhanced Dimension Classification

- Improved pattern-based detection for classifying dimensions as structural vs. breakdown
- Better handling of segment and geographic dimensions that should appear on the face of statements

## Upgrading

```bash
pip install edgartools --upgrade
```

No breaking changes from v5.7.0/v5.7.1.
