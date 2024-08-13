import re
import warnings
from functools import lru_cache
from typing import Optional, Union, Dict, List, Any

import pandas as pd
from bs4 import BeautifulSoup, Tag, Comment, XMLParsedAsHTMLWarning
from rich import box
from rich.table import Table

from edgar.richtools import repr_rich
from edgar.datatools import table_html_to_dataframe, clean_column_text

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

__all__ = ['DocumentData',
           'HtmlDocument',
           'Block',
           'TextBlock',
           'TableBlock',
           'TextAnalysis',
           'SECLine',
           'table_to_text',
           'html_to_text',
           'get_clean_html', ]

NAMESPACES = {
    "xbrli": 'http://www.xbrl.org/2003/instance',
    "i": 'http://www.xbrl.org/2003/instance',
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "xbrldi": 'http://xbrl.org/2006/xbrldi',
    "xbrll": "http://www.xbrl.org/2003/linkbase",
    "link": 'http://www.xbrl.org/2003/linkbase',
    "xlink": "http://www.w3.org/1999/xlink",
    "dei": "http://xbrl.sec.gov/dei/2023",
    "country": "http://xbrl.sec.gov/country/2023",
    "currency": "http://xbrl.sec.gov/currency/2023",
    "exch": "http://xbrl.sec.gov/exch/2023",
    "naics": "http://xbrl.sec.gov/naics/2023",
    "sic": "http://xbrl.sec.gov/sic/2023",
    "utr": "http://www.xbrl.org/2009/utr",
    "cef": "http://xbrl.sec.gov/cef/2023",
    "srt": "http://fasb.org/srt/2023",
    "ixt": "http://www.xbrl.org/inlineXBRL/transformation/2022-02-16",
    "ixt-sec": "http://www.sec.gov/inlineXBRL/transformation/2015-08-31"
    # Add other namespaces as needed
}


def ns_tag(tag):
    return re.compile(r'(?:' + '|'.join(NAMESPACES.keys()) + r'):' + tag)


