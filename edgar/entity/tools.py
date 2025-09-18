from edgar import Company

def income_statement(ticker:str, annual:bool=True, periods:int=4):
    company = Company(ticker)
    if company:
        return c.income_statement(annual=annual, periods=periods)

def balance_sheet(ticker:str, annual:bool=True, periods:int=4):
    company = Company(ticker)
    if company:
        return company.balance_sheet(annual=annual, periods=periods)

def cash_flow_statement(ticker:str, annual:bool=True, periods:int=4):
    company = Company(ticker)
    if company:
        return c.cash_flow(annual=annual, periods=periods)