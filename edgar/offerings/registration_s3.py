# Back-compat shim — this module moved to edgar.offerings.prospectus.registration_s3 (edgartools-n094.7).
# Re-exports the full surface (public + underscored) so existing
# `from edgar.offerings.registration_s3 import ...` imports keep resolving.
from edgar.offerings.prospectus import registration_s3 as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
