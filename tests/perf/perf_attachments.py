from edgar  import Filing
from pyinstrument import Profiler

if __name__ == '__main__':
    filing = Filing(form='10-K', filing_date='2024-05-10', company='Arogo Capital Acquisition Corp.', cik=1881741, accession_no='0001213900-24-041641')
    with Profiler() as p:
        filing.attachments
    p.print(timeline=True)