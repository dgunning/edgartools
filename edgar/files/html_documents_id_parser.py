import re
from typing import Dict, List

from bs4 import BeautifulSoup, NavigableString, Tag

from edgar.files.html_documents import (
    Block,
    HtmlDocument,
    LinkBlock,
    clean_html_root,
    decompose_page_numbers,
    extract_and_format_content,
)
from edgar.files.htmltools import ChunkedDocument


class AssembleText:

    @staticmethod
    def assemble_block_text(chunks: List[Block], prefix_src: str = None):
        if prefix_src:
            for block in chunks:
                if isinstance(block, LinkBlock):
                    yield block.to_markdown(prefix_src=prefix_src)
                else:
                    yield block.get_text()
        else:
            for block in chunks:
                yield block.get_text()

    @staticmethod
    def assemble_block_markdown(chunks: List[Block], prefix_src: str = None):
        if prefix_src:
            for block in chunks:
                if isinstance(block, LinkBlock):
                    yield block.to_markdown(prefix_src=prefix_src)
                else:
                    yield block.to_markdown()
        else:
            for block in chunks:
                yield block.to_markdown()

    @staticmethod
    def clean_and_assemble_text(
        start_element: Tag, markdown: bool = False
    ) -> str:
        # Now find the full text
        blocks: List[Block] = extract_and_format_content(start_element)
        # Compress the blocks
        blocks: List[Block] = HtmlDocument._compress_blocks(blocks)
        if markdown:
            return "".join(
                [text for text in AssembleText.assemble_block_markdown(blocks)]
            )
        else:
            return "".join(
                [text for text in AssembleText.assemble_block_text(blocks)]
            )

    @staticmethod
    def assemble_html_document(tags: List[Tag], markdown: bool = False) -> str:
        return ChunkedDocument.clean_part_line(
            "".join(
                [
                    AssembleText.clean_and_assemble_text(
                        tag, markdown=markdown
                    )
                    for tag in tags
                ]
            )
        )

    @staticmethod
    def find_block_level_parent(tag, all_link_tag: list):
        ori_tag = tag
        while tag and tag.parent is not None:
            parent = tag.parent
            link_count = 0
            for link in all_link_tag:
                matched = parent.find(id=link) or parent.find(
                    "a", attrs={"name": link}
                )
                if matched:
                    link_count += 1
            if link_count > 1:
                return tag
            tag = parent
        return tag if tag else ori_tag

    @staticmethod
    def assemble_items(
        html_content: str, item_links: List, markdown: bool = False
    ) -> dict:
        try:
            root: Tag = HtmlDocument.get_root(html_content)
            start_element = clean_html_root(root)
            decompose_page_numbers(start_element)
            soup = start_element

            link_ids = [item_id for item_name, item_id in item_links]
            items = {}

            # Helper method to extract content up to a specific element
            def get_intro_content(first_item_id: str) -> List[Tag]:
                intro_content = []
                current = soup.find(id=first_item_id) or soup.find(
                    "a", attrs={"name": first_item_id}
                )
                if current:
                    container = AssembleText.find_block_level_parent(current, link_ids)

                    if container:
                        for sibling in container.previous_siblings:
                            if isinstance(sibling, Tag):
                                intro_content.append(sibling)
                    sibling = current.previous_sibling
                    while sibling:
                        if isinstance(sibling, Tag):
                            intro_content.append(sibling)
                        sibling = sibling.previous_sibling
                    intro_content.reverse()
                return intro_content

            # Step 1: Extract intro (from start of document to first item)
            first_item_id = item_links[0][1] if item_links else None
            if first_item_id:
                intro_content = get_intro_content(first_item_id)
                items["Item 0"] = AssembleText.assemble_html_document(
                    intro_content, markdown=markdown
                )

            # Step 2: Extract items
            id_to_content = {}
            for idx, (item_name, item_id) in enumerate(item_links):

                if idx < len(item_links)-1:
                    n_item_id = item_links[idx+1][1]
                else:
                    n_item_id = None
                # Try both id and name attributes
                target = soup.find(id=item_id) or soup.find(
                    "a", attrs={"name": item_id}
                )
                if not target:
                    raise Exception(f"link id error. item_name:{item_name}, item_id:{item_id}")

                target = AssembleText.find_block_level_parent(target, link_ids)
                if target:
                    content = []
                    current = target
                    while current:
                        if (
                            current
                            and not isinstance(current, (str, NavigableString))
                            and n_item_id
                            and current.find(id=n_item_id) or soup.find(
                                "a", attrs={"name": n_item_id}
                            )
                        ):
                            break
                        if current.name is not None or (
                            current.string and current.string.strip()
                        ):
                            content.append(current)
                        current = current.next_sibling
                    id_to_content[item_id] = AssembleText.assemble_html_document(
                        content, markdown=markdown
                    )

                if item_id in id_to_content:
                    items[item_name] = id_to_content[item_id]

            # Step 3: Handle Signatures
            if "Signature" not in items and item_links:
                last_item_name, last_item_id = item_links[-1]
                last_content = items.get(last_item_name, "")
                sig_key = ["SIGNATURES", "SIGNATURE"]
                content_lines = last_content.split("\n")
                signature_line_index = None
                for i, line in enumerate(content_lines):
                    if line.strip().upper() in sig_key:
                        signature_line_index = i
                        break
                if signature_line_index is not None:
                    before_sig = "\n".join(content_lines[:signature_line_index])
                    sig_start_pos = len(before_sig) + 1
                    items["Signature"] = last_content[sig_start_pos:].strip()
                    items[last_item_name] = before_sig.strip()
                else:
                    items["Signature"] = ""

            return items
        except Exception:
            return {}

