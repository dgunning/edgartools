#!/usr/bin/env python3
"""
AI Mapping Agent for Concept Discovery

Uses LLM (via OpenRouter) to suggest mappings for unmapped XBRL concepts.

Usage:
    python -m edgar.xbrl.standardization.ai_mapper --input unmapped.csv --limit 10
    python -m edgar.xbrl.standardization.ai_mapper --concept "IncomeLossBeforeTax" --label "Income Before Tax"

Environment:
    OPENROUTER_API_KEY: Your OpenRouter API key
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from openai import OpenAI


# Available models on OpenRouter (free tier)
MODELS = {
    'devstral': 'mistralai/devstral-2512:free',
    'gpt-oss': 'openai/gpt-oss-120b',
}

DEFAULT_MODEL = 'devstral'

# Standard concepts we can map to (from concept_mappings.json)
STANDARD_CONCEPTS = [
    'Revenue', 'COGS', 'SGA', 'OperatingIncome', 'PretaxIncome', 'NetIncome',
    'OperatingCashFlow', 'Capex', 'TotalAssets', 'Goodwill', 'IntangibleAssets',
    'ShortTermDebt', 'LongTermDebt', 'CashAndEquivalents', 'GrossProfit',
    'TotalCurrentAssets', 'TotalCurrentLiabilities', 'TotalLiabilities',
    'TotalEquity', 'RetainedEarnings', 'CommonStock', 'AccountsReceivable',
    'AccountsPayable', 'Inventory', 'DeferredRevenue', 'AccruedLiabilities',
    'IncomeTaxExpense', 'InterestExpense', 'DepreciationAndAmortization',
    'ResearchAndDevelopment', 'SellingAndMarketing', 'GeneralAndAdministrative'
]

SYSTEM_PROMPT = """You are a financial analyst expert in XBRL taxonomy and SEC filings.

Your task is to map company-specific XBRL concepts to standardized financial metric names.

Rules:
1. Only suggest mappings from the provided list of standard concepts
2. Return "UNKNOWN" if the concept doesn't clearly map to any standard concept
3. Provide confidence: "high" (>90% sure), "medium" (70-90%), "low" (<70%)
4. Keep reasoning brief (1-2 sentences)

Respond ONLY with valid JSON in this exact format:
{
  "suggested_mapping": "Revenue",
  "confidence": "high",
  "reasoning": "Label contains 'revenue' and parent concept is Revenues"
}
"""


def create_client() -> OpenAI:
    """Create OpenRouter client."""
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable not set.\n"
            "Get your free key at: https://openrouter.ai/keys"
        )
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def suggest_mapping(
    client: OpenAI,
    concept: str,
    label: str,
    statement_type: str = "",
    calculation_parent: str = "",
    model: str = DEFAULT_MODEL
) -> Dict:
    """
    Use LLM to suggest a mapping for an unmapped concept.
    
    Returns dict with: suggested_mapping, confidence, reasoning
    """
    model_id = MODELS.get(model, MODELS[DEFAULT_MODEL])
    
    user_prompt = f"""Map this XBRL concept to a standard financial metric:

XBRL Concept: {concept}
Label: {label}
Statement Type: {statement_type or "Unknown"}
Calculation Parent: {calculation_parent or "None"}

Available standard concepts to map to:
{', '.join(STANDARD_CONCEPTS)}

If the concept doesn't clearly map to any of these, return "UNKNOWN" as the suggested_mapping."""

    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=200,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        # Handle markdown code blocks if present
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        
        result = json.loads(content)
        
        # Validate response
        if 'suggested_mapping' not in result:
            result['suggested_mapping'] = 'UNKNOWN'
        if 'confidence' not in result:
            result['confidence'] = 'low'
        if 'reasoning' not in result:
            result['reasoning'] = 'No reasoning provided'
        
        return result
        
    except json.JSONDecodeError as e:
        return {
            'suggested_mapping': 'UNKNOWN',
            'confidence': 'low',
            'reasoning': f'Failed to parse LLM response: {e}'
        }
    except Exception as e:
        return {
            'suggested_mapping': 'ERROR',
            'confidence': 'low',
            'reasoning': f'API error: {e}'
        }


