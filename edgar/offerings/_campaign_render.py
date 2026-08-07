# Back-compat shim — this module moved to edgar.offerings.crowdfunding._campaign_render (edgartools-n094.7).
# Re-exports the full surface (public + underscored) so existing
# `from edgar.offerings._campaign_render import ...` imports keep resolving.
from edgar.offerings.crowdfunding import _campaign_render as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
