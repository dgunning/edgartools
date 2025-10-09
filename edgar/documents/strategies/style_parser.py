"""
CSS style parser for HTML elements.
"""

import re
from typing import Dict, Optional, Tuple, Union
from edgar.documents.types import Style
from edgar.documents.utils import get_cache_manager


class StyleParser:
    """
    Parser for CSS style attributes.
    
    Handles inline styles and converts them to Style objects.
    """
    
    # Common CSS units
    ABSOLUTE_UNITS = {'px', 'pt', 'pc', 'cm', 'mm', 'in'}
    RELATIVE_UNITS = {'em', 'rem', 'ex', 'ch', 'vw', 'vh', '%'}
    
    # Font weight mappings
    FONT_WEIGHT_MAP = {
        'normal': '400',
        'bold': '700',
        'bolder': '800',
        'lighter': '300'
    }
    
    def __init__(self):
        """Initialize style parser with cache."""
        self._cache = get_cache_manager().style_cache
    
    def parse(self, style_string: str) -> Style:
        """
        Parse CSS style string into Style object.
        
        Args:
            style_string: CSS style string (e.g., "font-size: 14px; color: red")
            
        Returns:
            Parsed Style object
        """
        if not style_string:
            return Style()
        
        # Check cache first
        cached_style = self._cache.get(style_string)
        if cached_style is not None:
            return cached_style
        
        # Parse style
        style = Style()
        
        # Split into individual declarations
        declarations = self._split_declarations(style_string)
        
        for prop, value in declarations.items():
            self._apply_property(style, prop, value)
        
        # Cache result
        self._cache.put(style_string, style)
        
        return style
    
    def _split_declarations(self, style_string: str) -> Dict[str, str]:
        """Split style string into property-value pairs."""
        declarations = {}
        
        # Split by semicolon, handling potential issues
        parts = style_string.split(';')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Split property and value
            if ':' in part:
                prop, value = part.split(':', 1)
                prop = prop.strip().lower()
                value = value.strip()
                
                if prop and value:
                    declarations[prop] = value
        
        return declarations
    
    def _apply_property(self, style: Style, prop: str, value: str):
        """Apply CSS property to Style object."""
        # Font properties
        if prop == 'font-size':
            size = self._parse_length(value)
            if size is not None:
                style.font_size = size
        
        elif prop == 'font-weight':
            style.font_weight = self._normalize_font_weight(value)
        
        elif prop == 'font-style':
            if value in ['italic', 'oblique']:
                style.font_style = 'italic'
            elif value == 'normal':
                style.font_style = 'normal'
        
        # Text properties
        elif prop == 'text-align':
            if value in ['left', 'right', 'center', 'justify']:
                style.text_align = value
        
        elif prop == 'text-decoration':
            style.text_decoration = value
        
        # Color properties
        elif prop == 'color':
            style.color = self._normalize_color(value)
        
        elif prop in ['background-color', 'background']:
            color = self._extract_background_color(value)
            if color:
                style.background_color = color
        
        # Spacing properties
        elif prop == 'margin':
            self._parse_box_property(style, 'margin', value)
        elif prop == 'margin-top':
            margin = self._parse_length(value)
            if margin is not None:
                style.margin_top = margin
        elif prop == 'margin-bottom':
            margin = self._parse_length(value)
            if margin is not None:
                style.margin_bottom = margin
        elif prop == 'margin-left':
            margin = self._parse_length(value)
            if margin is not None:
                style.margin_left = margin
        elif prop == 'margin-right':
            margin = self._parse_length(value)
            if margin is not None:
                style.margin_right = margin
        
        elif prop == 'padding':
            self._parse_box_property(style, 'padding', value)
        elif prop == 'padding-top':
            padding = self._parse_length(value)
            if padding is not None:
                style.padding_top = padding
        elif prop == 'padding-bottom':
            padding = self._parse_length(value)
            if padding is not None:
                style.padding_bottom = padding
        elif prop == 'padding-left':
            padding = self._parse_length(value)
            if padding is not None:
                style.padding_left = padding
        elif prop == 'padding-right':
            padding = self._parse_length(value)
            if padding is not None:
                style.padding_right = padding
        
        # Display properties
        elif prop == 'display':
            style.display = value
        
        # Size properties
        elif prop == 'width':
            style.width = self._parse_dimension(value)
        elif prop == 'height':
            style.height = self._parse_dimension(value)
        
        # Line height
        elif prop == 'line-height':
            line_height = self._parse_line_height(value)
            if line_height is not None:
                style.line_height = line_height
    
    def _parse_length(self, value: str) -> Optional[float]:
        """Parse CSS length value to pixels."""
        value = value.strip().lower()
        
        # Handle special values
        if value in ['0', 'auto', 'inherit', 'initial']:
            return 0.0 if value == '0' else None
        
        # Extract number and unit
        match = re.match(r'^(-?\d*\.?\d+)\s*([a-z%]*)$', value)
        if not match:
            return None
        
        num_str, unit = match.groups()
        try:
            num = float(num_str)
        except ValueError:
            return None
        
        # Convert to pixels
        if not unit or unit == 'px':
            return num
        elif unit == 'pt':
            return num * 1.333  # 1pt = 1.333px
        elif unit == 'em':
            return num * 16  # Assume 16px base
        elif unit == 'rem':
            return num * 16  # Assume 16px root
        elif unit == '%':
            return None  # Can't convert percentage without context
        elif unit == 'in':
            return num * 96  # 1in = 96px
        elif unit == 'cm':
            return num * 37.8  # 1cm = 37.8px
        elif unit == 'mm':
            return num * 3.78  # 1mm = 3.78px
        
        return None
    
    def _parse_dimension(self, value: str) -> Optional[Union[float, str]]:
        """Parse dimension value (width/height)."""
        value = value.strip()
        
        # Check for percentage
        if value.endswith('%'):
            return value  # Return as string
        
        # Try to parse as length
        length = self._parse_length(value)
        return length
    
    def _parse_line_height(self, value: str) -> Optional[float]:
        """Parse line-height value."""
        value = value.strip()
        
        # Unitless number (multiplier)
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try as length
        return self._parse_length(value)
    
    def _normalize_font_weight(self, value: str) -> str:
        """Normalize font weight value."""
        value = value.strip().lower()
        
        # Map keywords to numeric values
        if value in self.FONT_WEIGHT_MAP:
            return self.FONT_WEIGHT_MAP[value]
        
        # Check if it's already numeric
        if value.isdigit() and 100 <= int(value) <= 900:
            return value
        
        return value
    
    def _normalize_color(self, value: str) -> str:
        """Normalize color value."""
        value = value.strip().lower()
        
        # Handle rgb/rgba
        if value.startswith(('rgb(', 'rgba(')):
            return value
        
        # Handle hex colors
        if value.startswith('#'):
            # Expand 3-char hex to 6-char
            if len(value) == 4:
                return '#' + ''.join(c*2 for c in value[1:])
            return value
        
        # Return named colors as-is
        return value
    
    def _extract_background_color(self, value: str) -> Optional[str]:
        """Extract color from background property."""
        # Simple extraction - could be enhanced
        parts = value.split()
        for part in parts:
            if part.startswith('#') or part.startswith('rgb'):
                return self._normalize_color(part)
            # Check for named colors
            if not any(unit in part for unit in self.ABSOLUTE_UNITS | self.RELATIVE_UNITS):
                return part
        
        return None
    
    def _parse_box_property(self, style: Style, prop_type: str, value: str):
        """Parse box property (margin/padding) with multiple values."""
        parts = value.split()
        
        if not parts:
            return
        
        # Convert all parts to lengths
        lengths = []
        for part in parts:
            length = self._parse_length(part)
            if length is not None:
                lengths.append(length)
        
        if not lengths:
            return
        
        # Apply based on number of values (CSS box model)
        if len(lengths) == 1:
            # All sides
            val = lengths[0]
            setattr(style, f'{prop_type}_top', val)
            setattr(style, f'{prop_type}_right', val)
            setattr(style, f'{prop_type}_bottom', val)
            setattr(style, f'{prop_type}_left', val)
        elif len(lengths) == 2:
            # Vertical, horizontal
            vert, horiz = lengths
            setattr(style, f'{prop_type}_top', vert)
            setattr(style, f'{prop_type}_bottom', vert)
            setattr(style, f'{prop_type}_left', horiz)
            setattr(style, f'{prop_type}_right', horiz)
        elif len(lengths) == 3:
            # Top, horizontal, bottom
            top, horiz, bottom = lengths
            setattr(style, f'{prop_type}_top', top)
            setattr(style, f'{prop_type}_bottom', bottom)
            setattr(style, f'{prop_type}_left', horiz)
            setattr(style, f'{prop_type}_right', horiz)
        elif len(lengths) >= 4:
            # Top, right, bottom, left
            setattr(style, f'{prop_type}_top', lengths[0])
            setattr(style, f'{prop_type}_right', lengths[1])
            setattr(style, f'{prop_type}_bottom', lengths[2])
            setattr(style, f'{prop_type}_left', lengths[3])
    
    def merge_styles(self, base: Style, override: Style) -> Style:
        """
        Merge two styles with override taking precedence.
        
        Args:
            base: Base style
            override: Override style
            
        Returns:
            Merged style
        """
        return base.merge(override)