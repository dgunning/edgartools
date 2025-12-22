from edgar.forms import list_forms

__all__ = [
    'list_takedown_forms'
]
takedown_forms = ["424A", "424B1", "424B2", "424B3", "424B4", "424B5", "424B6", "424B7", "424B8", "497", "486BPOS",
                  "F-3MEF"]


def list_takedown_forms():
    sec_forms = list_forms()
    return sec_forms.data.query("Form.isin(@takedown_forms)", engine="python")
