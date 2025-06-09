import re
import base64

__all__ = ['extract_text_between_tags', 'get_content_between_tags', 'strip_tags', 'is_xml', 'decode_uu']

def extract_text_between_tags(content: str, tag: str) -> str:
    """
    Extracts text from provided content between the specified HTML/XML tags.

    :param content: The text content to search through
    :param tag: The tag to extract the content from
    :return: The extracted text between the tags
    """
    tag_start = f'<{tag}>'
    tag_end = f'</{tag}>'
    is_tag = False
    extracted_content = ""

    for line in content.splitlines():
        if line.startswith(tag_start):
            is_tag = True
            continue  # Skip the start tag line
        elif line.startswith(tag_end):
            break  # Stop reading if end tag is found
        elif is_tag:
            extracted_content += line + '\n'  # Add line to result

    return extracted_content.strip()


def get_content_between_tags(content: str, outer_tag: str = None) -> str:
    """
    Extract content between specified tags, starting from most nested tags.

    Args:
        content: Raw content containing tagged sections
        outer_tag: Optional specific tag to extract from (e.g. 'XBRL', 'TEXT')

    Returns:
        str: Content between the specified tags, or innermost content if no tag specified
    """
    known_tags = ["PDF", "XBRL", "XML", "TEXT"]  # Ordered from most nested to least nested

    if outer_tag:
        # Extract content for specific tag
        pattern = f'<{outer_tag}>(.*?)</{outer_tag}>'
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ''

    # If no tag specified, find the first matching tag from most nested to least
    for tag in known_tags:
        pattern = f'<{tag}>(.*?)</{tag}>'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

    return ''


def strip_tags(text: str, start_tag: str, end_tag: str) -> str:
    """Strip XML/HTML tags from text if present."""
    if text.startswith(start_tag) and text.endswith(end_tag):
        return text[len(start_tag):-len(end_tag)].strip()
    return text

def is_xml(filename: str) -> bool:
    """Check if a file is XML based on the file extension.
    .xsd, .xml, .xbrl
    """
    return filename.lower().endswith(('.xsd', '.xml', '.xbrl'))


def decode_uu(uu_content):
    lines = uu_content.split('\n')
    data = ''
    for line in lines[1:]:  # Skip "begin" line
        if line.startswith('`') or line.startswith('end'):
            break
        # Convert UU to base64 padding
        data += ''.join([chr(((ord(c) - 32) & 63) + 32) for c in line.strip()])

    return base64.b64decode(data)