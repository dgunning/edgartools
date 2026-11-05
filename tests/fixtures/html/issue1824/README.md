# SEC source fixtures for issue 1824

Downloaded directly from SEC on 2026-11-01 before implementing the fallback.
The HTML files are saved response bytes, not edited table reconstructions or
VCR cassettes. Tests discover the earnings exhibit link in the primary 6-K.

| File | Source | SHA-256 |
|---|---|---|
| a3q26e_withguidancexfinal.htm | https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/a3q26e_withguidancexfinal.htm | `43d51cc7eba069f9d27e8a4647304d37bdeae90127d5c38e1736d857c240f00d` |
| tsm-20261015x6k.htm | https://www.sec.gov/Archives/edgar/data/1046179/000104617926000726/tsm-20261015x6k.htm | `43a0be1d03e92a19e49e8e55b18a0165811a5a7a105a5a89f731b53022bc664f` |
| tsm-monthend6kx20261022.htm | https://www.sec.gov/Archives/edgar/data/1046179/000104617926000728/tsm-monthend6kx20261022.htm | `9183c7d03daf67fd0efa4547cdc7e37fbcaaf33a593e71f37d27dba7dbc24878` |

Ground truth in the earnings exhibit: `(Unit: NT$ million, except for EPS)`;
net sales 1,494,243; gross profit 992,379; income from operations 876,445;
net income 763,064; reported EPS 29.43 (footnote b). Net income comparisons
are 452,302 for 3Q25 and 706,562 for 2Q26, with YoY/QoQ percentages interleaved.
Footnote a says the 3Q2026 figures have not been approved by the Board of Directors.
