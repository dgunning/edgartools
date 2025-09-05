#!/usr/bin/env python3
"""
Migrated from gists/bugs/339-MultifinancialsOrder.py
Multifinancials Order - Data Quality Issue

Original file: 339-MultifinancialsOrder.py
Category: data-quality
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import Company, MultiFinancials
from edgar.xbrl.xbrl import XBRL
from edgar.xbrl import XBRLS

def explore_statement_ordering(ticker: str):
    print("exploring single period statement ordering for", ticker)
    c = Company(ticker)
    filing = c.get_filings(form="10-K")[1]

    ### METHOD 1:
    # Parse XBRL data
    xb = filing.xbrl()

    # Access statements through the user-friendly API
    statements = xb.statements

    # Display financial statements
    income_statement = statements.income_statement()

    print(income_statement)
    print(
        xb.query()
        #.by_text("Interest Expense")
        .by_value(lambda v: v == -113_000_000)
    )


    """
                        Consolidated Statement of Income (Standardized)                         
                   Year Ended (In millions, except shares and per share data)                   
                                                                                                
                                                       Dec 1, 2023   Dec 2, 2022   Dec 3, 2021  
 ────────────────────────────────────────────────────────────────────────────────────────────── 
        Revenue                                            $19,409       $17,606       $15,785  
        Total Cost of Revenue                             $(2,354)      $(2,165)      $(1,865)  
        Gross Profit                                       $17,055       $15,441       $13,920  
        Operating Expenses                                                                      
          Research and development                          $3,473        $2,987        $2,540  
          Selling Expense                                   $5,351        $4,968        $4,321  
          General and Administrative Expense                $1,413        $1,219        $1,085  
          Amortization of intangibles                         $168          $169          $172  
          Operating Expenses                             $(10,405)      $(9,343)      $(8,118)  
        Operating Income                                    $6,650        $6,098        $5,802  
          Non-operating income (expense):                                                       
          Interest Expense                                  $(113)        $(112)        $(113)  
          Investment gains (losses), net                       $16         $(19)           $16  
          Other income (expense), net                         $246           $41                
          Nonoperating Income/Expense                         $149         $(90)         $(97)  
        Income Before Tax from Continuing Operations         6,799         6,008         5,705  
        Income Tax Expense                                  $1,371        $1,252          $883  
        Net Income                                          $5,428        $4,756        $4,822  
        Earnings Per Share (Basic)                           11.87         10.13         10.10  
        Shares Outstanding (Basic)                             457           470           477  
        Earnings Per Share (Diluted)                         11.82         10.10         10.02  
        Shares Outstanding (Diluted)                           459           471           481  
      """


def explore_statements_ordering(ticker: str, years: int = 5):
    print("exploring multi-period statement ordering for", ticker)
    # Get multiple years of 10-K filings
    company = Company(ticker)
    filings = company.get_filings(form="10-K").latest(years)

    ### METHOD 1:
    # Create multi-period financials
    xbrls = XBRLS.from_filings(filings)
    # Access statements spanning multiple years
    income_statement = xbrls.statements.income_statement()

    print("Multi-Year Income Statement:")
    print(income_statement)

    """
                                 CONSOLIDATED INCOME STATEMENT (5-Period View) (Standardized)                                 
                                  Year Ended (In millions, except shares and per share data)                                  
                                                                                                                              
                                                       Nov 29, 2024   Dec 1, 2023   Dec 2, 2022   Dec 3, 2021   Nov 27, 2020  
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── 
      Subscription                                                                       $1,646        $1,374         $1,108  
        Revenue                                             $21,505       $19,409       $17,606       $15,785        $12,868  
          Product                                                                           $35           $41            $36  
          Services and other                                                               $484          $450           $578  
          Interest Expense (non-operating)                   $(169)                                                           
          Investment gains (losses), net                        $48           $16         $(19)           $16            $13  
          Other income (expense), net                          $311          $246           $41                          $42  
        Total Cost of Revenue                              $(2,358)      $(2,354)      $(2,165)      $(1,865)       $(1,722)  
        Gross Profit                                        $19,147       $17,055       $15,441       $13,920        $11,146  
          Research and development                           $3,944        $3,473        $2,987        $2,540         $2,188  
          Acquisition termination fee                        $1,000                                                           
          Amortization of intangibles                          $169          $168          $169          $172           $162  
          General and Administrative Expense                 $1,529        $1,413        $1,219        $1,085           $968  
          Selling Expense                                    $5,764        $5,351        $4,968        $4,321         $3,591  
        Operating Expenses                                $(12,406)     $(10,405)      $(9,343)      $(8,118)       $(6,909)  
        Operating Income                                     $6,741        $6,650        $6,098        $5,802         $4,237  
          Nonoperating Income/Expense                          $190          $149         $(90)         $(97)          $(61)  
        Income Before Tax from Continuing Operations          6,931         6,799         6,008         5,705          4,176  
        Income Tax Expense                                   $1,371        $1,371        $1,252          $883       $(1,084)  
        Net Income                                           $5,560        $5,428        $4,756        $4,822         $5,260  
        Earnings Per Share (Basic)                            12.43         11.87         10.13         10.10          10.94  
        Earnings Per Share (Diluted)                          12.36         11.82         10.10         10.02          10.83  
        Shares Outstanding (Basic)                              447           457           470           477            481  
        Shares Outstanding (Diluted)                            450           459           471           481            485  
          Interest Expense                                                 $(113)        $(112)        $(113)         $(116) 

    """

if __name__ == "__main__":
    ticker = "AAPL"
    explore_statement_ordering(ticker)
    explore_statements_ordering(ticker)

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
