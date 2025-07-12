"""Tests for page break detection functionality."""

import pytest
from bs4 import BeautifulSoup
from edgar.files.page_breaks import (
    PageBreakDetector,
    detect_page_breaks,
    mark_page_breaks
)
from edgar.files.html import Document
from edgar.files.markdown import to_markdown


class TestPageBreakDetector:
    """Test the PageBreakDetector class."""
    
    def test_css_page_break_detection(self):
        """Test detection of CSS page break properties."""
        html = """
        <div>
            <p style="page-break-before:always">Page 1</p>
            <p style="page-break-after:always">Page 2</p>
            <div style="page-break-before: always">Page 3</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        page_breaks = PageBreakDetector.find_page_breaks(soup)
        
        assert len(page_breaks) == 3
        assert page_breaks[0]['element'] == 'p'
        assert page_breaks[1]['element'] == 'p'
        assert page_breaks[2]['element'] == 'div'
        assert 'page-break-before:always' in page_breaks[0]['selector']
        assert 'page-break-after:always' in page_breaks[1]['selector']
    
    def test_class_based_page_break_detection(self):
        """Test detection of class-based page breaks."""
        html = """
        <div>
            <div class="BRPFPageBreak">Page 1</div>
            <div class="pagebreak">Page 2</div>
            <div class="page-break">Page 3</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        page_breaks = PageBreakDetector.find_page_breaks(soup)
        
        assert len(page_breaks) == 3
        assert all(pb['element'] == 'div' for pb in page_breaks)
        assert 'BRPFPageBreak' in page_breaks[0]['selector']
        assert 'pagebreak' in page_breaks[1]['selector']
        assert 'page-break' in page_breaks[2]['selector']
    
    def test_hr_page_break_detection(self):
        """Test detection of HR elements with page break styling."""
        html = """
        <div>
            <hr style="height:3px">
            <hr style="height: 3px">
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        page_breaks = PageBreakDetector.find_page_breaks(soup)
        
        assert len(page_breaks) == 2
        assert all(pb['element'] == 'hr' for pb in page_breaks)
        assert 'height:3px' in page_breaks[0]['selector']
    
    def test_page_like_div_detection(self):
        """Test detection of divs with page-like dimensions."""
        html = """
        <div>
            <div style="height:842.4pt; width:597.6pt; position:relative">Page 1</div>
            <div style="height:792pt; width:612pt; overflow:hidden">Page 2</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        page_breaks = PageBreakDetector.find_page_breaks(soup)
        
        assert len(page_breaks) == 2
        assert all(pb['element'] == 'div' for pb in page_breaks)
        assert all(pb['is_page_div'] for pb in page_breaks)
        assert '842.4pt' in page_breaks[0]['style']
        assert '792pt' in page_breaks[1]['style']
    
    def test_is_page_like_div(self):
        """Test the _is_page_like_div method."""
        # Valid page-like div
        style1 = "height:842.4pt; width:597.6pt; position:relative"
        assert PageBreakDetector._is_page_like_div(style1) is True
        
        # Valid page-like div with overflow
        style2 = "height:792pt; width:612pt; overflow:hidden"
        assert PageBreakDetector._is_page_like_div(style2) is True
        
        # Invalid - missing position/overflow
        style3 = "height:842.4pt; width:597.6pt"
        assert PageBreakDetector._is_page_like_div(style3) is False
        
        # Invalid - wrong dimensions
        style4 = "height:100px; width:200px; position:relative"
        assert PageBreakDetector._is_page_like_div(style4) is False


