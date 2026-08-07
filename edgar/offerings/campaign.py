# Back-compat shim — this module moved to edgar.offerings.crowdfunding.campaign (edgartools-n094.7).
# Re-exports the full surface (public + underscored) so existing
# `from edgar.offerings.campaign import ...` imports keep resolving.
from edgar.offerings.crowdfunding import campaign as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
