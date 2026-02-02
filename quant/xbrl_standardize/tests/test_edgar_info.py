
from edgar import Company, set_identity
import sys

def test_company_info(ticker):
    try:
        set_identity("User user@example.com")
        c = Company(ticker)
        print(f"Ticker: {c.ticker}")
        print(f"Company: {c.name}")
        # Check attributes to find SIC
        print(f"Industry: {getattr(c, 'industry', 'N/A')}")
        print("\nAll attributes:")
        for attr in dir(c):
            if not attr.startswith('_'):
                try:
                    val = getattr(c, attr)
                    if not callable(val):
                        print(f"  {attr}: {val}")
                except:
                    pass
    except Exception as e:
        print(f"Error for {ticker}: {e}")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    test_company_info(ticker)
