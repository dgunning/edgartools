"""
Layer 2: AI Semantic Mapper

Uses LLM to map concepts that Layer 1 (tree parser) couldn't match.
Provides tree context to help AI make better decisions.

Key capabilities:
1. Takes unmapped concepts with tree context
2. Uses LLM to suggest mappings
3. Returns with confidence and reasoning
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..config_loader import get_config, MappingConfig
from ..models import (
    MappingResult, MappingSource, ConfidenceLevel,
    MetricConfig
)


# System prompt for the AI
SYSTEM_PROMPT = """You are a financial data expert specializing in XBRL concept mapping.

Your task is to determine if an XBRL concept matches a standard financial metric.

For each concept, you will receive:
- The XBRL concept name
- Its position in the calculation tree (parent, siblings, weight)
- The target metric we're trying to find

Respond in JSON format:
{
    "matches": true/false,
    "confidence": "high"/"medium"/"low",
    "reasoning": "Brief explanation"
}

Guidelines:
- "high" confidence: Exact or near-exact semantic match
- "medium" confidence: Conceptually similar but not exact
- "low" confidence: Possible match but uncertain
- Consider the calculation tree context (parent, weight) for accuracy
- Weight of -1.0 typically means a cost/expense (subtracted)
- Weight of +1.0 typically means revenue/income (added)
"""


class AISemanticMapper:
    """
    Layer 2: Uses LLM to map concepts that tree parser couldn't match.
    """
    
    def __init__(
        self,
        config: Optional[MappingConfig] = None,
        model: str = "mistralai/devstral-2512:free"
    ):
        self.config = config or get_config()
        self.model = model
        self.client = self._init_client()
        self._thresholds = self.config.defaults.get("confidence_thresholds", {
            "ai_high": 0.90,
            "ai_medium": 0.70
        })
    
    def _init_client(self) -> Optional[OpenAI]:
        """Initialize OpenAI client for OpenRouter."""
        if OpenAI is None:
            print("Warning: openai package not installed")
            return None
            
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print("Warning: OPENROUTER_API_KEY not set")
            return None
            
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
    
    def map_gaps(
        self,
        tree_results: Dict[str, MappingResult],
        xbrl,
        ticker: str,
        fiscal_period: str
    ) -> Dict[str, MappingResult]:
        """
        Map concepts that tree parser couldn't find.
        
        Args:
            tree_results: Results from Layer 1 tree parser
            xbrl: XBRL object with calculation trees
            ticker: Company ticker
            fiscal_period: Fiscal period string
            
        Returns:
            Updated results with AI mappings for gaps
        """
        results = dict(tree_results)
        
        # Find gaps (unmapped concepts)
        gaps = [
            metric for metric, result in results.items()
            if not result.is_mapped and result.source != MappingSource.CONFIG
        ]
        
        if not gaps:
            return results
        
        print(f"  AI processing {len(gaps)} gaps: {gaps}")
        
        # Get all concepts from tree for searching
        all_concepts = self._get_all_concepts(xbrl)
        
        for metric_name in gaps:
            metric_config = self.config.get_metric(metric_name)
            if metric_config is None:
                continue
            
            # Search for candidate concepts
            candidates = self._find_candidates(metric_config, all_concepts)
            
            if not candidates:
                continue
            
            # Use AI to evaluate top candidates
            best_match = self._evaluate_candidates(
                metric_config, candidates, ticker
            )
            
            if best_match:
                concept, confidence, reasoning = best_match
                results[metric_name] = MappingResult(
                    metric=metric_name,
                    company=ticker,
                    fiscal_period=fiscal_period,
                    concept=concept,
                    confidence=confidence,
                    confidence_level=self._get_confidence_level(confidence),
                    source=MappingSource.AI,
                    reasoning=reasoning,
                    tree_context=all_concepts.get(
                        concept.replace('us-gaap:', ''), {}
                    )
                )
        
        return results
    
    def _get_all_concepts(self, xbrl) -> Dict[str, Dict]:
        """Extract all concepts from calculation trees with context."""
        concepts = {}
        
        for role, tree in xbrl.calculation_trees.items():
            tree_name = role.split('/')[-1] if '/' in role else role
            
            for node_id, node in tree.all_nodes.items():
                concept = node_id.replace('us-gaap_', '').replace('us-gaap:', '')
                
                if concept not in concepts:
                    concepts[concept] = {
                        'full_id': node_id,
                        'trees': [],
                        'parent': node.parent,
                        'children': node.children,
                        'weight': node.weight
                    }
                concepts[concept]['trees'].append(tree_name)
        
        return concepts
    
    def _find_candidates(
        self,
        metric_config: MetricConfig,
        all_concepts: Dict[str, Dict]
    ) -> List[Tuple[str, Dict]]:
        """
        Find candidate concepts that might match the metric.
        Uses keyword matching and tree hints.
        """
        candidates = []
        
        # Get keywords from metric name and known concepts
        keywords = self._extract_keywords(metric_config)
        
        for concept, context in all_concepts.items():
            concept_lower = concept.lower()
            
            # Check if any keyword matches
            score = sum(1 for kw in keywords if kw in concept_lower)
            
            if score > 0:
                candidates.append((concept, context, score))
        
        # Sort by score and return top candidates
        candidates.sort(key=lambda x: -x[2])
        return [(c, ctx) for c, ctx, _ in candidates[:5]]
    
    def _extract_keywords(self, metric_config: MetricConfig) -> List[str]:
        """Extract search keywords from metric config."""
        keywords = []
        
        # From metric name
        name = metric_config.name.lower()
        keywords.extend([
            name,
            name.replace('and', ''),
        ])
        
        # From known concepts
        for concept in metric_config.known_concepts:
            # Split camelCase
            words = []
            current = []
            for c in concept:
                if c.isupper() and current:
                    words.append(''.join(current).lower())
                    current = [c]
                else:
                    current.append(c)
            if current:
                words.append(''.join(current).lower())
            keywords.extend(words)
        
        # Remove common words
        stopwords = {'and', 'or', 'the', 'of', 'from', 'to', 'in', 'for'}
        keywords = [k for k in keywords if k not in stopwords and len(k) > 2]
        
        return list(set(keywords))
    
    def _evaluate_candidates(
        self,
        metric_config: MetricConfig,
        candidates: List[Tuple[str, Dict]],
        ticker: str
    ) -> Optional[Tuple[str, float, str]]:
        """
        Use AI to evaluate candidate concepts.
        Returns (concept, confidence, reasoning) if match found.
        """
        if self.client is None:
            # Fallback: use simple heuristics
            return self._evaluate_without_ai(metric_config, candidates)
        
        for concept, context in candidates:
            result = self._ask_ai(metric_config, concept, context)
            if result and result.get('matches'):
                confidence = self._confidence_to_score(result.get('confidence', 'low'))
                if confidence >= self._thresholds.get('ai_medium', 0.70):
                    return (
                        f"us-gaap:{concept}",
                        confidence,
                        result.get('reasoning', 'AI match')
                    )
        
        return None
    
    def _ask_ai(
        self,
        metric_config: MetricConfig,
        concept: str,
        context: Dict
    ) -> Optional[Dict]:
        """Query the LLM for a single concept evaluation."""
        try:
            prompt = f"""
