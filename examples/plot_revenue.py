from edgar import *
from edgar.xbrl import *
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.ticker as mtick

def plot_revenue_simple(ticker:str):
    """Create a simple financial chart showing Revenue, Gross Profit, and Net Income.
    
    This simplified version is ideal for README examples and quick visualizations.
    
    Args:
        ticker: The stock ticker symbol of the company (e.g., 'MSFT' for Microsoft)
    
    Returns:
        matplotlib.figure.Figure: The figure containing the financial visualization
    """
    # Get company data
    c = Company(ticker)
    filings = c.get_filings(form="10-K").latest(5)
    xbs = XBRLS.from_filings(filings)
    income_statement = xbs.statements.income_statement()
    income_df = income_statement.to_dataframe()
    
    # Extract financial metrics
    net_income = income_df[income_df.concept == "us-gaap_NetIncomeLoss"][income_statement.periods].iloc[0]
    gross_profit = income_df[income_df.concept == "us-gaap_GrossProfit"][income_statement.periods].iloc[0]
    revenue = income_df[income_df.label == "Revenue"][income_statement.periods].iloc[0]
    
    # Convert periods to fiscal years for better readability
    periods = [pd.to_datetime(period).strftime('FY%y') for period in income_statement.periods]
    
    # Reverse the order so most recent years are last (oldest to newest)
    periods = periods[::-1]
    revenue_values = revenue.values[::-1]
    gross_profit_values = gross_profit.values[::-1]
    net_income_values = net_income.values[::-1]
    
    # Create a DataFrame for plotting
    plot_data = pd.DataFrame({
        'Revenue': revenue_values,
        'Gross Profit': gross_profit_values,
        'Net Income': net_income_values
    }, index=periods)
    
    # Convert to billions for better readability
    plot_data = plot_data / 1e9
    
    # Create the figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot the data as lines with markers
    plot_data.plot(kind='line', marker='o', ax=ax, linewidth=2.5)
    
    # Format the y-axis to show billions with 1 decimal place
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'${x:.1f}B'))
    
    # Add labels and title
    ax.set_xlabel('Fiscal Year')
    ax.set_ylabel('Billions USD')
    ax.set_title(f'{c.name} ({ticker}) Financial Performance')
    
    # Add a grid for better readability
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Add a source note
    plt.figtext(0.5, 0.01, 'Source: SEC EDGAR via edgartools', ha='center', fontsize=9)
    
    # Improve layout
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    
    return fig


