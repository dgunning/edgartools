"""Rich rendering for 13F holdings reports."""

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Column, Table

__all__ = ['render_rich', 'infotable_summary']


def infotable_summary(thirteen_f):
    """
    Create a summary DataFrame of the information table for display.

    Args:
        thirteen_f: ThirteenF instance

    Returns:
        pd.DataFrame or None: Summary of holdings sorted by value
    """
    if thirteen_f.has_infotable():
        infotable = thirteen_f.infotable
        if infotable is not None and len(infotable) > 0:
            return (infotable
                    .filter(['Issuer', 'Class', 'Cusip', 'Ticker', 'Value', 'SharesPrnAmount', 'Type', 'PutCall',
                             'SoleVoting', 'SharedVoting', 'NonVoting'])
                    .rename(columns={'SharesPrnAmount': 'Shares'})
                    .assign(Value=lambda df: df.Value,
                            Type=lambda df: df.Type.fillna('-'),
                            Ticker=lambda df: df.Ticker.fillna(''))
                    .sort_values(['Value'], ascending=False)
                    )
    return None


def render_rich(thirteen_f):
    """
    Create Rich Panel display for a 13F filing.

    Args:
        thirteen_f: ThirteenF instance

    Returns:
        Panel: Rich Panel containing filing summary and holdings table
    """
    title = f"{thirteen_f.form} Holding Report for {thirteen_f.filing.company} for period {thirteen_f.report_period}"
    summary = Table(
        "Report Period",
        Column("Investment Manager", style="bold deep_sky_blue1"),
        "Signed By",
        "Holdings",
        "Value",
        "Accession Number",
        "Filed",
        box=box.SIMPLE)

    summary.add_row(
        thirteen_f.report_period,
        thirteen_f.investment_manager.name if thirteen_f.investment_manager else thirteen_f.manager_name,
        thirteen_f.signer or "-",
        str(thirteen_f.total_holdings or "-"),
        f"${thirteen_f.total_value:,.0f}" if thirteen_f.total_value else "-",
        thirteen_f.filing.accession_no,
        thirteen_f.filing_date
    )

    content = [summary]

    # info table
    infotable_summary_df = infotable_summary(thirteen_f)
    if infotable_summary_df is not None:
        table = Table("", "Issuer", "Class", "Cusip", "Ticker", "Value", "Type", "Shares", "Put/Call",
                      row_styles=["bold", ""],
                      box=box.SIMPLE)
        for index, row in enumerate(infotable_summary_df.itertuples()):
            table.add_row(str(index),
                          row.Issuer,
                          row.Class,
                          row.Cusip,
                          row.Ticker,
                          f"${row.Value:,.0f}",
                          row.Type,
                          f"{int(row.Shares):,.0f}",
                          row.PutCall
                          )
        content.append(table)

    return Panel(
        Group(*content), title=title, subtitle=title
    )
