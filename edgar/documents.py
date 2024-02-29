import re
from typing import Optional, Tuple, Union, Dict, List

import pandas as pd
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

import warnings
from rich import box
from rich.table import Table

from edgar._rich import repr_rich
from edgar._xml import child_text

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


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
        for row in self.properties.itertuples():
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
        """
        Parse the Ixbrl Header
        <ix:header>

        </ix:header>
        """

        hidden_props, schema_refs, context_map, unit_map = None, None, None, None

        # Read the document information

        def get_context(context_ref: str) -> Optional[Tuple[str, str, Union[str, None]]]:
            """Get the value of the context for that context id"""
            context = context_map.get(context_ref)
            if context:
                start_date = context.get('start')
                end_date = context.get('end')
                identifier: Optional[str] = context.get('identifier')
                return start_date, end_date, identifier

        # Read the context
        resource_tag = ix_header_element.find('ix:resources')
        if resource_tag:
            context_map = dict()
            context_tags = resource_tag.find_all('xbrli:context')
            for ctx in context_tags:
                context_id = ctx.attrs['id']
                # Entity identifier
                entity_tag = ctx.find('xbrli:entity')
                context_map[context_id] = {'identifier': child_text(entity_tag, 'xbrli:identifier')}

                # Period
                period_tag = ctx.find('xbrli:period')

                instant = child_text(period_tag, 'xbrli:instant')
                if instant:
                    context_map[context_id]['start'] = instant
                    context_map[context_id]['end'] = instant
                else:
                    context_map[context_id]['start'] = child_text(period_tag, 'xbrli:startdate')
                    context_map[context_id]['end'] = child_text(period_tag, 'xbrli:enddate')
                # Parse segments
                segment = ctx.find('segment')
                if segment:
                    context_map[context_id]['dimensions'] = str({m.attrs['dimension']: m.text
                                                                 for m in
                                                                 segment.find_all('xbrldi:explicitdember')})
            # Read the units
            unit_map = dict()
            unit_tags = resource_tag.find_all('xbrli:unit')
            for unit in unit_tags:
                unit_id = unit.attrs['id']
                divide = unit.find('xbrli:divide')
                if divide:
                    numerator = child_text(divide.find('xbrli:unitnumerator'), 'xbrli:measure') or ''
                    denominator = child_text(divide.find('xbrli:unitdenominator'), 'xbrli:measure') or ''
                    # Strip the prefix
                    if ":" in numerator:
                        numerator = numerator.partition(":")[-1]
                    if ":" in denominator:
                        denominator = denominator.partition(":")[-1]
                    unit_map[unit_id] = f"{numerator} per {denominator}"
                else:
                    unit_map[unit_id] = child_text(unit, 'xbrli:measure') or ''

            # Read the hidden elements inti properties
            hidden_elements = ix_header_element.find('ix:hidden')
            hidden_props = None
            if hidden_elements:
                props = []

                els = hidden_elements.find_all()

                for el in els:
                    prop = dict()

                    name_parts = el.get('name', '').partition(":")
                    prop['name'] = name_parts[2]
                    prop['namespace'] = name_parts[0]
                    prop['value'] = el.text.strip()
                    prop['tag'] = el.name
                    if 'contextref' in el.attrs or 'unitref' in el.attrs:
                        ctx_ref = el.attrs.get('contextref')
                        start, end, identifier = get_context(ctx_ref)
                        prop['start'] = start
                        prop['end'] = end
                        prop['identifier'] = identifier

                    props.append(prop)
                hidden_props = pd.DataFrame(props)
        # Read the references
        references = ix_header_element.find('ix:references')
        if references:
            schema_ref_tags = references.find_all()
            schema_refs = [s.attrs.get('xlink:href')
                           for s in schema_ref_tags
                           if 'xlink:href' in s.attrs]

        # Now decompose (remove) the header from the text
        ix_header_element.decompose()
        # Create the header
        return cls(data=hidden_props,
                   schema_refs=schema_refs,
                   context=context_map,
                   units=unit_map)

    def parse_inline_data(self, start_element: Tag):
        records = []

        for ix_tag in start_element.find_all(INLINE_IXBRL_TAGS):

            # Weird case where the tag has no name
            if ix_tag.name is None:
                continue

            # Create a new record
            record = dict(ix_tag.attrs)
            record['tag'] = ix_tag.name
            # Get the context
            context_ref = record.get('contextref')

            if context_ref:
                record_context = self.context.get(context_ref, {})
                record.update(record_context)
                record.pop('contextref')

            record['value'] = ix_tag.text.strip()

            name_parts = record.get('name', '').partition(":")
            record['namespace'] = name_parts[0]
            record['name'] = name_parts[2]

            # Get the unit
            unit_ref = record.get('unitref')
            if unit_ref:
                record['unit'] = self.units.get(unit_ref)
                record.pop('unitref')

            records.append(record)

        records_df = pd.DataFrame(records)
        self.data = pd.concat([self.data, records_df], ignore_index=True)


