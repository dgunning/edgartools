# Back-compat shim — this module lives at edgar.offerings.prospectus.registration_s4.
# Re-exports the full surface (public + underscored) so
# `from edgar.offerings.registration_s4 import ...` imports resolve, matching
# the registration_s1 / registration_s3 shims.
from edgar.offerings.prospectus import registration_s4 as _moved

globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
