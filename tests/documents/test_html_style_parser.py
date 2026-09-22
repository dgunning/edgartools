"""
Tests for CSS style parser.
"""

import pytest
from edgar.documents.strategies.style_parser import StyleParser
from edgar.documents.types import Style


class TestStyleParser:
    """Test CSS style parsing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = StyleParser()
    
    def test_parse_empty_style(self):
        """Test parsing empty style string."""
        style = self.parser.parse("")
        assert isinstance(style, Style)
        assert style.font_size is None
        assert style.color is None
    
    def test_parse_font_properties(self):
        """Test parsing font properties."""
        style_str = "font-size: 14px; font-weight: bold; font-style: italic"
        style = self.parser.parse(style_str)
        
        assert style.font_size == 14.0
        assert style.font_weight == "700"  # bold -> 700
        assert style.font_style == "italic"
    
    def test_parse_text_properties(self):
        """Test parsing text properties."""
        style_str = "text-align: center; text-decoration: underline; color: red"
        style = self.parser.parse(style_str)
        
        assert style.text_align == "center"
        assert style.text_decoration == "underline"
        assert style.color == "red"
    
    def test_parse_spacing_properties(self):
        """Test parsing margin and padding."""
        # Single value
        style = self.parser.parse("margin: 10px")
        assert style.margin_top == 10.0
        assert style.margin_right == 10.0
        assert style.margin_bottom == 10.0
        assert style.margin_left == 10.0
        
        # Two values (vertical, horizontal)
        style = self.parser.parse("padding: 10px 20px")
        assert style.padding_top == 10.0
        assert style.padding_right == 20.0
        assert style.padding_bottom == 10.0
        assert style.padding_left == 20.0
        
        # Four values
        style = self.parser.parse("margin: 10px 20px 30px 40px")
        assert style.margin_top == 10.0
        assert style.margin_right == 20.0
        assert style.margin_bottom == 30.0
        assert style.margin_left == 40.0
    
    def test_parse_units(self):
        """Test parsing different CSS units."""
        # Pixels (default)
        style = self.parser.parse("font-size: 16px")
        assert style.font_size == 16.0
        
        # Points
        style = self.parser.parse("font-size: 12pt")
        assert style.font_size == pytest.approx(16.0, rel=0.1)  # 12pt ≈ 16px
        
        # Em units
        style = self.parser.parse("font-size: 1.5em")
        assert style.font_size == 24.0  # 1.5 * 16px base
        
        # Percentages (returns None as needs context)
        style = self.parser.parse("width: 50%")
        assert style.width == "50%"
    
    def test_parse_colors(self):
        """Test parsing color values."""
        # Named colors
        style = self.parser.parse("color: red; background-color: blue")
        assert style.color == "red"
        assert style.background_color == "blue"
        
        # Hex colors
        style = self.parser.parse("color: #ff0000")
        assert style.color == "#ff0000"
        
        # Short hex expansion
        style = self.parser.parse("color: #f00")
        assert style.color == "#ff0000"
        
        # RGB colors
        style = self.parser.parse("color: rgb(255, 0, 0)")
        assert style.color == "rgb(255, 0, 0)"
    
    def test_parse_display_properties(self):
        """Test parsing display properties."""
        style = self.parser.parse("display: none; width: 100px; height: 50px")
        assert style.display == "none"
        assert style.width == 100.0
        assert style.height == 50.0
    
    def test_parse_line_height(self):
        """Test parsing line-height."""
        # Unitless multiplier
        style = self.parser.parse("line-height: 1.5")
        assert style.line_height == 1.5
        
        # With units
        style = self.parser.parse("line-height: 20px")
        assert style.line_height == 20.0
    
    def test_parse_complex_style(self):
        """Test parsing complex style string."""
        style_str = """
            font-size: 14px;
            font-weight: bold;
            color: #333;
            margin: 10px 20px;
            padding-left: 15px;
            text-align: justify;
            line-height: 1.6;
            background: white url(image.png) no-repeat;
        """
        
        style = self.parser.parse(style_str)
        
        assert style.font_size == 14.0
        assert style.font_weight == "700"
        assert style.color == "#333333"
        assert style.margin_top == 10.0
        assert style.margin_right == 20.0
        assert style.padding_left == 15.0
        assert style.text_align == "justify"
        assert style.line_height == 1.6
        assert style.background_color == "white"
    
    def test_merge_styles(self):
        """Test merging styles."""
        base = self.parser.parse("font-size: 14px; color: black")
        override = self.parser.parse("color: red; font-weight: bold")
        
        merged = self.parser.merge_styles(base, override)
        
        assert merged.font_size == 14.0  # From base
        assert merged.color == "red"      # From override
        assert merged.font_weight == "700"  # From override
    
    def test_malformed_styles(self):
        """Test handling of malformed styles."""
        # Missing value
        style = self.parser.parse("color: ; font-size: 14px")
        assert style.color is None
        assert style.font_size == 14.0
        
        # Missing colon
        style = self.parser.parse("color red; font-size: 14px")
        assert style.color is None
        assert style.font_size == 14.0
        
        # Invalid unit
        style = self.parser.parse("font-size: 14xx")
        assert style.font_size is None
    
    def test_style_caching(self):
        """Test that style parsing is cached."""
        style_str = "font-size: 16px; color: blue"
        
        # Parse twice
        style1 = self.parser.parse(style_str)
        style2 = self.parser.parse(style_str)
        
        # Should return same object from cache
        # Check cache stats
        cache_stats = self.parser._cache.stats
        assert cache_stats.hits > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])