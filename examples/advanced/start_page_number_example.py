#!/usr/bin/env python3
"""
Example demonstrating the start_page_number functionality for page break markers.

This example shows how to use the start_page_number parameter to control
the starting page number in markdown output with page breaks.
"""

from edgar.files.markdown import to_markdown


def main():
    # Sample HTML content with page breaks
    html_content = """
    <html><body>
        <p>This is the first page of content.</p>
        <p>More content on page 1.</p>
        
        <p style="page-break-before:always">This starts page 2.</p>
        <p>More content on page 2.</p>
        
        <p style="page-break-before:always">This starts page 3.</p>
        <p>Final content on page 3.</p>
    </body></html>
    """
    
    print("=== Default Page Numbering (starting at 0) ===")
    markdown_default = to_markdown(html_content, include_page_breaks=True)
    print(markdown_default)
    print()
    
    print("=== Page Numbering Starting at 1 ===")
    markdown_start_1 = to_markdown(html_content, include_page_breaks=True, start_page_number=1)
    print(markdown_start_1)
    print()
    
    print("=== Page Numbering Starting at 5 ===")
    markdown_start_5 = to_markdown(html_content, include_page_breaks=True, start_page_number=5)
    print(markdown_start_5)
    print()
    
    print("=== Page Numbering Starting at 10 ===")
    markdown_start_10 = to_markdown(html_content, include_page_breaks=True, start_page_number=10)
    print(markdown_start_10)
    print()
    
    # Show the difference in page numbers
    print("=== Summary ===")
    print("Default (start=0): Pages 0, 1, 2")
    print("Start=1:          Pages 1, 2, 3")
    print("Start=5:          Pages 5, 6, 7")
    print("Start=10:         Pages 10, 11, 12")


if __name__ == "__main__":
    main() 