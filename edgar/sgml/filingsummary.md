# Filing Summary

# Overview 

A Filing Summary is an XML document that lists the attachments in the filing. 
It is most useful for `10-K`, `10-Q` and other filings with XBRL since it lists the individual report html which can be used directly to get individual statements e.g. **BalanceSheet** or other report

See an example in `data/sgml/AAPL-FilingSummary.xml`

```python

c = Company("AAPL")
f = c.get_filings(form="10-Q").latest(1)
f.attachments
```

```
 Seq   Document                        Description                                                                                         Type              
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────── 
  1     aapl-20250329.htm               10-Q                                                                                                📜  10-Q          
  2     a10-qexhibit31103292025.htm     EX-31.1                                                                                             📋  EX-31.1       
  3     a10-qexhibit31203292025.htm     EX-31.2                                                                                             📋  EX-31.2       
  4     a10-qexhibit32103292025.htm     EX-32.1                                                                                             📋  EX-32.1       
  5     aapl-20250329.xsd               XBRL TAXONOMY EXTENSION SCHEMA DOCUMENT                                                             🔰  EX-101.SCH    
  6     aapl-20250329_cal.xml           XBRL TAXONOMY EXTENSION CALCULATION LINKBASE DOCUMENT                                               📊  EX-101.CAL    
  7     aapl-20250329_def.xml           XBRL TAXONOMY EXTENSION DEFINITION LINKBASE DOCUMENT                                                📚  EX-101.DEF    
  8     aapl-20250329_lab.xml           XBRL TAXONOMY EXTENSION LABEL LINKBASE DOCUMENT                                                     📎  EX-101.LAB    
  9     aapl-20250329_pre.xml           XBRL TAXONOMY EXTENSION PRESENTATION LINKBASE DOCUMENT                                              📈  EX-101.PRE    
  10    aapl-20250329_g1.jpg                                                                                                                🎨  GRAPHIC       
  12    R1.htm                          Cover Page                                                                                          🌍  HTML          
  13    R2.htm                          CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS (Unaudited)                                         🌍  HTML          
  14    R3.htm                          CONDENSED CONSOLIDATED STATEMENTS OF COMPREHENSIVE INCOME (Unaudited)                               🌍  HTML          
  15    R4.htm                          CONDENSED CONSOLIDATED BALANCE SHEETS (Unaudited)                                                   🌍  HTML          
  16    R5.htm                          CONDENSED CONSOLIDATED BALANCE SHEETS (Unaudited) (Parenthetical)                                   🌍  HTML          
  17    R6.htm                          CONDENSED CONSOLIDATED STATEMENTS OF SHAREHOLDERS' EQUITY (Unaudited)                               🌍  HTML          
  18    R7.htm                          CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS (Unaudited)                                         🌍  HTML          
  19    R8.htm                          Summary of Significant Accounting Policies                                                          🌍  HTML          
  20    R9.htm                          Revenue                                                                                             🌍  HTML          
  21    R10.htm                         Earnings Per Share                                                                                  🌍  HTML          
  22    R11.htm                         Financial Instruments                                                                               🌍  HTML          
  23    R12.htm                         Condensed Consolidated Financial Statement Details                                                  🌍  HTML          
  24    R13.htm                         Debt                                                                                                🌍  HTML          
  25    R14.htm                         Shareholders' Equity                                                                                🌍  HTML          
  26    R15.htm                         Share-Based Compensation                                                                            🌍  HTML          
  27    R16.htm                         Contingencies                                                                                       🌍  HTML          
  28    R17.htm                         Segment Information and Geographic Data                                                             🌍  HTML          
  29    R18.htm                         Pay vs Performance Disclosure                                                                       🌍  HTML          
  30    R19.htm                         Insider Trading Arrangements                                                                        🌍  HTML          
  31    R20.htm                         Summary of Significant Accounting Policies (Policies)                                               🌍  HTML          
  32    R21.htm                         Revenue (Tables)                                                                                    🌍  HTML          
  33    R22.htm                         Earnings Per Share (Tables)                                                                         🌍  HTML          
  34    R23.htm                         Financial Instruments (Tables)                                                                      🌍  HTML          
  35    R24.htm                         Condensed Consolidated Financial Statement Details (Tables)                                         🌍  HTML          
  36    R25.htm                         Share-Based Compensation (Tables)                                                                   🌍  HTML          
  37    R26.htm                         Segment Information and Geographic Data (Tables)                                                    🌍  HTML          
  38    R27.htm                         Revenue - Disaggregated Net Sales and Portion of Net Sales That Was Previously Deferred (Details)   🌍  HTML          
  39    R28.htm                         Revenue - Additional Information (Details)                                                          🌍  HTML          
  40    R29.htm                         Revenue - Deferred Revenue, Expected Timing of Realization (Details)                                🌍  HTML          
  41    R30.htm                         Earnings Per Share - Computation of Basic and Diluted Earnings Per Share (Details)                  🌍  HTML          
  42    R31.htm                         Financial Instruments - Cash, Cash Equivalents and Marketable Securities (Details)                  🌍  HTML          
  43    R32.htm                         Financial Instruments - Additional Information (Details)                                            🌍  HTML          
  44    R33.htm                         Financial Instruments - Notional Amounts of Derivative Instruments (Details)                        🌍  HTML          
  45    R34.htm                         Condensed Consolidated Financial Statement Details - Inventories (Details)                          🌍  HTML          
  46    R35.htm                         Condensed Consolidated Financial Statement Details - Property, Plant and Equipment, Net (Details)   🌍  HTML          
  47    R36.htm                         Debt - Additional Information (Details)                                                             🌍  HTML          
  48    R37.htm                         Shareholders' Equity - Additional Information (Details)                                             🌍  HTML          
  49    R38.htm                         Share-Based Compensation - Restricted Stock Unit Activity and Related Information (Details)         🌍  HTML          
  50    R39.htm                         Share-Based Compensation - Additional Information (Details)                                         🌍  HTML          
  51    R40.htm                         Share-Based Compensation - Summary of Share-Based Compensation Expense and the Related Income Tax   🌍  HTML          
                                        Benefit (Details)                                                                                                     
  52    R41.htm                         Segment Information and Geographic Data - Information by Reportable Segment (Details)               🌍  HTML          
  53    R42.htm                         Segment Information and Geographic Data - Reconciliation of Segment Operating Income to the         🌍  HTML          
                                        Condensed Consolidated Statements of Operations (Details)                                                             
  54    Financial_Report.xlsx           IDEA: XBRL DOCUMENT                                                                                 📊  EXCEL         
  55    Show.js                         IDEA: XBRL DOCUMENT                                                                                 📄  JS            
  56    report.css                      IDEA: XBRL DOCUMENT                                                                                 📃  CSS           
  58    FilingSummary.xml               IDEA: XBRL DOCUMENT                                                                                 🔷  XML           
  61    MetaLinks.json                  IDEA: XBRL DOCUMENT                                                                                 📝  JSON          
  62    0000320193-25-000057-xbrl.zip   IDEA: XBRL DOCUMENT                                                                                 📦  ZIP           
  63    aapl-20250329_htm.xml           IDEA: XBRL DOCUMENT                                                                                 🔷  XML 
```