class TestPageBreakFunctions:
    """Test the public page break detection functions."""
    
    def test_detect_page_breaks(self):
        """Test the detect_page_breaks function."""
        html = """
        <div>
            <p style="page-break-before:always">Page 1</p>
            <div class="pagebreak">Page 2</div>
        </div>
        """
        page_breaks = detect_page_breaks(html)
        
        assert len(page_breaks) == 2
        assert page_breaks[0]['element'] == 'p'
        assert page_breaks[1]['element'] == 'div'
    
    def test_mark_page_breaks(self):
        """Test the mark_page_breaks function."""
        html = """
        <div>
            <p style="page-break-before:always">Page 1</p>
            <div class="pagebreak">Page 2</div>
        </div>
        """
        marked_html = mark_page_breaks(html)
        
        # Check that the _is_page_break attribute was added
        soup = BeautifulSoup(marked_html, 'html.parser')
        page_break_elements = soup.find_all(attrs={'_is_page_break': 'true'})
        assert len(page_break_elements) == 2
    

class TestStartPageNumber:
    """Test the start_page_number functionality."""
    
    def test_start_page_number_functionality(self):
        """Test that start_page_number parameter correctly offsets page break numbers"""
        html_content = """
        <html><body>
            <p>Page 1 content</p>
            <p style="page-break-before:always">Page 2 content</p>
            <p>More page 2 content</p>
            <p style="page-break-before:always">Page 3 content</p>
        </body></html>
        """
        
        # Test with default start_page_number (0)
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        markdown_default = document.to_markdown()
        assert "{0}------------------------------------------------" in markdown_default
        assert "{1}------------------------------------------------" in markdown_default
        assert "{2}------------------------------------------------" in markdown_default
        
        # Test with start_page_number = 5
        markdown_offset = document.to_markdown(start_page_number=5)
        assert "{5}------------------------------------------------" in markdown_offset
        assert "{6}------------------------------------------------" in markdown_offset
        assert "{7}------------------------------------------------" in markdown_offset
        
        # Test with start_page_number = 10
        markdown_offset_10 = document.to_markdown(start_page_number=10)
        assert "{10}------------------------------------------------" in markdown_offset_10
        assert "{11}------------------------------------------------" in markdown_offset_10
        assert "{12}------------------------------------------------" in markdown_offset_10
        
        # Verify that the original page numbers are not in the offset output
        assert "{0}------------------------------------------------" not in markdown_offset
        assert "{1}------------------------------------------------" not in markdown_offset
        assert "{2}------------------------------------------------" not in markdown_offset

    def test_to_markdown_function_with_start_page_number(self):
        """Test the to_markdown function with start_page_number parameter"""
        html_content = """
        <html><body>
            <p>Page 1 content</p>
            <p style="page-break-before:always">Page 2 content</p>
        </body></html>
        """
        
        # Test with start_page_number = 3
        markdown = to_markdown(html_content, include_page_breaks=True, start_page_number=3)
        assert markdown is not None
        assert "{3}------------------------------------------------" in markdown
        assert "{4}------------------------------------------------" in markdown
        
        # Test with start_page_number = 0 (default)
        markdown_default = to_markdown(html_content, include_page_breaks=True)
        assert markdown_default is not None
        assert "{0}------------------------------------------------" in markdown_default
        assert "{1}------------------------------------------------" in markdown_default


