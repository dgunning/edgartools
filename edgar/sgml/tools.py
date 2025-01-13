
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