class DocumentData:
    """
    Represents the header of an ixbrl document

    Contains the hidden properties, schema references, context and units
    """

    def __init__(self,
                 data: pd.DataFrame,
                 schema_refs: Optional[List[str]] = None,
                 context: Dict[str, Dict[str, Union[str, None]]] = None,
                 units: Dict[str, str] = None):
        self.data = data
        self.context = context or {}
        self.units = units or {}
        self.schema_refs = schema_refs or {}

    def __getitem__(self, item):
        result = self.data[self.data.name == item]
        if not result.empty:
            # Return a dict
            return result.to_dict(orient='records')[0]

    def __contains__(self, item):
        if self.data is None or self.data.empty:
            return False
        return item in self.data.name.to_list()

    def __str__(self):
        return "Inline Xbrl Header"

    def __rich__(self):
        table = Table("", "name", "value",
                      title="Inline Xbrl Document",
                      box=box.SIMPLE)
        for row in self.data.itertuples():
            table.add_row(row.namespace, row.name, row.value)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def parse_headers(cls, ix_header_tags: List[Tag]):
        ix_header = cls.parse_header(ix_header_tags[0])
        if len(ix_header_tags) == 1:
            return ix_header

        for header_tag in ix_header_tags[1:]:
            next_header = cls.parse_header(header_tag)
            dfs = [df for df in [ix_header.data, next_header.data] if df is not None]
            ix_header.properties = pd.concat(dfs) if len(dfs) > 0 else None
            ix_header.schema_refs.extend(next_header.schema_refs)
            ix_header.context.update(next_header.context)
            ix_header.units.update(next_header.units)

        return ix_header

    @classmethod
    def parse_header(cls, ix_header_element: Tag):
        hidden_props, schema_refs, context_map, unit_map = None, [], {}, {}

        resource_tag = ix_header_element.find(ns_tag('resources'))
        if resource_tag:
            # Parse contexts
            context_tags = resource_tag.find_all(ns_tag('context'))
            for ctx in context_tags:
                context_id = ctx.get('id')
                entity_tag = ctx.find(ns_tag('entity'))
                identifier = entity_tag.find(ns_tag('identifier')).text if entity_tag else None

                period_tag = ctx.find(ns_tag('period'))
                instant = period_tag.find(ns_tag('instant'))
                if instant:
                    start = end = instant.text
                else:
                    start = period_tag.find(ns_tag('startdate')).text if period_tag.find(ns_tag('startdate')) else None
                    end = period_tag.find(ns_tag('enddate')).text if period_tag.find(ns_tag('enddate')) else None

                context_map[context_id] = {'identifier': identifier, 'start': start, 'end': end}

                segment = ctx.find(ns_tag('segment'))
                if segment:
                    context_map[context_id]['dimensions'] = str({m.get('dimension'): m.text
                                                                 for m in segment.find_all(ns_tag('explicitMember'))})

            # Parse units
            unit_tags = resource_tag.find_all(ns_tag('unit'))
            for unit in unit_tags:
                unit_id = unit.get('id')
                divide = unit.find(ns_tag('divide'))
                if divide:
                    numerator = divide.find(ns_tag('unitnumerator')).find(ns_tag('measure')).text
                    denominator = divide.find(ns_tag('unitdenominator')).find(ns_tag('measure')).text
                    unit_map[unit_id] = f"{numerator.split(':')[-1]} per {denominator.split(':')[-1]}"
                else:
                    unit_map[unit_id] = unit.find(ns_tag('measure')).text.split(':')[-1]

            # Parse hidden elements
            hidden_elements = ix_header_element.find(ns_tag('hidden'))
            if hidden_elements:
                props = []
                for el in hidden_elements.find_all():
                    name_parts = el.get('name', '').partition(':')
                    prop = {
                        'name': name_parts[2],
                        'namespace': name_parts[0],
                        'value': el.text.strip(),
                        'tag': el.name
                    }
                    ctx_ref = el.get('contextref')
                    if ctx_ref:
                        ctx = context_map.get(ctx_ref, {})
                        prop.update({
                            'start': ctx.get('start'),
                            'end': ctx.get('end'),
                            'identifier': ctx.get('identifier')
                        })
                    props.append(prop)
                hidden_props = pd.DataFrame(props)

        # Parse references
        references = ix_header_element.find(ns_tag('references'))
        if references:
            schema_refs = [s.get('xlink:href') for s in references.find_all() if s.get('xlink:href')]

        ix_header_element.decompose()
        return cls(data=hidden_props, schema_refs=schema_refs, context=context_map, units=unit_map)

    def parse_inline_data(self, start_element: Tag):
        records = []
        inline_tags = ns_tag('nonfraction|nonnumeric|fraction')
        for ix_tag in start_element.find_all(inline_tags):
            if ix_tag.name is None:
                continue

            record = dict(ix_tag.attrs)
            record['tag'] = ix_tag.name
            context_ref = record.get('contextref')
            if context_ref:
                record.update(self.context.get(context_ref, {}))
                record.pop('contextref', None)

            record['value'] = ix_tag.text.strip()
            name_parts = record.get('name', '').partition(':')
            record['namespace'], record['name'] = name_parts[0], name_parts[2]

            unit_ref = record.get('unitref')
            if unit_ref:
                record['unit'] = self.units.get(unit_ref)
                record.pop('unitref', None)

            records.append(record)

        records_df = pd.DataFrame(records)
        self.data = pd.concat([self.data, records_df], ignore_index=True)


INLINE_IXBRL_TAGS = ['ix:nonfraction', 'ix:nonnumeric', 'ix:fraction']