class ParsedHtml10K:

    @staticmethod
    def extract_element_id(href: str) -> str:
        """
        Extract element ID from an XLink href.

        Args:
            href: XLink href attribute value

        Returns:
            Element ID
        """
        return href.split("#")[-1]

    def extract_html_link_info(self, html_content: str) -> List:
        """
        Find rows in tables that:
            1. Contain links
            2. Have a separate cell storing page numbers
        """

        html_content = html_content.replace("&nbsp;", " ")
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        link_info: List = []
        tables = soup.find_all("table")
        for table in tables:
            table_links: List[Dict] = []
            for row in table.find_all("tr"):
                cells = row.find_all("td", recursive=False)
                exist_page_num = False
                if cells:
                    text = [
                        " ".join(
                            cell.get_text(separator="", strip=True).split()
                        )
                        for cell in cells
                    ]
                    for cell in cells:
                        cell_text = cell.text.strip()
                        if cell_text.isdigit() or (
                            "-" in cell_text
                            and all(
                                p.strip().isdigit()
                                for p in cell_text.split("-")
                            )
                        ):
                            exist_page_num = True

                    links = [
                        cell.find("a")
                        for cell in cells
                        if cell.find("a")
                        and cell.find("a").attrs.get("href")
                        and cell.find("a").attrs.get("href").startswith("#")
                    ]

                    if links and exist_page_num:
                        link = links[0].attrs.get("href").split("#")[-1]
                        table_links.append({"text": text, "link": link})
            if table_links:
                link_info.append(table_links)

        return link_info

    @staticmethod
    def extract_item_and_split(link_info: List):
        """
        Defines matching patterns and functions for extracting and splitting SEC filing items.

        The code provides:
        1. Four dictionaries (items_match_1 to items_match_4) containing different formats of SEC item identifiers
        2. A match_function_map tuple that pairs each dictionary with its corresponding matching function
        3. Matching functions that handle case-insensitive comparisons (startswith, equals, contains)

        The matching strategies cover:
        - Standard item formats (e.g., "Item 1.")
        - Part/item combinations (e.g., "Part I, Item 1")
        - Full item descriptions (e.g., "Business")
        - Combined items (e.g., "Items 1 and 2.")

        Note: The actual item processing loop is not implemented in the selected code.
        """
        if not link_info:
            return []

        link_info = [item for sublist in link_info for item in sublist]
        items_match_1 = {  # Match items starting with these patterns
            "Item 1": "Item 1.",
            "Item 1A": "Item 1A.",
            "Item 1B": "Item 1B.",
            "Item 1C": "Item 1C.",
            "Item 2": "Item 2.",
            "Item 3": "Item 3.",
            "Item 4": "Item 4.",
            "Item 5": "Item 5.",
            "Item 6": "Item 6.",
            "Item 7": "Item 7.",
            "Item 7A": "Item 7A.",
            "Item 8": "Item 8.",
            "Item 9": "Item 9.",
            "Item 9A": "Item 9A.",
            "Item 9B": "Item 9B.",
            "Item 9C": "Item 9C.",
            "Item 10": "Item 10.",
            "Item 11": "Item 11.",
            "Item 12": "Item 12.",
            "Item 13": "Item 13.",
            "Item 14": "Item 14.",
            "Item 15": "Item 15.",
            "Item 16": "Item 16.",
            "Signatures": "Signature",
        }
        items_match_0 = {key: key for key in items_match_1}

        items_match_2 = {  # Exact match after stripping whitespace
            "Item 1": "Part I, Item 1",
            "Item 1A": "Part I, Item 1A",
            "Item 1B": "Part I, Item 1B",
            "Item 1C": "Part I, Item 1C",
            "Item 2": "Part I, Item 2",
            "Item 3": "Part I, Item 3",
            "Item 4": "Part I, Item 4",
            "Item 5": "Part II, Item 5",
            "Item 6": "Part II, Item 6",
            "Item 7": "Part II, Item 7",
            "Item 7A": "Part II, Item 7A",
            "Item 8": "Part II, Item 8",
            "Item 9": "Part II, Item 9",
            "Item 9A": "Part II, Item 9A",
            "Item 9B": "Part II, Item 9B",
            "Item 9C": "Part II, Item 9C",
            "Item 10": "Part III, Item 10",
            "Item 11": "Part III, Item 11",
            "Item 12": "Part III, Item 12",
            "Item 13": "Part III, Item 13",
            "Item 14": "Part III, Item 14",
            "Item 15": "Part IV, Item 15",
            "Item 16": "Part IV, Item 16",
            "Signatures": "Signature",
        }
        items_match_2_1 = {
            "Item 1": "Item No. 1",
            "Item 1A": "Item No. 1A",
            "Item 1B": "Item No. 1B",
            "Item 1C": "Item No. 1C",
            "Item 2": "Item No. 2",
            "Item 3": "Item No. 3",
            "Item 4": "Item No. 4",
            "Item 5": "Item No. 5",
            "Item 6": "Item No. 6",
            "Item 7": "Item No. 7",
            "Item 7A": "Item No. 7A",
            "Item 8": "Item No. 8",
            "Item 9": "Item No. 9",
            "Item 9A": "Item No. 9A",
            "Item 9B": "Item No. 9B",
            "Item 9C": "Item No. 9C",
            "Item 10": "Item No. 10",
            "Item 11": "Item No. 11",
            "Item 12": "Item No. 12",
            "Item 13": "Item No. 13",
            "Item 14": "Item No. 14",
            "Item 15": "Item No. 15",
            "Item 16": "Item No. 16",
        }

        items_match_3 = {  # Match item names (startswith comparison)
            "Item 1": "Business",
            "Item 1A": "Risk Factors",
            "Item 1B": "Unresolved Staff Comments",
            "Item 1C": "Cybersecurity",
            "Item 2": "Properties",
            "Item 3": "Legal Proceedings",
            "Item 4": "Mine Safety Disclosures",
            "Item 5": "Market for Registrant’s Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
            "Item 6": "[Reserved]",
            "Item 7": "Management’s Discussion and Analysis of Financial Condition and Results of Operations",
            "Item 7A": "Quantitative and Qualitative Disclosures About Market Risk",
            "Item 8": "Financial Statements and Supplementary Data",
            "Item 9": "Changes in and Disagreements with Accountants on Accounting and Financial Disclosure",
            "Item 9A": "Controls and Procedures",
            "Item 9B": "Other Information",
            "Item 9C": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
            "Item 10": "Directors, Executive Officers and Corporate Governance",
            "Item 11": "Executive Compensation",
            "Item 12": "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
            "Item 13": "Certain Relationships and Related Transactions, and Director Independence",
            "Item 14": "Principal Accountant Fees and Services",
            "Item 15": "Exhibit and Financial Statement Schedules",
            "Item 16": "Form 10-K Summary",
        }

        items_match_4 = {  # Match combined items (startswith comparison)
            "Item 1": "Items 1 and 2.",
            "Item 2": "Items 1 and 2.",
        }

        items_match_5 = {
            "Item 1": "1. Business",
            "Item 1A": "1A. Risk Factors",
            "Item 1B": "1B. Unresolved Staff Comments",
            "Item 1C": "1C. Cybersecurity",
            "Item 2": "2. Properties",
            "Item 3": "3. Legal Proceedings",
            "Item 4": "4. Mine Safety Disclosures",
            "Item 5": "5. Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
            "Item 6": "6. [Reserved]",
            "Item 7": "7. Management's Discussion and Analysis of Financial Condition and Results of Operations",
            "Item 7A": "7A. Quantitative and Qualitative Disclosures about Market Risk",
            "Item 8": "8. Financial Statements and Supplementary Data",
            "Item 9": "9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure",
            "Item 9A": "9A. Controls and Procedures",
            "Item 9B": "9B. Other Information",
            "Item 9C": "9C. Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
            "Item 10": "10. Directors, Executive Officers and Corporate Governance",
            "Item 11": "11. Executive Compensation",
            "Item 12": "12. Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
            "Item 13": "13. Certain Relationships and Related Transactions, and Director Independence",
            "Item 14": "14. Principal Accountant Fees and Services",
            "Item 15": "15. Exhibit and Financial Statement Schedules",
            "Item 16": "16. Form 10-K Summary",
        }

        items_match_6 = {
            "Item 1": "1 and 2. Business and Properties",
            "Item 2": "1 and 2. Business and Properties",
        }

        # Matching function types:
        # 1. equal
        # 2. startswith
        # 3. contains
        # 4. regex
        match_function_map = [  # The current page has an order
            (
                items_match_4,
                lambda x, y: x.strip().lower().startswith(y.lower()),
            ),
            (
                items_match_6,
                lambda x, y: x.strip().lower().startswith(y.lower()),
            ),
            (items_match_0, lambda x, y: x.strip().lower() == y.lower()),
            (
                items_match_1,
                lambda x, y: x.strip().lower().startswith(y.lower()),
            ),
            (items_match_2, lambda x, y: x.strip().lower() == y.lower()),
            (items_match_2_1, lambda x, y: x.strip().lower() == y.lower()),
            (items_match_3, lambda x, y: y.lower() in x.lower()),
            (items_match_5, lambda x, y: y.lower() in x.lower()),
        ]

        # Process matches and ensure unique items with ascending page numbers
        item_dict = {}

        for one_link in link_info:
            for match_map, match_function in match_function_map:
                for item_name, match_text in match_map.items():
                    for cell in one_link["text"]:
                        if match_function(cell, match_text):
                            link = one_link["link"]

                            # Only keep the first matching link for each item
                            if item_name not in item_dict:
                                item_dict[item_name] = link

        # Convert to list format without sorting
        item_links = [(name, link) for name, link in item_dict.items()]
        return item_links

    def extract_html(
        self, html_content: str, structure, markdown: bool = False
    ) -> dict:
        """
        Find rows in tables that:
            1. Contain links
            2. Have a separate cell storing page numbers
        """
        index_table = self.extract_html_link_info(html_content)
        item_links = self.extract_item_and_split(index_table)

        item_result = AssembleText.assemble_items(
            html_content, item_links, markdown=markdown
        )

        item_to_part = {}
        for part_name in structure.structure:
            part_items = structure.get_part(part_name)
            for item_name in part_items:
                item_to_part[item_name.lower()] = part_name.lower()

        # Step 4: Group items by part
        result = {part_name.lower(): {} for part_name in structure.structure}
        result["extracted"] = {}

        for item_name, content in item_result.items():
            item_name = item_name.lower()
            part_name = item_to_part.get(item_name)
            if part_name:
                result[part_name][item_name] = content
            else:
                result["extracted"][item_name] = content

        return result


