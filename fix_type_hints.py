#!/usr/bin/env python3
"""Fix TYPE_CHECKING imports for undefined names"""

import re
from pathlib import Path

# Files and their needed imports
fixes = {
    "edgar/files/tables.py": {
        "imports": ["from edgar.documents.nodes import BaseNode"]
    },
    "edgar/funds/core.py": {
        "imports": ["from edgar.entity.data import EntityData"]
    },
    "edgar/funds/data.py": {
        "imports": ["from bs4 import Tag"]
    },
    "edgar/ownership/html_render.py": {
        "imports": ["from edgar.ownership.core import Ownership"]
    },
    "edgar/sgml/sgml_common.py": {
        "imports": ["from edgar._filings import Filing"]
    },
    "edgar/storage.py": {
        "imports": ["from edgar._filings import Filings"]
    },
    "edgar/xbrl/parser.py": {
        "imports": ["from edgar.xbrl.models import Footnote"]
    },
    "edgar/xbrl/stitching/xbrls.py": {
        "imports": ["from edgar._filings import Filings"]
    },
    "edgar/xbrl/xbrl.py": {
        "imports": [
            "from edgar.xbrl.facts import FactQuery",
            "from edgar.xbrl.models import Footnote, Fact"
        ]
    }
}

def add_type_checking_imports(file_path, imports_to_add):
    """Add TYPE_CHECKING imports to a file"""
    content = Path(file_path).read_text()

    # Check if already has TYPE_CHECKING
    if 'TYPE_CHECKING' in content:
        # Find the if TYPE_CHECKING block and add imports
        pattern = r'(if TYPE_CHECKING:.*?)(\n(?:\s{4}|\t).*?)*\n'
        existing_block = re.search(pattern, content)
        if existing_block:
            # Add to existing block
            indent = "    "
            new_imports = "\n".join(f"{indent}{imp}" for imp in imports_to_add)
            # Insert after if TYPE_CHECKING:
            insert_pos = existing_block.end(1)
            content = content[:insert_pos] + "\n" + new_imports + content[insert_pos:]
        else:
            return False
    else:
        # Add TYPE_CHECKING to typing imports
        typing_pattern = r'(from typing import .*?)(\n)'
        match = re.search(typing_pattern, content)
        if match:
            # Add TYPE_CHECKING to imports
            if 'TYPE_CHECKING' not in match.group(1):
                new_typing = match.group(1) + ', TYPE_CHECKING'
                content = content[:match.start(1)] + new_typing + content[match.end(1):]

            # Add if TYPE_CHECKING block after typing import
            indent = "\n"
            type_checking_block = "\n\nif TYPE_CHECKING:\n"
            for imp in imports_to_add:
                type_checking_block += f"    {imp}\n"

            # Insert after the typing import line
            insert_pos = match.end()
            content = content[:insert_pos] + type_checking_block + content[insert_pos:]
        else:
            return False

    Path(file_path).write_text(content)
    return True

# Apply fixes
for file_path, fix_data in fixes.items():
    if Path(file_path).exists():
        if add_type_checking_imports(file_path, fix_data["imports"]):
            pass
        else:
            pass
    else:
        pass
