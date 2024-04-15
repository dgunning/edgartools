from edgar.reference.data.common import read_csv_from_package
from functools import lru_cache


@lru_cache(maxsize=64)
def describe_form(form: str) -> str:
    """
    Get the description of a form from the form descriptions file.
    """
    data = read_csv_from_package('secforms.csv')
    is_amendment = False
    if form.endswith("/A"):
        form = form[:-2]
        is_amendment = True
    form = form.upper()
    description = data.loc[data.Form == form]
    if len(description) == 0:
        return f"Form {form}"
    else:
        description = description.Description.iloc[0]
        return f"Form {form}{' Amendment' if is_amendment else ''}: {description}"
