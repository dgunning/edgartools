import pandas as pd
from edgar.datatools import dataframe_to_text

def test_dataframe_to_text():
    df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    text = dataframe_to_text(df)
    assert "1" in text