class TestFilingAndAttachmentMarkdown:
    """Test the start_page_number functionality in Filing and Attachment classes."""
    
    def test_filing_markdown_with_start_page_number(self):
        """Test that Filing.markdown() supports start_page_number parameter"""
        from edgar import Filing
        
        # Create a mock filing with HTML content
        filing = Filing(
            cik=12345,
            company="Test Company",
            form="10-K",
            filing_date="2023-01-01",
            accession_no="0001234567-23-000001"
        )
        
        # Mock the html() method to return test content
        html_content = """
        <html><body>
            <p>Page 1 content</p>
            <p style="page-break-before:always">Page 2 content</p>
        </body></html>
        """
        
        # Patch the html method to return our test content
        import unittest.mock
        with unittest.mock.patch.object(filing, 'html', return_value=html_content):
            # Test with start_page_number = 5
            markdown = filing.markdown(include_page_breaks=True, start_page_number=5)
            assert markdown is not None
            assert "{5}------------------------------------------------" in markdown
            assert "{6}------------------------------------------------" in markdown
            
            # Test with start_page_number = 0 (default)
            markdown_default = filing.markdown(include_page_breaks=True)
            assert markdown_default is not None
            assert "{0}------------------------------------------------" in markdown_default
            assert "{1}------------------------------------------------" in markdown_default
    
    def test_attachment_markdown_with_start_page_number(self):
        """Test that Attachment.markdown() supports start_page_number parameter"""
        from edgar.attachments import Attachment
        
        # Create a mock attachment with HTML content
        attachment = Attachment(
            sequence_number="1",
            description="Test Document",
            document="test.html",
            ixbrl=False,
            path="/test/path",
            document_type="HTML",
            size=1000
        )
        
        # Mock the content property to return test HTML
        html_content = """
        <html><body>
            <p>Page 1 content</p>
            <p style="page-break-before:always">Page 2 content</p>
        </body></html>
        """
        
        # Patch the content property and is_html method
        import unittest.mock
        with unittest.mock.patch.object(attachment, 'content', property(lambda self: html_content)), \
             unittest.mock.patch.object(attachment, 'is_html', return_value=True):
            
            # Test with start_page_number = 10
            markdown = attachment.markdown(include_page_breaks=True, start_page_number=10)
            assert markdown is not None
            assert "{10}------------------------------------------------" in markdown
            assert "{11}------------------------------------------------" in markdown
            
            # Test with start_page_number = 0 (default)
            markdown_default = attachment.markdown(include_page_breaks=True)
            assert markdown_default is not None
            assert "{0}------------------------------------------------" in markdown_default
            assert "{1}------------------------------------------------" in markdown_default
    
    def test_attachments_markdown_with_start_page_number(self):
        """Test that Attachments.markdown() supports start_page_number parameter"""
        from edgar.attachments import Attachments, Attachment
        
        # Create mock attachments
        attachment1 = Attachment(
            sequence_number="1",
            description="Test Document 1",
            document="test1.html",
            ixbrl=False,
            path="/test/path1",
            document_type="HTML",
            size=1000
        )
        
        attachment2 = Attachment(
            sequence_number="2",
            description="Test Document 2",
            document="test2.html",
            ixbrl=False,
            path="/test/path2",
            document_type="HTML",
            size=1000
        )
        
        html_content = """
        <html><body>
            <p>Page 1 content</p>
            <p style="page-break-before:always">Page 2 content</p>
        </body></html>
        """
        
        # Create Attachments instance
        attachments = Attachments(
            document_files=[attachment1, attachment2],
            data_files=None,
            primary_documents=[attachment1]
        )
        
        # Patch the content property and is_html method for both attachments
        import unittest.mock
        with unittest.mock.patch.object(attachment1, 'content', property(lambda self: html_content)), \
             unittest.mock.patch.object(attachment1, 'is_html', return_value=True), \
             unittest.mock.patch.object(attachment2, 'content', property(lambda self: html_content)), \
             unittest.mock.patch.object(attachment2, 'is_html', return_value=True):
            
            # Test with start_page_number = 7
            markdown_dict = attachments.markdown(include_page_breaks=True, start_page_number=7)
            assert len(markdown_dict) == 2
            assert "test1.html" in markdown_dict
            assert "test2.html" in markdown_dict
            
            # Check that both documents have the correct page numbering
            for content in markdown_dict.values():
                assert "{7}------------------------------------------------" in content
                assert "{8}------------------------------------------------" in content
            
            # Test with start_page_number = 0 (default)
            markdown_dict_default = attachments.markdown(include_page_breaks=True)
            assert len(markdown_dict_default) == 2
            
            for content in markdown_dict_default.values():
                assert "{0}------------------------------------------------" in content
                assert "{1}------------------------------------------------" in content

if __name__ == '__main__':
    pytest.main([__file__]) 