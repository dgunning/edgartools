from edgar import *
from pathlib import Path
from tqdm.auto import tqdm


def sample_and_test(form:str='3'):
    filings = get_filings(form=form, year=2023, quarter=1).sample(100)
    filing = filings[0]
    #filing = find("0001968369-23-000001")
    ownership = filing.obj()
    html = ownership.to_html()
    filing.open()
    print(str(filing))
    Path(f'data/ownership/generatedForm{form}.html').write_text(html)

def batch_check_for_no_html_in_filing():
    filings = get_filings(year=2024).sample(1000)
    for filing in tqdm(filings):
        html = filing.html()
        if not html:
            print(str(filing))
            filing.home.open()
            #break


if __name__ == '__main__':
    sample_and_test('5')