def plot_revenue_complex(ticker:str):
    """Create a comprehensive financial chart showing Revenue, Gross Profit, and Net Income with detailed annotations.
    
    This version includes profit margins, growth rates, and detailed formatting.
    
    Args:
        ticker: The stock ticker symbol of the company (e.g., 'MSFT' for Microsoft)
    
    Returns:
        matplotlib.figure.Figure: The figure containing the financial visualization
    """
    # Get company data
    c = Company(ticker)
    filings = c.get_filings(form="10-K").latest(5)
    xbs = XBRLS.from_filings(filings)
    income_statement = xbs.statements.income_statement()
    income_df = income_statement.to_dataframe()
    
    # Extract financial metrics
    net_income = income_df[income_df.concept == "us-gaap_NetIncomeLoss"][income_statement.periods].iloc[0]
    gross_profit = income_df[income_df.concept == "us-gaap_GrossProfit"][income_statement.periods].iloc[0]
    revenue = income_df[income_df.label == "Revenue"][income_statement.periods].iloc[0]
    
    # Convert periods to fiscal years for better readability
    periods = [pd.to_datetime(period).strftime('FY%y') for period in income_statement.periods]
    
    # Reverse the order so most recent years are last
    periods = periods[::-1]
    revenue_values = revenue.values[::-1]
    gross_profit_values = gross_profit.values[::-1]
    net_income_values = net_income.values[::-1]
    
    # Create a DataFrame for plotting
    plot_data = pd.DataFrame({
        'Revenue': revenue_values,
        'Gross Profit': gross_profit_values,
        'Net Income': net_income_values
    }, index=periods)
    
    # Convert to billions for better readability
    plot_data = plot_data / 1e9
    
    # Calculate profit margins for secondary axis
    margins = pd.DataFrame({
        'Gross Margin': plot_data['Gross Profit'] / plot_data['Revenue'] * 100,
        'Net Margin': plot_data['Net Income'] / plot_data['Revenue'] * 100
    }, index=periods)
    
    # Create the figure and primary axis
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    # Plot the financial metrics as bars
    x = np.arange(len(periods))
    width = 0.25
    
    ax1.bar(x - width, plot_data['Revenue'], width, label='Revenue', color='#3498db', alpha=0.8)
    ax1.bar(x, plot_data['Gross Profit'], width, label='Gross Profit', color='#2ecc71', alpha=0.8)
    ax1.bar(x + width, plot_data['Net Income'], width, label='Net Income', color='#9b59b6', alpha=0.8)
    
    # Create secondary axis for profit margins
    ax2 = ax1.twinx()
    ax2.plot(x, margins['Gross Margin'], 'o-', color='#2ecc71', linewidth=2, label='Gross Margin %')
    ax2.plot(x, margins['Net Margin'], 's-', color='#9b59b6', linewidth=2, label='Net Margin %')
    
    # Set up the axes labels and formatting
    ax1.set_xlabel('Fiscal Year', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Billions USD', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Profit Margin (%)', fontsize=12, fontweight='bold')
    
    # Format the y-axis to show billions with 1 decimal place
    ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'${x:.1f}B'))
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    
    # Set the x-tick positions and labels
    ax1.set_xticks(x)
    ax1.set_xticklabels(periods)
    
    # Add a title and subtitle
    plt.title(f'{c.name} ({ticker}) Financial Performance', fontsize=16, fontweight='bold', pad=20)
    plt.figtext(0.5, 0.01, 'Source: SEC EDGAR via edgartools', ha='center', fontsize=10)
    
    # Add a grid for better readability
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, fontsize=10)
    
    # Add value annotations on top of the bars
    for i, metric in enumerate(['Revenue', 'Gross Profit', 'Net Income']):
        for j, value in enumerate(plot_data[metric]):
            offset = (i - 1) * width
            ax1.annotate(f'${value:.1f}B', 
                        xy=(j + offset, value), 
                        xytext=(0, 3),
                        textcoords='offset points',
                        ha='center', va='bottom',
                        fontsize=8, fontweight='bold')
    
    # Add growth rates between years
    for metric in ['Revenue', 'Gross Profit', 'Net Income']:
        for i in range(1, len(periods)):
            growth = ((plot_data[metric].iloc[i] / plot_data[metric].iloc[i-1]) - 1) * 100
            offset = (list(plot_data.columns).index(metric) - 1) * width
            ax1.annotate(f'{growth:+.1f}%', 
                        xy=(i + offset, plot_data[metric].iloc[i]), 
                        xytext=(0, -15),
                        textcoords='offset points',
                        ha='center', 
                        color='#e74c3c' if growth < 0 else '#27ae60',
                        fontsize=8, fontweight='bold')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])
    return fig


# For backward compatibility
def plot_revenue(ticker:str):
    """Wrapper function that calls plot_revenue_complex for backward compatibility."""
    return plot_revenue_complex(ticker)

if __name__ == '__main__':
    # Create both simple and complex visualizations
    fig_simple = plot_revenue_simple("MSFT")
    plt.figure(fig_simple.number)
    plt.show()
    
    fig_complex = plot_revenue_complex("MSFT")
    plt.figure(fig_complex.number)
    plt.show()
    
    # Uncomment to save the figures
    fig_simple.savefig("MSFT_financial_simple.png", dpi=300, bbox_inches='tight')
    fig_complex.savefig("MSFT_financial_complex.png", dpi=300, bbox_inches='tight')