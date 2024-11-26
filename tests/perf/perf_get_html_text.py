from pyinstrument import Profiler
from html.html_documents import HtmlDocument

from edgar import Filing

if __name__ == '__main__':
    filing = Filing(form='10-K', filing_date='2024-05-10',
                    company='Arogo Capital Acquisition Corp.',
                    cik=1881741, accession_no='0001213900-24-041641')
    html = filing.html()
    with Profiler() as p:
        html_document = HtmlDocument.from_html(html, extract_data=False)
    p.print(timeline=True)

