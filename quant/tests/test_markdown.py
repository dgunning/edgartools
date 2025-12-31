import pandas as pd

from quant.markdown import extract_markdown


class FakeRendered:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def to_dataframe(self) -> pd.DataFrame:
        return self._df


class FakeStatement:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def render(self, standard: bool = True) -> FakeRendered:
        return FakeRendered(self._df)


class FakeFinancials:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def income_statement(self):
        return FakeStatement(self._df)

    def balance_sheet(self):
        return FakeStatement(self._df)

    def cashflow_statement(self):
        return FakeStatement(self._df)

    def statement_of_equity(self):
        return FakeStatement(self._df)

    def comprehensive_income(self):
        return FakeStatement(self._df)

    def cover(self):
        return FakeStatement(self._df)


class FakeFiling:
    def __init__(self, df: pd.DataFrame):
        self.form = "10-K"
        self.accession_no = "0000000000-00-000000"
        self.filing_date = "2024-01-31"
        self.company = "Test Corp"
        self.cik = 123456
        self.ticker = "TEST"
        self.financials = FakeFinancials(df)

    def obj(self):
        return self

    def html(self):
        return ""


def test_extract_markdown_drops_dimension_columns():
    df = pd.DataFrame(
        [
            {
                "label": "Total Revenue",
                "2023": 100,
                "concept": "us-gaap:Revenues",
                "dimension": False,
                "abstract": False,
                "level": 0,
            }
        ]
    )

    filing = FakeFiling(df)
    markdown = extract_markdown(
        filing,
        statement=["IncomeStatement"],
        show_dimension=False,
        notes=False,
    )

    assert "Income Statement" in markdown
    assert "dimension" not in markdown