To show a report
```
 f.reports[2].view()
```

```
  CONDENSED CONSOLIDATED STATEMENTS OF                                                                    
  OPERATIONS (Unaudited) - USD ($)shares                   3 Months Ended                 6 Months Ended  
  in Thousands, $ in Millions               Mar. 29, 2025   Mar. 30, 2024  Mar. 29, 2025   Mar. 30, 2024  
 ──────────────────────────────────────────────────────────────────────────────────────────────────────── 
  Net sales                                      $ 95,359        $ 90,753      $ 219,659       $ 210,328  
  Cost of sales                                    50,492          48,482        116,517         113,202  
  Gross margin                                     44,867          42,271        103,142          97,126  
  Operating expenses:                                                                                     
  Research and development                          8,550           7,903         16,818          15,599  
  Selling, general and administrative               6,728           6,468         13,903          13,254  
  Total operating expenses                         15,278          14,371         30,721          28,853  
  Operating income                                 29,589          27,900         72,421          68,273  
  Other income/(expense), net                        -279             158           -527             108  
  Income before provision for income taxes         29,310          28,058         71,894          68,381  
  Provision for income taxes                        4,530           4,422         10,784          10,829  
  Net income                                     $ 24,780        $ 23,636       $ 61,110        $ 57,552  
  Earnings per share:                                                                                     
  Basic (in dollars per share)                     $ 1.65          $ 1.53         $ 4.06          $ 3.72  
  Diluted (in dollars per share)                   $ 1.65          $ 1.53         $ 4.05          $ 3.71  
  Shares used in computing earnings per                                                                   
  share:                                                                                                  
  Basic (in shares)                            14,994,082      15,405,856     15,037,903      15,457,810  
  Diluted (in shares)                          15,056,133      15,464,709     15,103,499      15,520,675  
  Products                                                                                                
  Net sales                                      $ 68,714        $ 66,886      $ 166,674       $ 163,344  
  Cost of sales                                    44,030          42,424        103,477         100,864  
  Services                                                                                                
  Net sales                                        26,645          23,867         52,985          46,984  
  Cost of sales                                   $ 6,462         $ 6,058       $ 13,040        $ 12,338                                                                                                         
```
`f.reports` shows just the reports (also accessible via `tenk.reports`, `tenq.reports`, etc.)
`f.statements` shows just the statements


Fiiling -> SGML -> Attachments --> Attachment - Parse the HTML and render

# Feature
- Get report data into dataframes from the html
