"""
Storage providers for EdgarTools.

Re-exports from:
- _local: Local disk storage (download, compress, path helpers)
- _management: Analytics, optimization, cleanup
- datamule: Datamule tar-based filing source
"""

from edgar.storage._local import *
from edgar.storage._management import *
from edgar.storage.datamule import use_datamule_storage, is_using_datamule_storage
