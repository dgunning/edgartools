from edgar import *


def get_filing_by_accession_number():
    filing0 = get_by_accession_number("0001528621-22-001403") # 2022,3
    filing1 = get_by_accession_number("0000899243-22-030068") # 2022,3
    filing2 = get_by_accession_number("0001209191-22-055641")  # 2022,4
    filing3 = get_by_accession_number("0001209191-45-055641")  # Not valid



if __name__ == '__main__':
    get_filing_by_accession_number()
