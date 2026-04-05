#!/usr/bin/env python3
"""
Review CLI for AI Mapping Suggestions

CLI tool designed for automated agents (like Claude Code) to review and approve
concept mapping suggestions from the AI mapper.

Usage:
    # Show pending suggestions
    python -m edgar.xbrl.standardization.review_cli --show-pending --limit 10
    
    # Approve a mapping
    python -m edgar.xbrl.standardization.review_cli --approve "AccruedLiabilities" --maps-to "AccruedLiabilities"
    
    # Auto-approve high confidence suggestions
    python -m edgar.xbrl.standardization.review_cli --auto-approve-high
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# Default paths
SUGGESTIONS_FILE = Path('sandbox/data/ai_suggestions.json')
REVIEW_HISTORY_FILE = Path('sandbox/data/review_history.json')
CONCEPT_MAPPINGS_FILE = Path('edgar/xbrl/standardization/concept_mappings.json')


def load_suggestions(path: Path = SUGGESTIONS_FILE) -> List[Dict]:
    """Load pending AI suggestions."""
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_suggestions(suggestions: List[Dict], path: Path = SUGGESTIONS_FILE):
    """Save updated suggestions."""
    with open(path, 'w') as f:
        json.dump(suggestions, f, indent=2)


def load_review_history(path: Path = REVIEW_HISTORY_FILE) -> List[Dict]:
    """Load review history."""
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def save_review_history(history: List[Dict], path: Path = REVIEW_HISTORY_FILE):
    """Save review history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(history, f, indent=2)