def process_batch(
    concepts: List[Dict],
    model: str = DEFAULT_MODEL,
    dry_run: bool = False
) -> List[Dict]:
    """
    Process a batch of unmapped concepts.
    
    Each concept dict should have: concept, label, and optionally statement_type, calculation_parent
    """
    if dry_run:
        print("[DRY RUN] Would process the following concepts:")
        for c in concepts:
            print(f"  - {c.get('concept')}: {c.get('label')}")
        return []
    
    client = create_client()
    results = []
    
    for i, item in enumerate(concepts):
        print(f"Processing [{i+1}/{len(concepts)}]: {item.get('concept')}...")
        
        result = suggest_mapping(
            client=client,
            concept=item.get('concept', ''),
            label=item.get('label', ''),
            statement_type=item.get('statement_type', ''),
            calculation_parent=item.get('calculation_parent', ''),
            model=model
        )
        
        result['concept'] = item.get('concept')
        result['label'] = item.get('label')
        results.append(result)
        
        # Print result
        status = '✅' if result['confidence'] == 'high' else '⚠️' if result['confidence'] == 'medium' else '❌'
        print(f"  {status} → {result['suggested_mapping']} ({result['confidence']})")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='AI-powered concept mapping suggestions')
    parser.add_argument('--concept', type=str, help='Single concept to map')
    parser.add_argument('--label', type=str, help='Label for the concept')
    parser.add_argument('--input', type=str, help='JSON file with concepts to map')
    parser.add_argument('--output', type=str, help='Output JSON file for results')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL,
                        choices=list(MODELS.keys()), help='Model to use')
    parser.add_argument('--limit', type=int, default=10, help='Max concepts to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    
    args = parser.parse_args()
    
    # Single concept mode
    if args.concept:
        if not args.label:
            print("Error: --label required when using --concept")
            return
        
        if args.dry_run:
            print(f"[DRY RUN] Would map: {args.concept} ({args.label})")
            return
        
        client = create_client()
        result = suggest_mapping(client, args.concept, args.label, model=args.model)
        
        print(f"\nConcept: {args.concept}")
        print(f"Label: {args.label}")
        print(f"Suggested: {result['suggested_mapping']} ({result['confidence']})")
        print(f"Reasoning: {result['reasoning']}")
        return
    
    # Batch mode from file
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}")
            return
        
        with open(input_path) as f:
            data = json.load(f)
        
        # Handle coverage.py output format
        if isinstance(data, list) and data and 'unmapped_concepts' in data[0]:
            # Extract concepts from coverage report
            concepts = []
            for company in data:
                for concept in company.get('unmapped_concepts', []):
                    concepts.append({'concept': concept, 'label': concept})
            # Deduplicate
            seen = set()
            unique = []
            for c in concepts:
                if c['concept'] not in seen:
                    seen.add(c['concept'])
                    unique.append(c)
            concepts = unique
        else:
            concepts = data
        
        # Apply limit
        concepts = concepts[:args.limit]
        
        print(f"Processing {len(concepts)} concepts with model: {args.model}")
        print("-" * 50)
        
        results = process_batch(concepts, model=args.model, dry_run=args.dry_run)
        
        if results and args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {output_path}")
        
        # Summary
        if results:
            high = sum(1 for r in results if r['confidence'] == 'high')
            medium = sum(1 for r in results if r['confidence'] == 'medium')
            low = sum(1 for r in results if r['confidence'] == 'low')
            unknown = sum(1 for r in results if r['suggested_mapping'] == 'UNKNOWN')
            
            print(f"\n=== Summary ===")
            print(f"High confidence: {high}")
            print(f"Medium confidence: {medium}")
            print(f"Low confidence: {low}")
            print(f"Unknown: {unknown}")
        
        return
    
    # No input specified
    print("Usage:")
    print("  Single concept: --concept <concept> --label <label>")
    print("  Batch from file: --input <file.json> [--output <results.json>]")
    print("\nMake sure OPENROUTER_API_KEY is set in your environment.")


if __name__ == '__main__':
    main()
