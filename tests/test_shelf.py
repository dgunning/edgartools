from rich import print

from edgar.shelfofferings import list_takedown_forms


def test_list_takedown_forms():
    takedown_forms = list_takedown_forms()
    print(takedown_forms)
