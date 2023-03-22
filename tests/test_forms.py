from rich import print

from edgar import Filing
from edgar.forms import list_forms, EightK, find_section


def test_list_forms():
    forms = list_forms()
    assert len(forms) > 100


def test_forms_summary():
    forms = list_forms()
    summary = forms.summary()
    assert len(summary) == len(forms)
    print()
    print(forms)


def test_forms_get_form():
    forms = list_forms()
    form = forms.get_form('10-K')
    assert form
    assert form.form == '10-K'
    print(form)
    form = forms['10-Q']
    print(form)


adobe_8K = Filing(form='8-K',
                  filing_date='2023-03-15',
                  company='ADOBE INC.',
                  cik=796343,
                  accession_no='0000796343-23-000044')


def test_eightk_items():
    eightk = EightK(adobe_8K)
    assert len(eightk.items) == 2
    print()
    print(eightk)


def test_eightk_obj():
    eightk = adobe_8K.obj()
    assert isinstance(eightk, EightK)
    assert len(eightk.items) == 2
    print()
    assert "Item 2.02" == eightk.items[0].item_num
    assert "Results of Operations and Financial Condition. On" in eightk.items[0].text


def test_eightk_difficult_parsing():
    filing = Filing(form='8-K', filing_date='2023-03-20', company='4Front Ventures Corp.', cik=1783875,
                    accession_no='0001279569-23-000330')
    eightk = filing.obj()
    print()
    print(eightk)

    filing = Filing(form='8-K', filing_date='2023-03-20', company='ALBEMARLE CORP', cik=915913,
                    accession_no='0000915913-23-000088')
    eightk = filing.obj()
    print()
    print(eightk)


    filing = Filing(form='8-K', filing_date='2023-03-20', company='AFC Gamma, Inc.', cik=1822523,
                    accession_no='0001829126-23-002149')
    eightk = filing.obj()
    # md = filing.markdown()
    print()
    print(eightk)

    filing = Filing(form='8-K', filing_date='2023-03-20', company='Artificial Intelligence Technology Solutions Inc.',
                    cik=1498148, accession_no='0001493152-23-008256')
    eightk = filing.obj()
    print()
    print(eightk)

    filing = Filing(form='8-K', filing_date='2023-03-20', company='CATO CORP', cik=18255,
                    accession_no='0001562762-23-000124')
    eightk = filing.obj()
    print()
    print(eightk)


def test_eightk_with_spaces_in_items():
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AAR CORP', cik=1750,
                    accession_no='0001104659-23-034265')
    print()
    print(filing.markdown())
    eightk = filing.obj()
    print()
    print(eightk)
    assert len(eightk.items) == 3


def test_eightk_with_no_signature_header():
    filing = Filing(form='8-K', filing_date='2023-03-20', company='AMERISERV FINANCIAL INC /PA/', cik=707605,
                    accession_no='0001104659-23-034205')
    eightk = filing.obj()
    assert len(eightk.items) == 2


def test_find_section():
    assert find_section("If\D+an\D+emerging\D+growth\D+company,\D+indicate",
                        ['ABC', 'If\nan emerging growth company, indicate if the Exchange Act.\xa0\xa0☐', '|  |\n| --'])

    assert find_section("If\D+an\D+emerging\D+growth\D+company,\D+indicate",
                        ['ABC', '  If an emerging growth company, indicate if the Exchange Act.', '|  |\n| --'])