Evaluate if this XBRL concept matches the target metric:

Target Metric: {metric_config.name}
Description: {metric_config.description}

XBRL Concept: {concept}
Tree Context:
  - Parent: {context.get('parent', 'None')}
  - Weight: {context.get('weight', 'Unknown')}
  - Trees: {', '.join(context.get('trees', [])[:3])}

Does this concept represent {metric_config.name}?
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            if '{' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                return json.loads(content[start:end])
            
            return None
            
        except Exception as e:
            print(f"    AI error for {concept}: {e}")
            return None
    
    def _evaluate_without_ai(
        self,
        metric_config: MetricConfig,
        candidates: List[Tuple[str, Dict]]
    ) -> Optional[Tuple[str, float, str]]:
        """Fallback evaluation without AI."""
        for concept, context in candidates:
            # Check if concept name is very similar to known concepts
            for known in metric_config.known_concepts:
                if known.lower() in concept.lower() or concept.lower() in known.lower():
                    return (
                        f"us-gaap:{concept}",
                        0.75,
                        f"Partial match with {known}"
                    )
            
            # Check tree hints
            hints = metric_config.tree_hints
            if hints.get('weight') and context.get('weight') == hints['weight']:
                if hints.get('section') and hints['section'] in str(context.get('trees', [])).lower():
                    return (
                        f"us-gaap:{concept}",
                        0.70,
                        f"Matches tree hints"
                    )
        
        return None
    
    def _confidence_to_score(self, level: str) -> float:
        """Convert confidence level string to numeric score."""
        levels = {
            'high': self._thresholds.get('ai_high', 0.90),
            'medium': self._thresholds.get('ai_medium', 0.70),
            'low': 0.50
        }
        return levels.get(level.lower(), 0.50)
    
    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to level."""
        if confidence >= self._thresholds.get('ai_high', 0.90):
            return ConfidenceLevel.HIGH
        elif confidence >= self._thresholds.get('ai_medium', 0.70):
            return ConfidenceLevel.MEDIUM
        elif confidence > 0:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.NONE
