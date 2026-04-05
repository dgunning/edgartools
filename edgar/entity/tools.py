from edgar import Company


def income_statement(ticker: str, annual: bool = True, periods: int = 4):
    return Company(ticker).income_statement(annual=annual, periods=periods)


def balance_sheet(ticker: str, annual: bool = True, periods: int = 4):
    return Company(ticker).balance_sheet(annual=annual, periods=periods)


def cash_flow_statement(ticker: str, annual: bool = True, periods: int = 4):
    return Company(ticker).cash_flow_statement(annual=annual, periods=periods)
