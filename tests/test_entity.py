from edgar._companies import EntityData, get_entity_submissions

def test_entity_is_company():

    # TSLA
    assert get_entity_submissions(1318605).is_company

    # Taneja Vaibhav at TSLA
    assert not get_entity_submissions(1771340).is_company