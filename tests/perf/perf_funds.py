from edgar import *
from edgar.funds import *
from pyinstrument import Profiler

def main():
    fund:Fund = get_fund("S000011951")
    fund_series = fund.get_series()
    classes = fund.get_classes()

    fund:FundClass = get_fund("C000013712")
    fund_series = fund.fund.get_series()
    classes = fund.fund.get_classes()

    fund:FundClass = get_fund("C000013712")
    fund_series = fund.fund.get_series()
    classes = fund.fund.get_classes()

    fund:FundClass = get_fund("VBILX")
    fund_series = fund.fund.get_series()
    classes = fund.fund.get_classes()


if __name__ == "__main__":
    with Profiler() as p:
        main()
    p.print()