class Block:

    def __init__(self, text: Optional[str], **tags):
        self.text: Optional[str] = text
        self.inline: bool = False
        self.metadata: Dict[str, Any] = tags

    def __contains__(self, item):
        return item in self.text

    def to_markdown(self) -> str:
        return self.text

    def get_text(self):
        return self.text

    def is_empty(self):
        return not self.is_linebreak() and not self.text.strip()

    def is_linebreak(self) -> bool:
        # This block is a line break if it only has '\n'
        return self.text != '' and self.text.strip('\n') == ''

    def __str__(self):
        return "Block"

    def __repr__(self):
        return self.text


class TextBlock(Block):

    def __init__(self, text: str, inline: bool = False, **tags):
        super().__init__(text, **tags)
        self.inline: bool = inline

    @property
    @lru_cache(maxsize=1)
    def num_words(self):
        "return the number of words in this text block"
        if self.is_linebreak() or self.is_empty():
            return 0
        return len(self.text.split(" "))

    @property
    @lru_cache(maxsize=1)
    def is_header(self):
        return is_header(self.text)

    @lru_cache(maxsize=1)
    def analyze(self):
        return TextAnalysis(self.text)

    def __str__(self):
        return "TextBlock"

    def __repr__(self):
        return self.text


class TableBlock(Block):
    """
    Represents an HTML table in the document
    """

    def __init__(self, table_element: Tag, **tag):
        super().__init__(text=None, **tag)
        self.table_element = table_element

    @lru_cache()
    def get_text(self):
        _text = fixup(table_to_text(self.table_element))
        _text = "\n" + _text + "\n"
        return _text

    def to_dataframe(self) -> pd.DataFrame:
        table_df = table_html_to_dataframe(str(self.table_element))
        return table_df

    def to_markdown(self) -> str:
        return self.to_dataframe().to_markdown() + "\n"

    def __str__(self):
        return "TableBlock"

    def __repr__(self):
        return str(self)


item_pattern = r"(?:ITEM|Item)\s+(?:[0-9]{1,2}[A-Z]?\.?|[0-9]{1,2}\.[0-9]{2})"


