"""The flat edgar.offerings.* module paths are gone in 6.0.

Bead: edgartools-07lk.22.2 (the stubs removed in 6.0); the move itself was
edgartools-n094.7, shipped in 5.40.0.

The offerings parsers moved into edgar.offerings.crowdfunding, .exempt and
.prospectus, and the 16 old flat modules were left as stubs that re-exported
them without a warning. 6.0 deletes them, so an old import fails at the import
line. The package-level names (`from edgar.offerings import FormD`) and
`filing.obj()` are unaffected.
"""

import importlib
import sys
from pathlib import Path

import pytest

MOVES = {
    "formc": "crowdfunding",
    "campaign": "crowdfunding",
    "_campaign_render": "crowdfunding",
    "formd": "exempt",
    "registration_s1": "prospectus",
    "registration_s3": "prospectus",
    "registration_s4": "prospectus",
    "drs": "prospectus",
    "_fee_table": "prospectus",
    "_424b_classifier": "prospectus",
    "_424b_cover": "prospectus",
    "_424b_tables": "prospectus",
    "_424b_xbrl": "prospectus",
    "_s1_classifier": "prospectus",
    "_s1_cover": "prospectus",
    "_s3_cover": "prospectus",
}

PACKAGE_NAMES = {
    "FormC": "edgar.offerings.crowdfunding.formc",
    "Campaign": "edgar.offerings.crowdfunding.campaign",
    "FormD": "edgar.offerings.exempt.formd",
    "RegistrationS1": "edgar.offerings.prospectus.registration_s1",
    "RegistrationS3": "edgar.offerings.prospectus.registration_s3",
    "RegistrationS4": "edgar.offerings.prospectus.registration_s4",
    "DraftRegistrationStatement": "edgar.offerings.prospectus.drs",
}


@pytest.mark.parametrize("name", sorted(MOVES))
def test_the_old_flat_path_is_removed(name):
    old = f"edgar.offerings.{name}"
    sys.modules.pop(old, None)
    with pytest.raises(ModuleNotFoundError, match=old.replace(".", r"\.")):
        importlib.import_module(old)


@pytest.mark.parametrize("name", sorted(MOVES))
def test_the_new_path_imports(name):
    module = importlib.import_module(f"edgar.offerings.{MOVES[name]}.{name}")
    assert module.__name__ == f"edgar.offerings.{MOVES[name]}.{name}"


@pytest.mark.parametrize("symbol", sorted(PACKAGE_NAMES))
def test_package_level_names_are_unaffected(symbol):
    import edgar.offerings
    cls = getattr(edgar.offerings, symbol)
    assert cls.__module__.startswith(PACKAGE_NAMES[symbol])


def test_group_offerings_by_file_number_is_exported_where_the_guide_says():
    from edgar.offerings import group_offerings_by_file_number
    from edgar.offerings.crowdfunding.formc import group_offerings_by_file_number as real
    assert group_offerings_by_file_number is real


def test_obj_dispatch_names_the_new_modules():
    """Read structurally: obj() imports these lazily, so a stale path only fails on that form."""
    text = Path(importlib.import_module("edgar").__file__).read_text(encoding="utf-8")
    for name in ("drs", "registration_s1", "registration_s3", "registration_s4"):
        assert f"from edgar.offerings.{name} import" not in text
        assert f"from edgar.offerings.prospectus.{name} import" in text
