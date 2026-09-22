"""MA-I municipal advisor registration filings.

`edgar/muniadvisors.py` became this package (bead edgartools-07lk.12.1), with
the parser itself in `core.py`, matching `edgar/ownership/` and `edgar/entity/`.

THIS IS NOT A DEPRECATION AND NOTHING MOVED for a caller: a module converting
to a package of the same name keeps `edgar.muniadvisors` resolving exactly as
it did, so `from edgar.muniadvisors import MunicipalAdvisorForm` is unchanged
and no shim is needed. That is what makes this move free where `edgar.effect`
and `edgar.form144` — which changed dotted path — each needed one.

`__all__` names only `MunicipalAdvisorForm`, but the module carried 19 public
top-level names that attribute access could reach (`Disclosures`, `Applicant`,
the disclosure dataclasses). Re-exporting `__all__` alone would quietly drop
the other 18, so the fallback below forwards every attribute, preserving object
identity and staying correct as `core` grows.
"""

from edgar.muniadvisors import core as _core
from edgar.muniadvisors.core import MunicipalAdvisorForm

__all__ = ['MunicipalAdvisorForm']


def __getattr__(name: str):
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__():
    return sorted(set(__all__) | set(dir(_core)))