class HtmlDocument:

    def __init__(self,
                 blocks: List[Block],
                 data: Optional[DocumentData] = None,
                 ):
        assert isinstance(blocks, list), "blocks must be a list of Block objects"
        self.blocks: List[Block] = blocks  # The text blocks
        self.data: Optional[DocumentData] = data  # Any data in the document

    @property
    def text(self) -> str:
        _text = ""

        for i, block in enumerate(self.blocks):
            _text += block.get_text()

        return _text

    @property
    def markdown(self) -> str:
        """Convert the document to markdown"""
        md = ""
        for block in self.blocks:
            line = block.to_markdown()
            if is_header(line):
                md += "\n" + line + "\n"
            else:
                md += line

        return md

    def get_table_blocks(self) -> List[TableBlock]:
        """Get a list of all the table blocks in the document"""
        return [block for block in self.blocks if isinstance(block, TableBlock)]

    @staticmethod
    def _compress_blocks(blocks: List[Block]):
        """
        Create a new block structure with blocks that are only whitespace appended to previous blocks
        For example ... if there are consecutive blocks like so
        'THIS is a block'
        ' '

        the result should be
        'THIS is a block '
        Copy to a new block structure
        """
        compressed_blocks = []
        current_block = None
        for i, block in enumerate(blocks):
            if isinstance(block, TableBlock):
                if current_block:
                    compressed_blocks.append(current_block)
                    current_block = None  # Reset the current block
                compressed_blocks.append(block)
            else:
                if block.text.endswith("\n"):
                    if current_block:
                        if current_block.inline and block.inline:
                            current_block.text += block.text
                            compressed_blocks.append(current_block)
                            current_block = None  # Reset the current block
                        else:
                            compressed_blocks.append(current_block)
                            compressed_blocks.append(block)
                            current_block = None  # Reset the current block
                    else:
                        compressed_blocks.append(block)
                elif block.is_empty():  # Empty blocks get appended to the previous block
                    if not current_block:
                        current_block = block
                    else:
                        current_block.text += block.text
                else:
                    if current_block:
                        # If current is empty assume the inline status of the block
                        if current_block.is_empty():
                            current_block.inline = block.inline
                        current_block.text += block.text
                    else:
                        current_block = block
        # Remember to add the last block
        if current_block and not current_block.is_empty():
            compressed_blocks.append(current_block)

        # Strip the first block
        if compressed_blocks:
            compressed_blocks[0].text = compressed_blocks[0].get_text().lstrip()

        return compressed_blocks

    @classmethod
    def extract_text(cls, start_element: Tag):
        # Remove page numbers
        decompose_page_numbers(start_element)

        # Now find the full text
        blocks: List[Block] = extract_and_format_content(start_element)
        # Compress the blocks
        blocks: List[Block] = HtmlDocument._compress_blocks(blocks)

        return blocks

    @classmethod
    def extract_data(cls, start_element: Tag) -> Optional[DocumentData]:
        header_elements = start_element.find_all('ix:header')
        if len(header_elements) == 0:
            return None
        ixbrl_document: DocumentData = DocumentData.parse_headers(header_elements)
        for header_element in header_elements:
            header_element.decompose()
        ixbrl_document.parse_inline_data(start_element.body)
        return ixbrl_document

    @classmethod
    def get_root(cls, html: str) -> Tag:
        # First check if the html is inside a <DOCUMENT><TEXT> block
        if "<TEXT>" in html[:500]:
            html = get_text_between_tags(html, 'TEXT')

        soup = BeautifulSoup(html, features='lxml')
        # Cleanup the soup before extracting text (including removing comments)
        fixup_soup(soup)
        return soup.find('html')

    @classmethod
    def from_html(cls, html: str, extract_data: bool = False):
        """Create from an html string"""
        # Get the root element
        root: Tag = cls.get_root(html)

        # If the root cannot be located it's not valid HTML
        if not root:
            return None

        # Extract any inline data inside the html
        data = cls.extract_data(root) if extract_data else None

        # Clean the root element .. strip out the header tags, script and style tags, and table of content links
        root = clean_html_root(root)

        # Now extract the text into blocks
        blocks: List[Block] = cls.extract_text(root)

        return cls(blocks=blocks, data=data)

    @staticmethod
    def _render_blocks(blocks: List[Block]) -> str:
        text_ = "".join([block.get_text() for block in blocks])
        return text_.strip()

    def generate_text_chunks(self, ignore_tables: bool = False) -> List[str]:
        for chunk in self.generate_chunks(ignore_tables=ignore_tables):
            yield HtmlDocument._render_blocks(chunk)

    def generate_chunks(self, ignore_tables: bool = False) -> List[List[Block]]:
        current_chunk = []
        accumulating_regular_text = False
        header_detected = False
        item_header_detected = False

        for i, block in enumerate(self.blocks):
            if isinstance(block, TableBlock) or block.metadata.get('element') in ['ol', 'ul']:
                if isinstance(block, TableBlock) and ignore_tables:
                    continue
                if current_chunk:
                    if any(block.text.strip() for block in current_chunk):  # Avoid emitting empty chunks
                        yield current_chunk
                    current_chunk = []
                yield [block]  # Yield TableBlock as its own chunk
                accumulating_regular_text = False
                header_detected = False
                item_header_detected = False
            elif isinstance(block, TextBlock):
                analysis = block.analyze()
                is_regular_text = analysis.is_regular_text

                # Check if the block is an "Item" header
                is_item_header = bool(re.match(item_pattern, block.text))

                if is_item_header:
                    # Yield the current chunk before starting a new one with the "Item" header
                    if current_chunk:
                        if any(block.text.strip() for block in current_chunk):  # Avoid emitting empty chunks
                            yield current_chunk

                    # Initialize the new chunk with the "Item" header
                    current_chunk = [block]

                    # Update flags accordingly
                    item_header_detected = True
                    header_detected = True  # "Item" headers are considered regular headers for flag purposes
                    accumulating_regular_text = False  # Reset since we're starting a new section
                elif analysis.is_header:
                    if current_chunk and not accumulating_regular_text and not item_header_detected:
                        if any(block.text.strip() for block in current_chunk):  # Avoid emitting empty chunks
                            yield current_chunk
                        current_chunk = []
                    header_detected = True
                    accumulating_regular_text = False  # Reset this flag since we found a new header
                    current_chunk.append(block)  # Start accumulating from this header
                    item_header_detected = False  # Reset this as we found a different type of header
                elif is_regular_text and (header_detected or accumulating_regular_text):
                    current_chunk.append(block)
                    accumulating_regular_text = True
                    item_header_detected = False  # Regular text resets the "Item" header detection
                else:
                    if accumulating_regular_text or item_header_detected:
                        if any(block.text.strip() for block in current_chunk):  # Avoid emitting empty chunks
                            yield current_chunk
                        current_chunk = []
                        accumulating_regular_text = False
                        header_detected = False
                        item_header_detected = False
                    current_chunk.append(block)

            # Check to yield the remaining chunk if it's the last block
            if i == len(self.blocks) - 1 and current_chunk:
                if any(block.text.strip() for block in current_chunk):  # Avoid emitting empty chunks
                    yield current_chunk