INLINE_IXBRL_TAGS = ['ix:nonfraction', 'ix:nonnumeric', 'ix:fraction']


class TextBlock:

    def __init__(self, text: str):
        self.text: str = text

    def __str__(self):
        return "TextBlock"

    def __repr__(self):
        return self.text


class TableBlock(TextBlock):

    def __init__(self, text: str):
        super().__init__(text)

    def __str__(self):
        return "TableBlock"


class HtmlDocument:

    def __init__(self, blocks: List[TextBlock], data: Optional[DocumentData] = None):
        self.blocks: List[TextBlock] = blocks
        self.data: Optional[DocumentData] = data

    @property
    def text(self):
        return "\n".join([b.text for b in self.blocks])

    @classmethod
    def extract_text(cls, start_element: Tag):
        # Remove table of contents
        decompose_toc_links(start_element)
        # Remove page numbers
        decompose_page_numbers(start_element)

        # Now find the full text
        blocks: List[TextBlock] = extract_and_format_content(start_element)

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
    def from_html(cls, html: str):
        # First check if the html is inside a <DOCUMENT><TEXT> block
        if "<TEXT>" in html[:500]:
            html = get_text_between_tags(html, 'TEXT')
        soup = BeautifulSoup(html, features='lxml')
        root: Tag = soup.find('html')
        data = cls.extract_data(root)
        blocks: List[TextBlock] = cls.extract_text(root)
        return cls(blocks=blocks, data=data)


def extract_and_format_content(element) -> List[TextBlock]:
    """
    Recursively extract and format content from an element,
    applying special formatting to tables and concatenating text for other elements.
    """
    if element.name == 'table':
        return [TableBlock(text=table_to_text(element))]
    else:
        blocks: List[TextBlock] = []
        for child in element.children:
            if child.name:
                blocks.extend(extract_and_format_content(child))
            elif child.string:
                stripped_string = child.string.strip()
                if stripped_string:
                    # Fix unnecessary line breaks between sections
                    stripped_string = re.sub(r'(?<=[^.?!])\s*\n{2,}\s*', ' ', stripped_string)
                    blocks.append(TextBlock(stripped_string))
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
                row_text.append(col.get_text().strip().ljust(col_widths[new_index]))

        if any([text.strip() for text in row_text]):  # Skip entirely empty rows
            formatted_row = ' | '.join(row_text)
            formatted_table += formatted_row + '\n'
            formatted_table += '-+-'.join(['-' * len(text) for text in row_text]) + '\n'

    return formatted_table


def decompose_toc_links(start_element: Tag) -> List[Tag]:
    regex = re.compile('Table [Oo]f [cC]ontents')
    toc_tags = start_element.find_all('a', string=regex)
    for toc_tag in toc_tags:
        toc_tag.decompose()


def decompose_page_numbers(start_element: Tag):
    span_tags_with_numbers = start_element.find_all('span', string=re.compile('^\d{1,2}$'))
    sequences = []  # To store the sequences of tags for potential review
    current_sequence = []
    previous_number = None

    for tag in span_tags_with_numbers:
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
