#!/usr/bin/env python3
"""Quick test to see what footnoteArcs actually reference."""

import xml.etree.ElementTree as ET

from edgar import Company

# Get APD 2015 10-K
apd = Company("APD")
filings_2015 = apd.get_filings(form="10-K", filing_date="2015-01-01:2015-12-31")
filing_2015 = list(filings_2015)[0]

# Find instance document
for att in filing_2015.attachments:
    if att.document == 'apd-20150930.xml':
        xml_content = att.download()
        break

# Parse XML
root = ET.fromstring(xml_content)

namespaces = {
    'link': 'http://www.xbrl.org/2003/linkbase',
    'xlink': 'http://www.w3.org/1999/xlink',
}

# Find footnoteArcs and check what they reference
footnote_links = root.findall('.//link:footnoteLink', namespaces)
print(f"Found {len(footnote_links)} footnoteLink elements\n")

for fn_link in footnote_links:
    arcs = fn_link.findall('.//link:footnoteArc', namespaces)
    print(f"Found {len(arcs)} footnoteArc elements")
    print("\nFirst 5 arcs reference:")
    for i, arc in enumerate(arcs[:5]):
        arc_to = arc.get('{http://www.w3.org/1999/xlink}to')
        arc_from = arc.get('{http://www.w3.org/1999/xlink}from')
        print(f"  Arc {i+1}: from='{arc_from}' to='{arc_to}'")
