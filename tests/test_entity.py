from edgar._companies import EntityData, get_entity_submissions

def test_entity_is_company():

    # TSLA
    assert get_entity_submissions(1318605).is_company

    # Taneja Vaibhav at TSLA
    assert not get_entity_submissions(1771340).is_company

    # &VEST Domestic Fund II LP
    assert get_entity_submissions(1800903).is_company

    # Siemens AG
    assert get_entity_submissions(940418).is_company

    # SIEMENS ENERGY AG/ADR
    assert get_entity_submissions(1830056).is_company

    # SIEVERT STEPHANIE A
    assert not get_entity_submissions(1718179).is_company

    assert get_entity_submissions(1911716).is_company

    # Warren Buffett
    assert not get_entity_submissions(315090).is_company