def extract_and_format_content(element) -> List[Block]:
    """
    Recursively extract and format content from an element,
    applying special formatting to tables and concatenating text for other elements.
    """

    if element.name == 'table':
        table_block = TableBlock(table_element=element, rows=len(element.find_all("tr")))
        return [table_block]
    elif element.name in ['ul', 'ol']:
        return [TextBlock(text=fixup(element.text), element=element.name, text_type='list')]
    else:
        inline = is_inline(element)
        blocks: List[Block] = []
        len_children = len(element.contents)
        for index, child in enumerate(element.children):
            if child.name:
                blocks.extend(extract_and_format_content(child))
                if not inline and len(blocks) > 0 and not isinstance(blocks[-1], TableBlock):
                    # are we at the end of the children?
                    if not blocks[-1].inline or index == len_children - 1:
                        if blocks[-1].text.strip():
                            blocks[-1].text += '\n'
                        else:
                            blocks[-1].text = '\n'
            else:
                stripped_string = replace_inline_newlines(child.string)
                stripped_string = fixup(stripped_string)
                if not stripped_string.strip() and len(blocks) > 0 and not blocks[-1].get_text().strip():
                    if not blocks[-1].get_text().endswith('\n'):  # Don't add a space after a new line
                        blocks[-1].text += stripped_string
                else:
                    blocks.append(TextBlock(stripped_string, inline=inline, element=element.name, text_type='string'))

        return blocks


def table_to_text(table_tag):
    rows = table_tag.find_all('tr')
    col_widths = []
    col_has_content = []

    # Determine the maximum width for each column and identify empty columns
    for row in rows:
        cols = row.find_all(['td', 'th'])
        for i, col in enumerate(cols):
            width = len(col.get_text().strip())
            if len(col_widths) <= i:
                col_widths.append(width)
                col_has_content.append(width > 0)
            else:
                col_widths[i] = max(col_widths[i], width)
                if width > 0:
                    col_has_content[i] = True

    # Create a list of indices for columns that have content
    content_col_indices = [i for i, has_content in enumerate(col_has_content) if has_content]

    # Adjust col_widths to only include columns with content
    col_widths = [col_widths[i] for i in content_col_indices]

    formatted_table = ""
    for index, row in enumerate(rows):
        cols = row.find_all(['td', 'th'])
        # Map cols to their new indices based on content_col_indices, then format
        row_text = []
        for i, col in enumerate(cols):
            if i in content_col_indices:  # Check if column should be included
                new_index = content_col_indices.index(i)  # Get new index for col_widths
                row_text.append(clean_column_text(col.get_text()).ljust(col_widths[new_index]))

        if any([text.strip() for text in row_text]):  # Skip entirely empty rows
            formatted_row = ' | '.join(row_text)
            formatted_table += formatted_row + '\n'
            if index == 0:
                formatted_table += '-+-'.join(['-' * len(text) for text in row_text]) + '\n'

    return formatted_table


