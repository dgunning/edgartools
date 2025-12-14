"""
Utility modules for HTML parsing.
"""

from edgar.documents.utils.cache import CacheManager, CacheStats, LRUCache, TimeBasedCache, WeakCache, cached, get_cache_manager
from edgar.documents.utils.currency_merger import CurrencyColumnMerger

# Note: CacheableMixin not exported to avoid circular imports
# Import directly: from edgar.documents.cache_mixin import CacheableMixin
from edgar.documents.utils.html_utils import create_lxml_parser, remove_xml_declaration
from edgar.documents.utils.streaming import StreamingParser
from edgar.documents.utils.table_matrix import ColumnAnalyzer, MatrixCell, TableMatrix

# Note: table_utils not exported to avoid circular imports
# Import directly: from edgar.documents.utils.table_utils import process_table_matrix

__all__ = [
    'LRUCache',
    'WeakCache',
    'TimeBasedCache',
    'CacheManager',
    'get_cache_manager',
    'cached',
    'CacheStats',
    'StreamingParser',
    'TableMatrix',
    'ColumnAnalyzer',
    'MatrixCell',
    'CurrencyColumnMerger',
    # 'CacheableMixin',  # Not exported - import directly to avoid circular imports
    'remove_xml_declaration',
    'create_lxml_parser',
    # 'process_table_matrix'  # Not exported - import directly to avoid circular imports
]
