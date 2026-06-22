# Back-compat shim — this module moved to edgar.offerings.prospectus._s1_classifier (edgartools-n094.7).
# Re-exports the full surface (public + underscored) so existing
# `from edgar.offerings._s1_classifier import ...` imports keep resolving.
from edgar.offerings.prospectus import _s1_classifier as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
