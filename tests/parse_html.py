from unstructured.partition.html import partition_html
from lxml import etree as ET

html = """
<html>
<body>
    <div>
    the Company issues shares at $<div style="display:inline;"><bold>5.22</bold></div> per share. 
    There is more text
    </div>
</body>
</html>
"""

elements = partition_html(text=html)
print(''.join(e.text for e in elements))

document = ET.fromstring(html)
print(document)
# Get the first div
div = document.find('.//div')
# Print the text of the first div
print(div.text_content())