from edgar.funds import *

def research_investment_fund(ticker):
    """
    Research investment fund performance and compare with competitors.

    Args:
        ticker: The stock ticker symbol of the investment fund (e.g., 'Vanguard' or 'Fidelity')
    """
    fund_class:FundClass = get_fund_class("VFIAX")
    fund = fund_class.fund
    fund_class
    print(fund)

if __name__ == '__main__':
    research_investment_fund("VFIAX")