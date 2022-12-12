from bs4 import BeautifulSoup
from edgar.xml import child_value
import pyarrow.compute as pc

from edgar import Company


def test_child_value():
    soup = BeautifulSoup(
        """
        
        """, features="xml"
    )


def test_parse_xbrl():
    company = Company.for_ticker('SNOW')
    obj = company.get_filings("10-Q")
    print(obj)
    print(pc.min_max(obj.filing_index['filingDate']).as_py())
