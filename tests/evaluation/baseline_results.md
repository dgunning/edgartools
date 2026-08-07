# TOC Evaluation Baseline — 2026-04-11

Before agent-aware TOC parsing. 20 10-K filings, 4 agents.

## Per-Filing Results

| Ticker | Agent | Found | / Tot | Rate | Content | Methods |
|--------|-------|------:|------:|-----:|--------:|---------|
| AAPL | Workiva | 21 | 22 | 95% | 20 | toc |
| GOOGL | Workiva | 22 | 22 | 100% | 22 | toc |
| AMZN | Workiva | 21 | 22 | 95% | 21 | toc |
| JPM | Workiva | 21 | 22 | 95% | 18 | toc |
| TSLA | Workiva | 21 | 22 | 95% | 21 | toc |
| MSFT | Donnelley | 22 | 22 | 100% | 22 | toc |
| ORCL | Donnelley | 22 | 22 | 100% | 22 | toc |
| BLK | Donnelley | 21 | 22 | 95% | 20 | toc |
| BRKR | Donnelley | 22 | 22 | 100% | 22 | toc |
| ACHC | Donnelley | 22 | 22 | 100% | 22 | toc |
| BHB | Toppan Merrill | 21 | 22 | 95% | 20 | toc |
| LOCO | Toppan Merrill | 4 | 22 | 18% | 4 | toc |
| ANVS | Toppan Merrill | 19 | 22 | 86% | 19 | toc |
| ELUT | Toppan Merrill | 21 | 22 | 95% | 14 | toc |
| EP | Toppan Merrill | 22 | 22 | 100% | 3 | toc |
| BMNM | Novaworks | 21 | 22 | 95% | 19 | toc |
| CRVO | Novaworks | 0 | 22 | 0% | 0 | - |
| CDIO | Novaworks | 19 | 22 | 86% | 18 | toc |
| CLOQ | Novaworks | 21 | 22 | 95% | 21 | toc |
| BAYVU | Novaworks | 22 | 22 | 100% | 19 | toc |

## Per-Agent Averages

| Agent | Avg Detection | Avg Content | Filings |
|-------|:---:|:---:|:---:|
| Workiva | 96% | 100% | 5 |
| Donnelley | 98% | 100% | 5 |
| Toppan Merrill | 79% | 75% | 5 |
| Novaworks | 75% | 78% | 5 |
| **Overall** | **87%** | **88%** | **20** |

## Notable Failures
- **LOCO** (Toppan Merrill): Only 4/22 sections detected
- **CRVO** (Novaworks): 0/22 sections detected — TOC analysis returned nothing
- **EP** (Toppan Merrill): 22/22 detected but only 3 with content
