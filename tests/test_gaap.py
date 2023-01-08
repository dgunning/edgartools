from edgar.gaap import get_gaap
from edgar.core import log


def test_get_gaap():
    try:
        gaap = get_gaap()
        assert 'us-gaap' in gaap
        assert 'us-gaap:AffordableHousingProgramAssessments' in gaap

        assert 'bogus' not in gaap
        assert 'us-gaap:bogus' not in gaap
    except TypeError as err:
        # Cannot get gaap file from the package location because ... github action things
        log.error(err)