def html_to_text(html: str) -> str:
    """Converts HTML to plain text"""
    return HtmlDocument.from_html(html, extract_data=False).text


def html_to_markdown(html: str) -> str:
    """Converts HTML to markdown"""
    return HtmlDocument.from_html(html, extract_data=False).markdown


def decompose_toc_links(start_element: Tag):
    regex = re.compile('Table [Oo]f [cC]ontents')
    toc_tags = start_element.find_all('a', string=regex)
    for toc_tag in toc_tags:
        toc_tag.decompose()


def decompose_page_numbers(start_element: Tag):
    span_tags_with_numbers = start_element.find_all('span', string=re.compile('^\d{1,3}$'))
    sequences = []  # To store the sequences of tags for potential review
    current_sequence = []
    previous_number = None

    for tag in span_tags_with_numbers:
        if not tag.text:
            continue
        number = int(tag.text)
        # Check if the number is sequentially next
        if previous_number is None or number == previous_number + 1:
            current_sequence.append(tag)
        else:
            # If a sequence is broken and the current sequence has more than one element, it's considered valid
            if len(current_sequence) > 1:
                sequences.append(current_sequence)
                # Decompose all tags in the current valid sequence
                for seq_tag in current_sequence:
                    seq_tag.decompose()
            # Start a new sequence
            current_sequence = [tag]
        previous_number = number

    # Check the last sequence
    if len(current_sequence) > 1:
        sequences.append(current_sequence)
        for seq_tag in current_sequence:
            seq_tag.decompose()

    return sequences


def get_text_between_tags(html: str, tag: str, ):
    tag_start = f'<{tag}>'
    tag_end = f'</{tag}>'
    is_header = False
    content = ""

    for line in html.splitlines():
        if line:
            # If line matches header_start, start capturing
            if line.startswith(tag_start):
                is_header = True
                continue  # Skip the current line as it's the opening tag

            # If line matches header_end, stop capturing
            elif line.startswith(tag_end):
                break

            # If within header lines, add to header_content
            elif is_header:
                content += line + '\n'  # Add a newline to preserve original line breaks
    return content


def is_inline(tag):
    # is is navigable string return False
    if not tag.name:
        return False
    # Common inline elements
    inline_elements = {'a', 'span', 'strong', 'em', 'b', 'i', 'u', 'small', 'font', 'big', 'sub', 'sup', 'img', 'label',
                       'input', 'button'}

    # Check if the tag's name is in the list of inline elements
    if tag.name in inline_elements:
        return True

    # #ixbrl tags are inline
    if tag.name.startswith("ix:"):
        return True

    # Check for inline styling
    if tag.has_attr('style'):
        styles = tag['style'].split(';')
        for style in styles:
            if style.strip().lower().startswith('display'):
                property_value = style.split(':')
                if len(property_value) > 1 and property_value[1].strip().lower() == 'inline':
                    return True

    return False


def fixup(text: str):
    # This pattern matches one or more non-breaking space (\xa0) or one or more whitespace characters (\s+)
    text = re.sub(r'\xa0|[^\S\n]+', ' ', text)

    return text


def get_clean_html(html: str) -> Optional[str]:
    """Get a clean version of the html without the header tags, script and style tags, and table of content links.
    """
    root = HtmlDocument.get_root(html)

    # If the root cannot be located it's not valid HTML
    if not root:
        return None

    # Clean the root element
    root = clean_html_root(root)
    return str(root)


