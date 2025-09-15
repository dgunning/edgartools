from edgar import *



def check_facts(ticker:str):
    c = Company(ticker)
    balance_sheet = c.balance_sheet(annual=True, periods=8)
    print(balance_sheet)

    income_statement = c.income_statement(annual=True, periods=8)
    print(income_statement)


if __name__ == '__main__':
    for ticker in ["TSLA", "AAPL", "MSFT", "GOOGL"]:
        check_facts(ticker)