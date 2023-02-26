from edgar import *

if __name__ == '__main__':
    # Get filings with default values
    filings = get_filings()
    print(filings)

    print(filings.filter(form="D"))

    # Get filings for a year
    filings_2014 = get_filings(year=2014)
    print(filings_2014)

    # Get filings for a year and a quarter
    filings_2014_4 = get_filings(2014, 4)
    print(filings_2014_4)

    # Get a company
    ge = Company("GE")
    print(ge)

    print(ge.get_filings())

    # Get company facts
    facts = ge.get_facts()
    print(facts)

