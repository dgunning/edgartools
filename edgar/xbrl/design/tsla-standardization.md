                                                    
```python

from edgar import *
import pandas as pd
pd.options.display.max_colwidth = 100

c = Company("TSLA")
filings = c.latest("10-Q", 6)
xb = None
print(xb.statements.income_statement())
```

                                        Consolidated Statement of Income (Standardized)                                                        
                                              Three Months Ended (In millions, except shares and per share data)                                               
                                                                                                                                                               
                                                                                                                             Jun 30, 2023 (Q2)   Jun 30, 2023  
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── 
      Product and Service                                                                                                                                      
        Product and Service                                                                                                                                    
        Revenue                                                                                                                                                
          Revenue                                                                                                                         $567         $3,038  
          Revenue                                                                                                                      $24,927        $48,256  
        Revenue                                                                                                                                                
          Automotive leasing                                                                                                              $338           $671  
          Cost of Revenue                                                                                                               $1,231         $2,592  
          Cost of Revenue                                                                                                            $(20,394)      $(39,212)  
        Gross Profit                                                                                                                    $4,533         $9,044  
        Operating Expenses                                                                                                                                     
          Research and Development Expense                                                                                                $943         $1,714  
          Selling, General and Administrative Expense                                                                                   $1,191         $2,267  
          Operating Expenses                                                                                                          $(2,134)       $(3,981)  
        Operating Income                                                                                                                $2,399         $5,063  
        Interest income                                                                                                                   $238           $451  
        Interest Expense                                                                                                                 $(28)          $(57)  
        Other income, net                                                                                                                 $328           $280  
        Income Before Tax                                                                                                               $2,937         $5,737  
        Income Tax Expense                                                                                                              $(323)         $(584)  
        Net Income                                                                                                                      $2,614         $5,153  
        Net (loss) income attributable to noncontrolling interests and redeemable noncontrolling interests in subsidiaries                 $89            $63  
        Net Income                                                                                                                      $2,703         $5,216  
        Net Income                                                                                                                                             
          Earnings Per Share                                                                                                              0.85           1.65  
          Earnings Per Share (Diluted)                                                                                                    0.78           1.50  
        Net Income                                                                                                                                             
          Shares Outstanding                                                                                                             3,171          3,168  
          Shares Outstanding (Diluted)                                                                                                   3,478          3,473  
                           

```python

print(xb.query()
      .by_value(lambda v : v == 24_927_000_000 or v == 567_000_000)
      .to_dataframe('concept', 'label', 'value', 'period_end', 'statement_type')
      )
```                                                                                                                                    

                                                       concept               label        value  period_end   statement_type
0                                       tsla:AutomotiveLeasing  Automotive leasing    567000000  2023-06-30  IncomeStatement
1  us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax            Revenues    567000000  2023-06-30  IncomeStatement
2                                             us-gaap:Revenues      Total revenues  24927000000  2023-06-30  IncomeStatement
3                                             us-gaap:Revenues      Total revenues  24927000000  2023-06-30  IncomeStatement
4                                             us-gaap:Revenues      Total revenues  24927000000  2023-06-30  IncomeStatement
