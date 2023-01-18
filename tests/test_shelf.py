from edgar.shelf import list_takedown_forms
from edgar.form import *
from rich import print


def test_list_takedown_forms():
    print(SecForms.load())
    takedown_forms = list_takedown_forms()
    print(takedown_forms)