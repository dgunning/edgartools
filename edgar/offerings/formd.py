# Back-compat shim — this module moved to edgar.offerings.exempt.formd (edgartools-n094.7).
# Re-exports the full surface (public + underscored) so existing
# `from edgar.offerings.formd import ...` imports keep resolving.
from edgar.offerings.exempt import formd as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
