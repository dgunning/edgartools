from edgar.gaap import gaap


def test_get_gaap():
    assert 'us-gaap' in gaap
    assert 'us-gaap:AffordableHousingProgramAssessments' in gaap

    assert 'bogus' not in gaap
    assert 'us-gaap:bogus' not in gaap
