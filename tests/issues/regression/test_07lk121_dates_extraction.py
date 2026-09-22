"""Quarter and date reasoning lives in `edgar.dates`; `edgar.core` re-exports it.

edgartools-07lk.12.1 item (6), staged under 07lk.23's "new paths behind import
shims" row. This is the same bounded extraction `edgar/settings.py` was in PR
#1075 -- see tests/issues/regression/test_07lk121_settings_extraction.py, whose
structure this mirrors deliberately -- applied to the next coherent third of
core.py rather than to the wholesale `core.py` -> `settings.py` rename the bead
originally proposed.

WHY THESE FOUR AND WHY `edgar.dates`. The settings extraction's own docstring
names what was left behind: "quarter math, HTML sniffing, a pager, thread helpers,
`Result` and the logger". The quarter math is the piece with a canonical home that
already exists -- `edgar/dates.py` was already the module for turning a user's
dates into something the SEC APIs accept -- so it goes there rather than to a new
module invented for it. `ZoneInfo` and `BDay` were imported by core.py *only* for
these functions and left with them.

WHAT THIS FILE GUARDS:

1. **The implementation MOVED; core.py is the wrapper.** The 07lk.23 rename trap.
   If the code had stayed in core.py with dates.py aliasing onto it, the real
   implementation would sit at the path 6.0 deletes, and dropping the shim would
   take it along. Asserted by `__module__`, not by value.

2. **The re-exports are the SAME objects.** Every call site is a
   `from edgar.core import <name>`, so a re-export covers all of them -- but only
   if identity holds.

3. **The direction of the dependency**, parsed rather than grepped.

4. **The maths still answers correctly.** An extraction that silently changed a
   quarter boundary would pass every structural check above, so the boundaries are
   pinned to specific values -- including the year-spanning range, which is the
   case with real arithmetic in it.
"""
import ast
import datetime

import edgar.core
import edgar.dates

MOVED_NAMES = [
    "current_year_and_quarter",
    "filing_date_to_year_quarters",
    "is_start_of_quarter",
    "parse_acceptance_datetime",
]


class TestTheImplementationMoved:
    """Moved to the canonical name, not aliased onto the deprecated one."""

    def test_functions_are_defined_in_edgar_dates(self):
        for name in MOVED_NAMES:
            fn = getattr(edgar.dates, name)
            assert fn.__module__ == "edgar.dates", (
                f"{name} reports __module__={fn.__module__!r}; the implementation "
                f"must live at the canonical name so 6.0 can drop the edgar.core "
                f"shim without taking the implementation with it"
            )


class TestCoreStillReExportsThem:
    """The shim, removed in 6.0."""

    def test_every_moved_name_is_reachable_from_core(self):
        missing = [n for n in MOVED_NAMES if not hasattr(edgar.core, n)]
        assert not missing, f"edgar.core stopped re-exporting: {missing}"

    def test_re_exports_are_the_same_objects(self):
        for name in MOVED_NAMES:
            assert getattr(edgar.core, name) is getattr(edgar.dates, name), (
                f"edgar.core.{name} is a different object from edgar.dates.{name}"
            )

    def test_core_imports_dates_and_not_the_reverse(self):
        """Parsed, not searched: dates.py names `edgar.core` in its docstring."""

        def imported_modules(module) -> set:
            tree = ast.parse(open(module.__file__).read())
            return {n.module for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module}

        assert "edgar.dates" in imported_modules(edgar.core)
        assert "edgar.core" not in imported_modules(edgar.dates), (
            "edgar.dates must not depend on edgar.core -- that would make the "
            "deprecation shim a circular import"
        )


class TestWhatDeliberatelyStayedInCore:
    """The rest of the grab-bag. It keeps its name until something else earns one."""

    def test_non_date_names_did_not_move(self):
        for name in ("listify", "has_html_content", "is_probably_html", "strtobool",
                     "get_bool", "parallel_thread_map", "DataPager", "Result"):
            assert hasattr(edgar.core, name)
            assert not hasattr(edgar.dates, name), (
                f"{name} is not date reasoning and should not have moved"
            )


class TestTheMathIsUnchanged:
    """Ground truth. Structural checks above all pass on wrong arithmetic."""

    def test_a_single_date_maps_to_its_own_quarter(self):
        assert edgar.dates.filing_date_to_year_quarters("2024-03-01") == [(2024, 1)]
        assert edgar.dates.filing_date_to_year_quarters("2024-04-10") == [(2024, 2)]
        assert edgar.dates.filing_date_to_year_quarters("2024-12-31") == [(2024, 4)]

    def test_quarter_boundaries_are_inclusive_at_the_month_edges(self):
        """March 31 is Q1 and April 1 is Q2 -- the off-by-one that (m-1)//3 exists
        to get right, and the one a careless rewrite would invert."""
        assert edgar.dates.filing_date_to_year_quarters("2024-03-31") == [(2024, 1)]
        assert edgar.dates.filing_date_to_year_quarters("2024-04-01") == [(2024, 2)]

    def test_a_range_inside_one_year_yields_only_the_quarters_it_spans(self):
        assert edgar.dates.filing_date_to_year_quarters("2024-02-01:2024-08-15") == [
            (2024, 1), (2024, 2), (2024, 3)
        ]

    def test_a_range_across_years_fills_the_middle_years_completely(self):
        assert edgar.dates.filing_date_to_year_quarters("2022-11-01:2024-02-01") == [
            (2022, 4),
            (2023, 1), (2023, 2), (2023, 3), (2023, 4),
            (2024, 1),
        ]

    def test_an_open_start_runs_from_the_first_full_index_quarter(self):
        """The SEC full-index begins 1993 Q1; an empty start means "from there"."""
        quarters = edgar.dates.filing_date_to_year_quarters(":1993-04-01")
        assert quarters == [(1993, 1), (1993, 2)]

    def test_current_year_and_quarter_is_computed_in_eastern_time(self):
        """Eastern, not local. The SEC publishes on Eastern, so a machine in UTC+13
        must not report next quarter on the last evening of this one."""
        from zoneinfo import ZoneInfo

        now_eastern = datetime.datetime.now(ZoneInfo("America/New_York"))
        expected = (now_eastern.year, (now_eastern.month - 1) // 3 + 1)
        assert edgar.dates.current_year_and_quarter() == expected

    def test_acceptance_datetimes_parse_the_zulu_suffix_sec_sends(self):
        parsed = edgar.dates.parse_acceptance_datetime("2024-03-01T17:30:00.000Z")
        assert parsed.year == 2024 and parsed.month == 3 and parsed.day == 1
        assert parsed.hour == 17 and parsed.minute == 30
        assert parsed.tzinfo is not None, "the Z must survive as a UTC offset"
