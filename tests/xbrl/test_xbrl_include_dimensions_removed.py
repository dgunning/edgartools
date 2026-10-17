"""
include_dimensions was removed from statement rendering in 6.0 (GH #574).

It had been deprecated since 5.8.0 in favour of view= ('standard', 'detailed',
'summary'): include_dimensions=True was view='detailed' and
include_dimensions=False was view='standard'. Passing it now raises TypeError.

Where removing it would have moved a later parameter into its positional slot,
the later parameters are keyword-only, so a 5.x positional call fails loudly
instead of silently binding the old value to a different parameter.

These tests need no filing: argument binding fails before the method body runs.
"""
import warnings

import pytest

from edgar.financials import Financials
from edgar.xbrl.presentation import StatementView
from edgar.xbrl.statements import Statement, Statements

STATEMENT_ACCESSORS = ['balance_sheet', 'income_statement', 'cash_flow_statement',
                       'statement_of_equity', 'comprehensive_income']


def _bare_statement():
    return object.__new__(Statement)


def _bare_statements():
    return object.__new__(Statements)


@pytest.mark.fast
@pytest.mark.parametrize('value', [True, False])
def test_statement_render_rejects_include_dimensions(value):
    with pytest.raises(TypeError, match="include_dimensions"):
        _bare_statement().render(include_dimensions=value)


@pytest.mark.fast
@pytest.mark.parametrize('value', [True, False])
def test_statement_to_dataframe_rejects_include_dimensions(value):
    with pytest.raises(TypeError, match="include_dimensions"):
        _bare_statement().to_dataframe(include_dimensions=value)


@pytest.mark.fast
@pytest.mark.parametrize('method', STATEMENT_ACCESSORS)
def test_statements_accessors_reject_include_dimensions(method):
    with pytest.raises(TypeError, match="include_dimensions"):
        getattr(_bare_statements(), method)(include_dimensions=True)


@pytest.mark.fast
def test_statements_to_dataframe_rejects_include_dimensions():
    with pytest.raises(TypeError, match="include_dimensions"):
        _bare_statements().to_dataframe('IncomeStatement', include_dimensions=True)


@pytest.mark.fast
@pytest.mark.parametrize('method', STATEMENT_ACCESSORS)
def test_financials_accessors_reject_include_dimensions(method):
    with pytest.raises(TypeError, match="include_dimensions"):
        getattr(Financials(xb=None), method)(include_dimensions=True)


# --- The 5.x positional slot must not rebind to another parameter ---------

@pytest.mark.fast
@pytest.mark.parametrize('method', STATEMENT_ACCESSORS)
def test_financials_accessor_positional_slot_raises(method):
    # 5.x: financials.income_statement(True) meant include_dimensions=True.
    # Without keyword-only view it would now mean view=True.
    with pytest.raises(TypeError, match="positional"):
        getattr(Financials(xb=None), method)(True)


@pytest.mark.fast
def test_statement_to_dataframe_positional_slot_raises():
    # 5.x slot 5 was include_dimensions; it must not become include_unit.
    with pytest.raises(TypeError, match="positional"):
        _bare_statement().to_dataframe(None, None, True, None, True)


@pytest.mark.fast
def test_statements_to_dataframe_positional_slot_raises():
    # 5.x slot 4 was include_dimensions; it must not become view or presentation.
    with pytest.raises(TypeError, match="positional"):
        _bare_statements().to_dataframe('IncomeStatement', None, True, True)


@pytest.mark.fast
def test_statement_render_positional_slot_raises():
    # include_dimensions was render()'s last parameter, so nothing shifted;
    # a sixth positional argument is simply too many.
    with pytest.raises(TypeError, match="positional"):
        _bare_statement().render(None, None, True, False, None, True)


# --- view= still reaches the statement ---------------------------------------

class _RecordingStatements:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def accessor(**kwargs):
            self.calls.append((name, kwargs))
            return name
        return accessor


class _RecordingXBRL:
    def __init__(self):
        self.statements = _RecordingStatements()


@pytest.mark.fast
@pytest.mark.parametrize('method', STATEMENT_ACCESSORS)
def test_financials_forwards_view_only(method):
    xb = _RecordingXBRL()
    result = getattr(Financials(xb), method)(view='detailed')
    assert result == method
    assert xb.statements.calls == [(method, {'view': 'detailed'})]


@pytest.mark.fast
def test_statements_to_dataframe_forwards_view_without_warning():
    # In 5.x this method always passed include_dimensions=False to render(),
    # so every call warned. It now forwards view and warns about nothing.
    rendered_with = {}

    class _Rendered:
        def to_dataframe(self, presentation):
            return ('frame', presentation)

    class _Stmt:
        def render(self, **kwargs):
            rendered_with.update(kwargs)
            return _Rendered()

    class _Statements(Statements):
        def __init__(self):
            pass

        def __getitem__(self, item):
            return _Stmt()

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = _Statements().to_dataframe('IncomeStatement', view=StatementView.DETAILED)

    assert result == ('frame', True)
    assert rendered_with == {'period_view': None, 'standard': True, 'view': StatementView.DETAILED}
