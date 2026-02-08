from edgar import *
from rich import print
from edgar.xbrl.periods import determine_periods_to_display

def check_statements():
    c = Company("AVGO")
    f = c.latest("10-Q")
    xb:XBRL = f.xbrl()
    period_end = xb.period_of_report
    #print(xb.statements)
    periods = determine_periods_to_display(xb, "IncomeStatement")
    ic = xb.statements.income_statement()
    rendered_statement = ic.render()
    print(rendered_statement)
    #print(ic)

if __name__ == '__main__':
    check_statements()