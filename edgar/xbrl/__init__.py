from edgar.xbrl.xbrldata import XBRLData, XbrlDocuments, XBRLInstance,  StatementData, Statements
from edgar.xbrl.presentation import XBRLPresentation
from typing import Optional, Union


def get_xbrl_object(filing: 'Filing') -> Optional[Union[XBRLInstance, XBRLData]]:
    """
    Extract XBRL data from a filing
    :param filing: Filing
    :return: XBRLInstance or XBRLData
    """
    xbrl_documents: XbrlDocuments = XbrlDocuments(filing.attachments)
    if xbrl_documents.empty:
        return None
    elif xbrl_documents.instance_only:
        return xbrl_documents.get_xbrl_instance()
    else:
        return XBRLData.extract(filing)



