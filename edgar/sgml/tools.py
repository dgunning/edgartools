import re
__all__ = ['extract_text_between_tags']

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
    Extract content between specified uppercase tags, handling nested tags.
    If no tag specified, returns innermost content that has no tags.

    Args:
        content: Raw content containing tagged sections
        outer_tag: Optional specific tag to extract from (e.g. 'XBRL', 'TEXT')

    Returns:
        str: Content between the specified tags, or innermost content if no tag specified
    """
    # Find all opening and closing tags
    tag_pattern = r'<([A-Z][A-Z0-9]*)>|</([A-Z][A-Z0-9]*)>'
    tags = [(m.group(1) or m.group(2), m.start(), m.end(), bool(m.group(1)))
            for m in re.finditer(tag_pattern, content)]

    if not tags:
        return content

    # Stack to track nested tags
    stack = []
    tag_contents = {}

    for tag, start, end, is_opening in tags:
        if is_opening:
            stack.append((tag, start, end))
        elif stack and stack[-1][0] == tag:
            # Found matching closing tag
            open_tag, open_start, open_end = stack.pop()
            # Extract content between tags
            content_between = content[open_end:start]
            # Check if this content has any tags in it
            has_nested_tags = bool(re.search(tag_pattern, content_between))
            tag_contents[open_tag] = {
                'content': content_between,
                'has_nested': has_nested_tags
            }

    if outer_tag:
        return tag_contents.get(outer_tag, {}).get('content', '')

    # If no specific tag requested, return first content without nested tags
    for tag_info in tag_contents.values():
        if not tag_info['has_nested']:
            return tag_info['content']

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