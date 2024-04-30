import argparse

from tqdm import tqdm

from edgar import get_filings


def sample_and_test_filings(years, sample_size):
    print(f"Sampling {sample_size} filings from {years}")
    for filing in tqdm(get_filings(year=years).sample(sample_size)):
        try:
            attachments = filing.attachments
            filing.text()
            filing.view()
            filing.markdown()
            filing.obj()
            print(filing.header)
        except Exception as e:
            print(f"Failed to get text for {filing}")
            filing.open()
            print(e)
            raise


def main():
    parser = argparse.ArgumentParser(description='Inspect filings from specific years with a given sample size.')
    parser.add_argument('-y', '--years', type=int, nargs='+', required=True,
                        help='Years to fetch filings for (e.g., -y 1999 2000)')
    parser.add_argument('-s', '--sample_size', type=int, required=True,
                        help='Sample size of filings to process')

    args = parser.parse_args()
    sample_and_test_filings(args.years, args.sample_size)


if __name__ == '__main__':
    main()