class ParsedHtml10Q:
    """Parser for 10-Q HTML documents that handles same item numbers in different parts."""

    @staticmethod
    def extract_element_id(href: str) -> str:
        """Extract element ID from an XLink href."""
        return href.split("#")[-1]

    def extract_html_link_info(self, html_content: str) -> List:
        """Find rows in tables that contain links and page numbers."""
        html_content = html_content.replace("&nbsp;", " ")
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        link_info: List = []
        tables = soup.find_all("table")
        part_regex = re.compile(r"^\s*(Part\s+[IVXLC]+)\s*", re.IGNORECASE)
        part = None
        for table in tables:
            table_links: List[Dict] = []
            for row in table.find_all("tr"):
                row_text = row.get_text()
                row_text = row.get_text().strip()
                part_match = part_regex.match(row_text)
                if part_match:
                    part = re.sub(r'\s+', ' ', part_match.group(1).lower())
                cells = row.find_all("td", recursive=False)
                exist_page_num = False
                if cells:
                    text = [
                        cell.get_text(separator="  ", strip=True)
                        for cell in cells
                    ]
                    for cell in cells:
                        cell_text = cell.text.strip()
                        if cell_text.isdigit() or (
                            "-" in cell_text
                            and all(
                                p.strip().isdigit()
                                for p in cell_text.split("-")
                            )
                        ):
                            exist_page_num = True

                    links = [
                        cell.find("a")
                        for cell in cells
                        if cell.find("a")
                        and cell.find("a").attrs.get("href")
                        and cell.find("a").attrs.get("href").startswith("#")
                    ]

                    if part and links and exist_page_num:
                        link = links[0].attrs.get("href").split("#")[-1]
                        table_links.append(
                            {"part": part, "text": text, "link": link}
                        )
            if table_links:
                link_info.append(table_links)

        return link_info

    @staticmethod
    def extract_item_and_split(link_info: List):
        """Extract and match 10-Q specific items, handling same item numbers in different parts."""
        if not link_info:
            return []

        link_info = [item for sublist in link_info for item in sublist]

        # 10-Q specific item patterns
        items_match_1 = {  # Standard 10-Q item formats
            "part i": {
                "Item 1": "Item 1.",
                "Item 2": "Item 2.",
                "Item 3": "Item 3.",
                "Item 4": "Item 4.",
            },
            "part ii": {
                "Item 1": "Item 1.",
                "Item 1A": "Item 1A.",
                "Item 2": "Item 2.",
                "Item 3": "Item 3.",
                "Item 4": "Item 4.",
                "Item 5": "Item 5.",
                "Item 6": "Item 6.",
            },
            "Extarect": {"Signatures": "Signature"},
        }

        items_match_2 = {  # Part-prefixed items
            "part i": {
                "Item 1": "part i, Item 1",
                "Item 2": "part i, Item 2",
                "Item 3": "part i, Item 3",
                "Item 4": "part i, Item 4",
            },
            "part ii": {
                "Item 1": "part ii, Item 1",
                "Item 1A": "part ii, Item 1A",
                "Item 2": "part ii, Item 2",
                "Item 3": "part ii, Item 3",
                "Item 4": "part ii, Item 4",
                "Item 5": "part ii, Item 5",
                "Item 6": "part ii, Item 6",
            },
        }

        items_match_3 = {  # Item descriptions
            "part i": {
                "Item 1": "Financial Statements",
                "Item 2": "Management’s Discussion and Analysis of Financial Condition and Results of Operations",
                "Item 3": "Quantitative and Qualitative Disclosures About Market Risk",
                "Item 4": "Controls and Procedures",
            },
            "part ii": {
                "Item 1": "Legal Proceedings",
                "Item 1A": "Risk Factors",
                "Item 2": "Unregistered Sales of Equity Securities and Use of Proceeds",
                "Item 3": "Defaults Upon Senior Securities",
                "Item 4": "Mine Safety Disclosures",
                "Item 5": "Other Information",
                "Item 6": "Exhibits",
            },
        }

        match_function_map = [
            (
                items_match_1,
                lambda x, y: x.strip().lower().startswith(y.lower()),
            ),
            (items_match_2, lambda x, y: x.strip().lower() == y.lower()),
            (items_match_3, lambda x, y: y.lower() in x.lower()),
            # (items_match_4, lambda x, y: x.strip().lower().startswith(y.lower())),
        ]

        # Process matches and ensure unique items
        item_dict = {}

        for one_link in link_info:
            for match_map, match_function in match_function_map:
                for part in match_map:
                    for item_name, match_text in match_map[part].items():
                        for cell in one_link["text"]:
                            if match_function(cell, match_text):
                                link = one_link["link"]
                                if (
                                    one_link["part"] == part
                                    and item_name not in item_dict
                                ):
                                    item_dict[(part, item_name)] = link

        # Convert to list format without sorting
        item_links = [(name, link) for name, link in item_dict.items()]
        if len(item_links) > 11:
            return {}
        return item_links

    def extract_html(self, html_content: str, structure, markdown:bool=True) -> dict:
        """Extract 10-Q items from HTML content, handling same item numbers in different parts."""
        index_table = self.extract_html_link_info(html_content)
        item_links = self.extract_item_and_split(index_table)

        # Assemble items with part information preserved
        item_result = AssembleText.assemble_items(html_content, item_links, markdown=markdown)
        res = {
            "part i": {},
            "part ii":{},
            "extracted":{}
        }
        for one in item_result:
            if isinstance(one, str):
                res["extracted"][one.lower()] = item_result[one]
            elif isinstance(one, tuple):
                res[one[0].lower()][one[1].lower()] = item_result[one]
        return res
