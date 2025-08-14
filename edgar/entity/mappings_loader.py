"""
Loader for learned statement mappings and canonical structures.

This module handles loading and caching of learned mappings from the
structural learning process.
"""

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_learned_mappings() -> Dict[str, Dict[str, Any]]:
    """
    Load learned statement mappings from package data.
    
    Returns:
        Dictionary of concept -> mapping info
    """
    try:
        # Get the data file path
        data_dir = Path(__file__).parent / 'data'
        mappings_file = data_dir / 'statement_mappings_v1.json'
        
        if not mappings_file.exists():
            log.warning(f"Learned mappings file not found: {mappings_file}")
            return {}
        
        with open(mappings_file, 'r') as f:
            data = json.load(f)
        
        mappings = data.get('mappings', {})
        metadata = data.get('metadata', {})
        
        log.info(f"Loaded {len(mappings)} learned concept mappings "
                f"(version: {metadata.get('version', 'unknown')})")
        
        return mappings
        
    except Exception as e:
        log.error(f"Error loading learned mappings: {e}")
        return {}


@lru_cache(maxsize=1)
def load_canonical_structures() -> Dict[str, Any]:
    """
    Load canonical statement structures.
    
    Returns:
        Dictionary of statement_type -> canonical structure
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        structures_file = data_dir / 'learned_mappings.json'
        
        if not structures_file.exists():
            log.warning(f"Canonical structures file not found: {structures_file}")
            return {}
        
        with open(structures_file, 'r') as f:
            structures = json.load(f)
        
        log.info(f"Loaded canonical structures for {len(structures)} statement types")
        return structures
        
    except Exception as e:
        log.error(f"Error loading canonical structures: {e}")
        return {}


@lru_cache(maxsize=1)
def load_virtual_trees() -> Dict[str, Any]:
    """
    Load virtual presentation trees.
    
    Returns:
        Dictionary of statement_type -> virtual tree
    """
    try:
        data_dir = Path(__file__).parent / 'data'
        trees_file = data_dir / 'virtual_trees.json'
        
        if not trees_file.exists():
            log.warning(f"Virtual trees file not found: {trees_file}")
            return {}
        
        with open(trees_file, 'r') as f:
            trees = json.load(f)
        
        log.info(f"Loaded virtual trees for {len(trees)} statement types")
        return trees
        
    except Exception as e:
        log.error(f"Error loading virtual trees: {e}")
        return {}


def get_concept_mapping(concept: str) -> Optional[Dict[str, Any]]:
    """
    Get mapping information for a specific concept.
    
    Args:
        concept: Concept name (without namespace)
        
    Returns:
        Mapping info dict or None if not found
    """
    mappings = load_learned_mappings()
    return mappings.get(concept)


def get_statement_concepts(statement_type: str, 
                         min_confidence: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """
    Get all concepts for a specific statement type.
    
    Args:
        statement_type: Type of statement (BalanceSheet, IncomeStatement, etc.)
        min_confidence: Minimum confidence threshold
        
    Returns:
        Dictionary of concept -> mapping info
    """
    mappings = load_learned_mappings()
    
    result = {}
    for concept, info in mappings.items():
        if (info.get('statement_type') == statement_type and
            info.get('confidence', 0) >= min_confidence):
            result[concept] = info
    
    return result