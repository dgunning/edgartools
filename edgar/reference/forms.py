from functools import lru_cache

from edgar.reference.data.common import read_csv_from_package

sec_form_data = read_csv_from_package('secforms.csv')


@lru_cache(maxsize=64)
def describe_form(form: str,
                  prepend_form: bool = True) -> str:
    """
    Get the description of a form from the form descriptions file.
    """
    is_amendment = False
    if form.endswith("/A"):
        form = form[:-2]
        is_amendment = True
    form = form.upper()
    description = sec_form_data.loc[sec_form_data.Form == form]
    if len(description) == 0:
        return f"Form {form}"
    else:
        description = description.Description.iloc[0]
        if prepend_form:
            return f"Form {form}{' Amendment' if is_amendment else ''}: {description}"
        else:
            return description


PROSPECTUSES = ["S-1", "S-3", "S-4", "S-8", "S-11", "F-1", "F-3", "F-4", "F-6", "F-10", "424B1",
                "424B2", "424B3", "424B4", "424B5", "424B7", "424B8", "485BPOS", "486BPOS", "497", "N-2", "N-14",
                "POS AM", "POSASR", "POS EX", "10", "20-F", "8-A", "SF-1", "SF-3"
                ]
