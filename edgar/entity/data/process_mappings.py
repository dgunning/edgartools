#!/usr/bin/env python3
"""
Process the learned canonical structures into a simplified mappings file
optimized for the Facts API.
"""

import json


def process_mappings():
    """Convert canonical structures to simple concept->statement mappings."""
    
    # Load canonical structures
    with open('learned_mappings.json', 'r') as f:
        canonical = json.load(f)
    
    # Create simplified mappings
    mappings = {}
    metadata = {
        'version': '1.0.0',
        'generated': '2025-08-13',
        'companies_analyzed': 133,
        'source': 'structural_learning_production_run'
    }
    
    # Process each statement type
    for statement_type, concepts in canonical.items():
        for concept_data in concepts:
            concept = concept_data['concept']
            
            # Only include high-confidence mappings
            if concept_data['occurrence_rate'] >= 0.3:  # 30% threshold
                mappings[concept] = {
                    'statement_type': statement_type,
                    'confidence': concept_data['occurrence_rate'],
                    'label': concept_data['label'],
                    'parent': concept_data.get('parent'),
                    'is_abstract': concept_data.get('is_abstract', False),
                    'is_total': concept_data.get('is_total', False),
                    'section': concept_data.get('section'),
                    'avg_depth': concept_data.get('avg_depth', 0)
                }
    
    # Save processed mappings
    output = {
        'metadata': metadata,
        'mappings': mappings
    }
    
    with open('statement_mappings_v1.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Processed {len(mappings)} concept mappings")
    print("Statement distribution:")
    
    stmt_counts = {}
    for concept, data in mappings.items():
        stmt = data['statement_type']
        stmt_counts[stmt] = stmt_counts.get(stmt, 0) + 1
    
    for stmt, count in sorted(stmt_counts.items()):
        print(f"  {stmt}: {count}")

if __name__ == "__main__":
    process_mappings()