def clean_html_root(root: Tag) -> Tag:
    """Clean the root element by removing header tags, script and style tags, and table of content links."""
    # Remove the header tags
    for tag in root.find_all('ix:header'):
        tag.decompose()

    # Remove table of content links
    decompose_toc_links(root)

    # Remove script and style tags
    for tag in root.find_all(['script', 'style']):
        tag.decompose()

    # Remove comments
    for comment in root.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    return root


def replace_inline_newlines(text: str):
    """Replace newlines inside the text container"""
    text = text.replace('\n', ' ')
    return text


def fixup_soup(soup):
    # Find and remove all comments
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()


# List of words that are commonly not capitalized in titles
common_words = {'and', 'or', 'but', 'the', 'a', 'an', 'in', 'with', 'for', 'on', 'at', 'to', 'of', 'by', 'as'}


class SECLine:

    def __init__(self, text):
        self.text = text.strip()  # Remove leading and trailing whitespace
        self.is_header = False
        self.is_empty = False
        self.features = {}
        self.analyze()

    def analyze(self):
        self.set_empty()
        self.set_header()
        self.set_features()

    def set_empty(self):
        if not self.text:
            self.is_empty = True

    def set_header(self):
        if self.is_empty:  # Skip empty lines for header detection
            return
        self.is_header = is_header(self.text)

    def set_features(self):
        # Additional features can be added here
        self.features['word_count'] = len(self.text.split())
        self.features['upper_case'] = self.text.isupper()
        self.features['title_case'] = self.text.istitle()


def is_header(text: str):
    # Remove numerical prefix for enumeration, e.g., "1. ", "I. ", "(1) "
    trimmed_text = re.sub(r'^(\d+\.|\w\.\s|\(\d+\)\s)', '', text)
    if not trimmed_text:
        return False

    # Split the line into words, considering special cases for common words
    words = [word for word in trimmed_text.split() if word.isalpha()]

    # Check if the line is mostly title case, ignoring common words and numerical prefixes
    if words:
        title_case_words = [word for word in words if (word.istitle() or word.lower() in common_words)]
        upper_case_words = [word for word in words if word.isupper()]
        mostly_title_case = len(title_case_words) / len(words) > 0.6  # Threshold for mostly title case
        mostly_upper_case = len(upper_case_words) / len(words) > 0.6

        if mostly_title_case or mostly_upper_case:
            return True
    return False


class TextAnalysis:
    def __init__(self, text):
        # Pre-compute and store these properties to avoid recalculating them for each method call
        words = TextAnalysis._get_alpha_words(text)
        self.num_words = len(words)
        self.num_upper_case_words = len([word for word in words if word.isupper()])
        self.num_title_case_words = len([word for word in words if word.istitle()])

        # Show a preview of the text i.e. first 6 characters followed by ... if longer
        self._text = text[:6] + "..." if len(text) > 6 else text

    @staticmethod
    def _get_alpha_words(text):
        """Removes numerical prefixes and splits the text into alphabetic words."""
        trimmed_text = re.sub(r'[^a-zA-Z0-9\s]+', '', text)
        return [word for word in trimmed_text.split() if word.isalpha()]

    @property
    def is_header(self):
        """Determines if the text is a header based on title or upper case predominance."""
        mostly_title_case = (self.num_title_case_words / self.num_words > 0.6) if self.num_words > 0 else False
        mostly_upper_case = (self.num_upper_case_words / self.num_words > 0.6) if self.num_words > 0 else False
        return mostly_title_case or mostly_upper_case

    @property
    def is_mostly_upper(self):
        """Checks if the majority of the words in the text are in uppercase."""
        return self.num_upper_case_words / self.num_words > 0.6

    @property
    def is_mostly_title_case(self):
        """Checks if the majority of the words in the text are in title case."""
        return self.num_title_case_words / self.num_words > 0.6

    @property
    @lru_cache(maxsize=1)
    def is_regular_text(self):
        return self.num_words > 25

    def __str__(self):
        # Show the first 8 characters of the text
        return f"Text Analysis: {self._text}"
