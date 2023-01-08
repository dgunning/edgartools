from edgar.gaap import get_gaap


def test_get_gaap():
    gaap = get_gaap()
    assert 'us-gaap' in gaap
    assert 'us-gaap:AffordableHousingProgramAssessments' in gaap

    assert 'bogus' not in gaap
    assert 'us-gaap:bogus' not in gaap
