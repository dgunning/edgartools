from rich import print

from edgar.forms import list_forms


def test_list_forms():
    forms = list_forms()
    assert len(forms) > 100


def test_forms_summary():
    forms = list_forms()
    summary = forms.summary()
    assert len(summary) == len(forms)
    print()
    print(forms)


def test_forms_get_form():
    forms = list_forms()
    form = forms.get_form('10-K')
    assert form
    assert form.form == '10-K'
    print(form)
    form = forms['10-Q']
    print(form)