def load_concept_mappings(path: Path = CONCEPT_MAPPINGS_FILE) -> Dict:
    """Load existing concept mappings."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_concept_mappings(mappings: Dict, path: Path = CONCEPT_MAPPINGS_FILE):
    """Save updated concept mappings."""
    with open(path, 'w') as f:
        json.dump(mappings, f, indent=2)


def show_pending(suggestions: List[Dict], limit: int = 10, confidence_filter: str = None):
    """Display pending suggestions for review."""
    filtered = suggestions
    
    if confidence_filter:
        filtered = [s for s in suggestions if s.get('confidence') == confidence_filter]
    
    # Exclude already approved or UNKNOWN
    filtered = [s for s in filtered if s.get('suggested_mapping') not in ['UNKNOWN', 'ERROR']]
    
    if not filtered:
        print("No pending suggestions to review.")
        return
    
    print(f"\n=== Pending Suggestions ({len(filtered)} total) ===\n")
    
    for i, s in enumerate(filtered[:limit]):
        confidence_icon = '✅' if s['confidence'] == 'high' else '⚠️' if s['confidence'] == 'medium' else '❌'
        print(f"[{i+1}] {s['concept']}")
        print(f"    Label: {s['label']}")
        print(f"    {confidence_icon} Suggested: {s['suggested_mapping']} ({s['confidence']})")
        print(f"    Reasoning: {s.get('reasoning', 'N/A')}")
        print()
    
    if len(filtered) > limit:
        print(f"... and {len(filtered) - limit} more. Use --limit to show more.")
    
    # Show top 5 high confidence for agent context
    high_conf = [s for s in filtered if s['confidence'] == 'high']
    if high_conf:
        print("\n### Top 5 High-Confidence Mappings (recommended for auto-approve) ###")
        for s in high_conf[:5]:
            print(f"  --approve \"{s['concept']}\" --maps-to \"{s['suggested_mapping']}\"")


def approve_mapping(
    concept: str,
    maps_to: str,
    suggestions: List[Dict],
    history: List[Dict],
    mappings: Dict
) -> bool:
    """Approve a mapping suggestion."""
    # Find the suggestion
    found = None
    for s in suggestions:
        if s['concept'] == concept:
            found = s
            break
    
    if not found:
        print(f"Error: Concept '{concept}' not found in suggestions.")
        return False
    
    # Add to concept mappings
    if maps_to not in mappings:
        mappings[maps_to] = []
    
    if concept not in mappings[maps_to]:
        mappings[maps_to].append(concept)
        print(f"✅ Added mapping: {concept} → {maps_to}")
    else:
        print(f"ℹ️ Mapping already exists: {concept} → {maps_to}")
    
    # Record in history
    history.append({
        'timestamp': datetime.now().isoformat(),
        'action': 'approve',
        'concept': concept,
        'maps_to': maps_to,
        'original_suggestion': found.get('suggested_mapping'),
        'confidence': found.get('confidence'),
        'reasoning': found.get('reasoning')
    })
    
    # Remove from suggestions
    suggestions[:] = [s for s in suggestions if s['concept'] != concept]
    
    return True


def reject_mapping(concept: str, suggestions: List[Dict], history: List[Dict]) -> bool:
    """Reject a mapping suggestion."""
    # Find and remove
    found = None
    for s in suggestions:
        if s['concept'] == concept:
            found = s
            break
    
    if not found:
        print(f"Error: Concept '{concept}' not found in suggestions.")
        return False
    
    # Record in history
    history.append({
        'timestamp': datetime.now().isoformat(),
        'action': 'reject',
        'concept': concept,
        'original_suggestion': found.get('suggested_mapping'),
        'confidence': found.get('confidence'),
        'reasoning': found.get('reasoning')
    })
    
    # Remove from suggestions
    suggestions[:] = [s for s in suggestions if s['concept'] != concept]
    
    print(f"❌ Rejected: {concept}")
    return True


def auto_approve_high(suggestions: List[Dict], history: List[Dict], mappings: Dict) -> int:
    """Auto-approve all high confidence suggestions."""
    high_conf = [s for s in suggestions 
                 if s.get('confidence') == 'high' 
                 and s.get('suggested_mapping') not in ['UNKNOWN', 'ERROR']]
    
    count = 0
    for s in high_conf:
        if approve_mapping(s['concept'], s['suggested_mapping'], suggestions, history, mappings):
            count += 1
    
    return count


def main():
    parser = argparse.ArgumentParser(description='Review AI mapping suggestions')
    parser.add_argument('--show-pending', action='store_true', help='Show pending suggestions')
    parser.add_argument('--limit', type=int, default=10, help='Max items to show')
    parser.add_argument('--confidence', type=str, choices=['high', 'medium', 'low'],
                        help='Filter by confidence level')
    parser.add_argument('--approve', type=str, help='Concept to approve')
    parser.add_argument('--maps-to', type=str, help='Standard concept to map to')
    parser.add_argument('--reject', type=str, help='Concept to reject')
    parser.add_argument('--auto-approve-high', action='store_true',
                        help='Auto-approve all high confidence suggestions')
    parser.add_argument('--suggestions-file', type=str, default=str(SUGGESTIONS_FILE),
                        help='Path to suggestions JSON')
    
    args = parser.parse_args()
    
    suggestions_path = Path(args.suggestions_file)
    
    # Load data
    suggestions = load_suggestions(suggestions_path)
    history = load_review_history()
    mappings = load_concept_mappings()
    
    if args.show_pending:
        show_pending(suggestions, limit=args.limit, confidence_filter=args.confidence)
        return
    
    if args.auto_approve_high:
        count = auto_approve_high(suggestions, history, mappings)
        if count > 0:
            save_suggestions(suggestions, suggestions_path)
            save_review_history(history)
            save_concept_mappings(mappings)
            print(f"\n✅ Auto-approved {count} high-confidence mappings.")
        else:
            print("No high-confidence mappings to auto-approve.")
        return
    
    if args.approve:
        if not args.maps_to:
            print("Error: --maps-to required when using --approve")
            return
        
        if approve_mapping(args.approve, args.maps_to, suggestions, history, mappings):
            save_suggestions(suggestions, suggestions_path)
            save_review_history(history)
            save_concept_mappings(mappings)
        return
    
    if args.reject:
        if reject_mapping(args.reject, suggestions, history):
            save_suggestions(suggestions, suggestions_path)
            save_review_history(history)
        return
    
    # Default: show help
    parser.print_help()


if __name__ == '__main__':
    main()
