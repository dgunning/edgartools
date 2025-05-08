from edgar import *
from pathlib import Path


def sample_and_test(form:str='3'):
    filings = get_filings(form=form, year=2023, quarter=1).sample(100)
    filing = filings[0]
    #filing = find("0001968369-23-000001")
    ownership = filing.obj()
    html = ownership.to_html()
    filing.open()
    print(str(filing))
    Path(f'data/ownership/generatedForm{form}.html').write_text(html)


if __name__ == '__main__':
    sample_and_test('5')