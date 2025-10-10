"""
Mixin class providing text caching functionality for document nodes.

This module consolidates the text caching pattern used across multiple node types
(DocumentNode, ParagraphNode, ContainerNode, TableNode, and Document).
"""

from typing import Callable, Any


class CacheableMixin:
    """
    Mixin providing text caching functionality for nodes.

    This mixin implements a lazy-evaluated text caching pattern that:
    1. Checks for existing cached text
    2. Generates text on first access via a generator function
    3. Caches the result for subsequent accesses
    4. Provides recursive cache clearing for tree structures

    Usage:
        class MyNode(CacheableMixin):
            def text(self, **kwargs):
                def generator():
                    # Generate text logic here
                    return "generated text"
                return self._get_cached_text(generator)
    """

    def _get_cached_text(self, generator_func: Callable[[], Any], *args, **kwargs) -> Any:
        """
        Get cached text or generate and cache it.

        This method implements the caching pattern:
        - If cache exists and is not None, return cached value
        - Otherwise, call generator function to create text
        - Store result in cache
        - Return the result

        Args:
            generator_func: Function that generates the text when cache miss occurs
            *args: Positional arguments to pass to generator (currently unused)
            **kwargs: Keyword arguments to pass to generator (currently unused)

        Returns:
            The cached or newly generated text

        Note:
            The cache is stored in the instance attribute '_text_cache'.
            Generator function is called without arguments in current implementation.
        """
        if hasattr(self, '_text_cache') and self._text_cache is not None:
            return self._text_cache

        # Generate text and cache it
        self._text_cache = generator_func(*args, **kwargs)
        return self._text_cache

    def clear_text_cache(self) -> None:
        """
        Clear cached text recursively.

        This method:
        1. Clears the text cache for this node (sets to None)
        2. Recursively clears cache for all children (if node has children)

        The recursive clearing ensures that when a parent node's content changes,
        all descendant nodes also have their caches invalidated.

        Safe to call even if:
        - Node doesn't have a cache (_text_cache attribute)
        - Node doesn't have children
        - Children don't have clear_text_cache method
        """
        # Clear own cache if it exists
        if hasattr(self, '_text_cache'):
            self._text_cache = None

        # Recursively clear children's caches
        if hasattr(self, 'children'):
            for child in self.children:
                if hasattr(child, 'clear_text_cache'):
                    child.clear_text_cache()
