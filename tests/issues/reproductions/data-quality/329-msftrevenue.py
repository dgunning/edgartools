#!/usr/bin/env python3
"""
Migrated from gists/bugs/329-MSFTRevenue.py
M S F T Revenue - Data Quality Issue

Original file: 329-MSFTRevenue.py
Category: data-quality
Migrated: Automatically migrated from legacy bug reproduction system
"""

# Original imports and setup
from edgar import *
from rich import print
import os


if __name__ == '__main__':
    c = Company("MSFT")
    f = Filing(company='MICROSOFT CORP',
               cik=789019,
               form='10-K',
               filing_date='2024-07-30',
               accession_no='0000950170-24-087843')

    xb = f.xbrl()
    inc = xb.statements.income_statement()
    #inc_rendered = inc.render()
    print(inc)

   # print(
   # xb.query().by_text("Cost of Revenue")
    #.to_dataframe('concept', 'label', 'value', 'statement_type')
    #)

    print(
    xb.query().by_text("Selling")
    .to_dataframe('concept', 'label', 'value', 'statement_type')
    )

    print(
    xb.query().by_value(lambda v: v == -7_609_000_000 )
    .to_dataframe('concept', 'label', 'value', 'statement_type')
    )


"""
                         Consolidated Statement of Income (Standardized)                          
                    Year Ended (In millions, except shares and per share data)                    
                                                                                                  
                                                      Jun 30, 2024   Jun 30, 2023   Jun 30, 2022  
 ──────────────────────────────────────────────────────────────────────────────────────────────── 
      Product and Service                                                                         
        Product and Service                                                                       
        Revenue                                           $245,122       $211,915       $198,270  
        Cost of Revenue                                  $(74,114)      $(65,863)      $(62,650)  
        Gross Profit                                      $171,008       $146,052       $135,620  
        Research and Development Expense                 $(29,510)      $(27,195)      $(24,512)  
        Selling, General and Administrative Expense      $(24,456)      $(22,759)      $(21,825)  
        Selling, General and Administrative Expense       $(7,609)       $(7,575)       $(5,900)  
        Operating Income                                  $109,433        $88,523        $83,383  
        Nonoperating Income/Expense                       $(1,646)           $788           $333  
        Income Before Tax                                 $107,787        $89,311        $83,716  
        Income Tax Expense                                 $19,651        $16,950        $10,978  
        Net Income                                         $88,136        $72,361        $72,738  
        Earnings per share:                                                                       
          Earnings Per Share                                 11.86           9.72           9.70  
          Earnings Per Share (Diluted)                       11.80           9.68           9.65  
        Weighted average shares outstanding:                                                      
          Shares Outstanding                                 7,431          7,446          7,496  
          Shares Outstanding (Diluted)                       7,469          7,472          7,540  
                                                                                                  
                                   concept                label                                              value   statement_type
0       us-gaap:SellingAndMarketingExpense  Sales and marketing                                       -24456000000  IncomeStatement
1       us-gaap:SellingAndMarketingExpense  Sales and marketing                                       -22759000000  IncomeStatement
2       us-gaap:SellingAndMarketingExpense  Sales and marketing                                       -21825000000  IncomeStatement
3  msft:SellingAndMarketingPolicyTextBlock  Sales and Marketing  <p style="font-size:10pt;margin-top:13.5pt;fon...      Disclosures
                                   concept                       label        value   statement_type
0  us-gaap:"GeneralAndAdministrativeExpense"  General and administrative  -7609000000  IncomeStatement


"""

# Migration Notes:
# - This file was automatically migrated from the legacy gists/bugs/ system
# - Consider converting to structured test format using templates in tests/issues/_templates/
# - Add proper assertions and error handling for robust testing
# - Update imports to be more specific if needed
