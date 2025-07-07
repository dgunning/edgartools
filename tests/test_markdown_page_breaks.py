#!/usr/bin/env python3

from edgar.files.html import Document


class TestMarkdownPageBreaks:
    """Dedicated tests for markdown page break functionality"""

    def test_explicit_page_breaks_with_content(self):
        """Test that explicit page breaks work and preserve content"""
        html_content = """
        <html>
        <body>
            <div>Content before first page break</div>
            <p style="page-break-before:always">Content after first page break</p>
            <div>More content</div>
            <hr style="page-break-after:always"/>
            <div>Content after hr page break</div>
        </body>
        </html>
        """
        
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        # Check that we have page breaks and content
        page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
        text_nodes = [node for node in document.nodes if node.type == 'text_block']
        
        assert len(page_break_nodes) >= 1  # At least document start
        assert len(text_nodes) >= 3  # Should have text content
        
        # Test markdown conversion
        markdown = document.to_markdown()
        assert markdown is not None
        
        # Should have both page breaks and content
        assert '{' in markdown and '}' in markdown  # Page break markers
        assert 'Content before first page break' in markdown
        assert 'Content after first page break' in markdown
        assert 'More content' in markdown
        assert 'Content after hr page break' in markdown

    def test_page_div_breaks_with_content(self):
        """Test that page-like divs are detected as page breaks while preserving content"""
        html_content = """
        <html>
        <body>
            <div>Content before page breaks</div>
            <div style="height: 842.4pt; width: 597.6pt; position: relative; overflow: hidden; padding: 0;">
                <div>Page 1 header</div>
                <p>Page 1 paragraph content</p>
                <div>Page 1 footer</div>
            </div>
            <div style="height: 842.4pt; width: 597.6pt; position: relative; overflow: hidden; padding: 0;">
                <div>Page 2 header</div>
                <p>Page 2 paragraph content</p>
                <div>Page 2 footer</div>
            </div>
            <div>Content after page breaks</div>
        </body>
        </html>
        """
        
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        # Check that we have page breaks and content
        page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
        text_nodes = [node for node in document.nodes if node.type == 'text_block']
        
        # Should detect: document_start (page 0) + 2 page divs = 3 page breaks
        assert len(page_break_nodes) == 3
        # Should have multiple text nodes with content (content gets efficiently combined)
        assert len(text_nodes) >= 3
        
        # Test markdown conversion
        markdown = document.to_markdown()
        assert markdown is not None
        
        # Should have both page breaks and content
        page_break_count = markdown.count('{')
        assert page_break_count >= 3  # At least 3 page breaks
        
        # Verify content is preserved
        assert 'Content before page breaks' in markdown
        assert 'Page 1 header' in markdown
        assert 'Page 1 paragraph content' in markdown
        assert 'Page 1 footer' in markdown
        assert 'Page 2 header' in markdown
        assert 'Page 2 paragraph content' in markdown
        assert 'Page 2 footer' in markdown
        assert 'Content after page breaks' in markdown
        


    def test_unilever_like_structure(self):
        """Test a structure similar to the Unilever 20-F file"""
        html_content = """
        <html xmlns="http://www.w3.org/1999/xhtml">
        <body>
            <div style="--justify: justify; --position: absolute; background-color: #FFFFFF; border: 1px solid #CCCC; content-visibility: auto; float: none; font-family: Arial, Sans Serif; font-size: 0; height: 842.4pt; margin: 10px auto 10px auto; overflow: hidden; padding: 0; position: relative; width: 597.6pt; word-wrap: break-word;">
                <div style="left: 0pt; position: var(--position); top: 799.88pt;">
                    <div style="width: 512pt;"></div>
                </div>
                <div style="left: 0pt; position: var(--position); top: 0pt;">
                    <div style="width: 512pt;"></div>
                </div>
                <div>
                    <div style="line-height: 8pt; position: var(--position); top: 113.39pt; width: 597.6pt;">
                        <span style="font-family: 'Arial', sans-serif; font-size: 8pt; font-style: normal; font-weight: normal; left: 69.27pt; position: var(--position); white-space: pre;">
                            Indicate by check mark which basis of accounting the registrant has used to prepare the financial statements included in this filing:
                        </span>
                    </div>
                    <div style="position: var(--position); top: 131.31pt; width: 597.6pt;">
                        <div style="font-size: 0pt; left: 42.67pt; position: var(--position); top: 0pt; width: 512.25pt;">
                            <div>
                                <table style="border-collapse: collapse; display: inline-table; width: 100%;">
                                    <tbody>
                                        <tr style="height: 0;">
                                            <td colspan="1" rowspan="1" style="padding: 0; width: 135pt;"></td>
                                            <td colspan="1" rowspan="1" style="padding: 0; width: 3.75pt;"></td>
                                            <td colspan="1" rowspan="1" style="padding: 0; width: 234.75pt;"></td>
                                        </tr>
                                        <tr style="height: 21.75pt;">
                                            <td colspan="1" rowspan="1" style="font-size: 0; text-align: left; vertical-align: top;">
                                                <div style="left: 0pt; position: var(--position); top: 0pt; width: 135pt;">
                                                    <div>
                                                        <div style="line-height: 9pt; position: var(--position); top: 2.63pt; width: 135pt;">
                                                            <span style="font-family: 'Arial', sans-serif; font-size: 7pt; font-style: normal; font-weight: normal; left: 2.63pt; position: var(--position); text-decoration: none; white-space: pre;">
                                                                U.S. GAAP 
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div style="--justify: justify; --position: absolute; background-color: #FFFFFF; border: 1px solid #CCCC; content-visibility: auto; float: none; font-family: Arial, Sans Serif; font-size: 0; height: 842.4pt; margin: 10px auto 10px auto; overflow: hidden; padding: 0; position: relative; width: 597.6pt; word-wrap: break-word;">
                <div style="left: 0pt; position: var(--position); top: 799.88pt;">
                    <div style="width: 512pt;"></div>
                </div>
                <div>
                    <div style="line-height: 8pt; position: var(--position); top: 50pt; width: 597.6pt;">
                        <span style="font-family: 'Arial', sans-serif; font-size: 12pt; font-weight: bold; left: 200pt; position: var(--position);">
                            UNILEVER PLC
                        </span>
                    </div>
                    <div style="line-height: 8pt; position: var(--position); top: 100pt; width: 597.6pt;">
                        <span style="font-family: 'Arial', sans-serif; font-size: 10pt; left: 50pt; position: var(--position);">
                            Annual Report on Form 20-F for the fiscal year ended December 31, 2023
                        </span>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        # Check that we have page breaks and content
        page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
        text_nodes = [node for node in document.nodes if node.type == 'text_block']
        table_nodes = [node for node in document.nodes if node.type == 'table']
        

        
        # Should detect: 2 page divs (no document_start needed since first element is a page div) = 2 page breaks
        assert len(page_break_nodes) == 2
        # Should have content nodes - at least some text and/or tables
        assert len(text_nodes) + len(table_nodes) >= 2
        
        # Test markdown conversion
        markdown = document.to_markdown()
        assert markdown is not None
        
        # Should have both page breaks and content
        page_break_count = markdown.count('{')
        assert page_break_count >= 2
        
        # Verify some content is preserved
        content_found = any(phrase in markdown for phrase in [
            'accounting', 'registrant', 'financial statements', 'UNILEVER', 'Annual Report', 'Form 20-F'
        ])
        assert content_found, f"Expected content not found in markdown: {markdown[:500]}..."
        


    def test_page_break_detection_with_page_divs(self):
        """Test that div elements with page-like dimensions are detected as page breaks"""
        test_html = """
        <html>
        <body>
            <div>Content before page breaks</div>
            <div style="height: 842.4pt; width: 597.6pt; position: relative; overflow: hidden; padding: 0;">
                <div>Page 1 content</div>
            </div>
            <div style="height: 842.4pt; width: 597.6pt; position: relative; overflow: hidden; padding: 0;">
                <div>Page 2 content</div>
            </div>
            <div style="height: 792pt; width: 612pt; position: absolute; overflow: hidden; padding: 0;">
                <div>Page 3 content (Letter size)</div>
            </div>
            <div style="height: 100px; width: 200px; position: relative;">
                <div>Not a page (wrong dimensions)</div>
            </div>
            <div>Content after page breaks</div>
        </body>
        </html>
        """
        
        # Test with page breaks enabled
        document = Document.parse(test_html, include_page_breaks=True)
        assert document is not None
        
        # Count page break nodes
        page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
        
        # Should detect: 
        # - page 0 (document start - content before first page div)
        # - page 1 (first page-like div - A4: 842.4pt x 597.6pt)
        # - page 2 (second page-like div - A4: 842.4pt x 597.6pt)  
        # - page 3 (third page-like div - Letter: 792pt x 612pt)
        # Total = 4 page breaks
        assert len(page_break_nodes) == 4
        
        # Check that page numbers are sequential starting from 0
        page_numbers = [node.page_number for node in page_break_nodes]
        expected_numbers = [0, 1, 2, 3]
        assert page_numbers == expected_numbers
        
        # Check that the page breaks have the correct source elements
        sources = [node.metadata.get('source_element', 'unknown') for node in page_break_nodes]
        assert sources[0] == 'document_start'  # Document start page break
        assert sources[1] == 'div'  # First page div
        assert sources[2] == 'div'  # Second page div  
        assert sources[3] == 'div'  # Third page div
        
        # Verify content is preserved
        markdown = document.to_markdown()
        assert 'Content before page breaks' in markdown
        assert 'Page 1 content' in markdown
        assert 'Page 2 content' in markdown
        assert 'Page 3 content (Letter size)' in markdown
        assert 'Not a page (wrong dimensions)' in markdown  # This should not be treated as page break
        assert 'Content after page breaks' in markdown
        


    def test_mixed_page_breaks(self):
        """Test mixing explicit page breaks with page divs"""
        html_content = """
        <html>
        <body>
            <div>Initial content</div>
            <p style="page-break-before:always">After explicit break</p>
            <div style="height: 842.4pt; width: 597.6pt; position: relative; overflow: hidden;">
                <div>Page div content</div>
            </div>
            <hr style="page-break-after:always"/>
            <div>Final content</div>
        </body>
        </html>
        """
        
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        markdown = document.to_markdown()
        assert markdown is not None
        
        # Should have multiple page breaks and all content
        page_break_count = markdown.count('{')
        assert page_break_count >= 4  # document_start + explicit + page div + hr
        
        assert 'Initial content' in markdown
        assert 'After explicit break' in markdown
        assert 'Page div content' in markdown
        assert 'Final content' in markdown
        

    def test_brpf_page_break_detection(self):
        """Test that BRPFPageBreak elements (nested page breaks) are detected correctly"""
        html_content = """
        <html>
        <body>
            <div>Content before page break</div>
            <div class="BRPFPageBreakArea" style="clear: both; margin-top: 10pt; margin-bottom: 10pt;">
                <div class="BRPFPageBreak" style="page-break-after: always;">
                    <hr style="border-width: 0px; clear: both; margin: 4px 0px; width: 100%; height: 2px; color: #000000; background-color: #000000;">
                </div>
            </div>
            <div>Content after first page break</div>
            <div class="BRPFPageBreakArea" style="clear: both; margin-top: 10pt; margin-bottom: 10pt;">
                <div class="BRPFPageBreak" style="page-break-after: always;">
                    <hr style="border-width: 0px; clear: both; margin: 4px 0px; width: 100%; height: 2px; color: #000000; background-color: #000000;">
                </div>
            </div>
            <div>Content after second page break</div>
        </body>
        </html>
        """
        
        document = Document.parse(html_content, include_page_breaks=True)
        assert document is not None
        
        # Check that we have page breaks and content
        page_break_nodes = [node for node in document.nodes if node.type == 'page_break']
        text_nodes = [node for node in document.nodes if node.type == 'text_block']
        
        # Should detect: document_start (page 0) + 2 BRPFPageBreak elements = 3 page breaks
        assert len(page_break_nodes) == 3
        assert len(text_nodes) >= 3  # Should have content nodes
        
        # Check page numbering
        page_numbers = [node.page_number for node in page_break_nodes]
        assert page_numbers == [0, 1, 2]
        
        # Test markdown conversion
        markdown = document.to_markdown()
        assert markdown is not None
        
        # Should have 3 page break markers
        page_break_count = markdown.count('{')
        assert page_break_count == 3
        
        # Verify content is preserved
        assert 'Content before page break' in markdown
        assert 'Content after first page break' in markdown
        assert 'Content after second page break' in markdown


 