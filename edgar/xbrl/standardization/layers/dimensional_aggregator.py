"""
Dimensional Aggregator Layer

Aggregates dimensional XBRL facts when consolidated totals are missing.
This addresses the "dimensional blind spot" where companies like JPM report
specific line items (e.g., Commercial Paper) ONLY under dimensions (e.g., VIEs).

Key XBRL Axes handled:
- us-gaap:VariableInterestEntitiesByClassificationOfEntityAxis (VIEs)  
- us-gaap:ProductOrServiceAxis (revenue breakdown)
- us-gaap:StatementBusinessSegmentsAxis (segment reporting)

Usage:
    from edgar.xbrl.standardization.layers.dimensional_aggregator import DimensionalAggregator
    
    aggregator = DimensionalAggregator()
    value = aggregator.aggregate_if_missing(xbrl, 'CommercialPaper', consolidated_value=0)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class AggregationResult:
    """Result of dimensional aggregation."""
    concept: str
    aggregated_value: Optional[float]
    dimension_count: int
    dimensions_used: List[str]
    method: str  # 'sum', 'max', etc.
    validation_status: str  # 'aggregated', 'validated', 'mismatch', 'no_data'
    notes: Optional[str] = None


class DimensionalAggregator:
    """
    Aggregates dimensional XBRL facts when consolidated totals are missing.
    
    Handles the case where companies report values ONLY with dimensional
    qualifiers (e.g., segment, VIE, product line) without a consolidated total.
    
    Also validates that Sum(Dimensional) ≈ Consolidated when both exist,
    to detect "orphaned" dimensional data.
    """
    
    # Aggregation rules by concept
    # Defines which Axes to include/exclude and aggregation method
    AGGREGATION_RULES: Dict[str, Dict[str, Any]] = {
        'CommercialPaper': {
            'include_axes': ['VariableInterestEntitiesByClassificationOfEntityAxis'],
            'exclude_axes': [],
            'method': 'sum',
            'notes': 'JPM reports CP only under VIE dimension'
        },
        'ShortTermBorrowings': {
            'include_axes': ['*'],  # Include all dimensional values
            'exclude_axes': ['StatementEquityComponentsAxis'],  # Exclude equity-related
            'method': 'sum',
            'notes': 'Sum all dimensional borrowings'
        },
        'LongTermDebt': {
            'include_axes': ['*'],
            'exclude_axes': [],
            'method': 'sum',
            'notes': 'Sum all debt segments'
        },
        'Revenue': {
            'include_axes': ['ProductOrServiceAxis', 'StatementBusinessSegmentsAxis'],
            'exclude_axes': [],
            'method': 'sum',
            'notes': 'Sum revenue by segment/product'
        },
    }
    
    # Tolerance for validation (Sum vs Consolidated)
    VALIDATION_TOLERANCE = 0.05  # 5%
    
    # Threshold for "placeholder zero" detection
    PLACEHOLDER_ZERO_THRESHOLD = 1_000_000  # $1M
    
    def __init__(self):
        self._cache = {}
    
    def should_aggregate(
        self,
        consolidated_value: Optional[float],
        dimensional_sum: float
    ) -> bool:
        """
        Determine if aggregation should be used instead of consolidated value.
        
        Triggers aggregation if:
        1. Consolidated value is None (missing)
        2. Consolidated value is 0 but dimensional sum is significant
           (handles "placeholder zero" cases)
        
        Args:
            consolidated_value: The non-dimensional consolidated value (may be None)
            dimensional_sum: Sum of dimensional values
            
        Returns:
            True if aggregation should be used
        """
        if consolidated_value is None:
            return True
        
        # Handle "placeholder zero" - consolidated is 0 but dimensions have data
        if consolidated_value == 0 and dimensional_sum > self.PLACEHOLDER_ZERO_THRESHOLD:
            return True
        
        return False
    
    def aggregate_if_missing(
        self,
        xbrl,
        concept: str,
        consolidated_value: Optional[float] = None
    ) -> AggregationResult:
        """
        Return aggregated dimensional value if consolidated is missing or zero.
        
        Args:
            xbrl: XBRL object with facts
            concept: Concept name to aggregate (e.g., 'CommercialPaper')
            consolidated_value: Known consolidated value (if any)
            
        Returns:
            AggregationResult with aggregated value and metadata
        """
        concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
        
        # Get dimensional facts
        dimensional_data = self._get_dimensional_facts(xbrl, concept_name)
        
        if not dimensional_data['facts']:
            return AggregationResult(
                concept=concept,
                aggregated_value=None,
                dimension_count=0,
                dimensions_used=[],
                method='none',
                validation_status='no_data',
                notes='No dimensional facts found'
            )
        
        # Apply aggregation rules
        rule = self.AGGREGATION_RULES.get(concept_name, {
            'include_axes': ['*'],
            'exclude_axes': [],
            'method': 'sum'
        })
        
        # Filter facts by axes
        filtered_facts = self._filter_by_axes(
            dimensional_data['facts'],
            rule['include_axes'],
            rule['exclude_axes']
        )
        
        if not filtered_facts:
            return AggregationResult(
                concept=concept,
                aggregated_value=None,
                dimension_count=0,
                dimensions_used=[],
                method=rule['method'],
                validation_status='no_data',
                notes='No facts matched aggregation rules'
            )
        
        # Aggregate values
        aggregated_value = self._aggregate_values(filtered_facts, rule['method'])
        dimensions_used = list(set(f.get('axis', 'unknown') for f in filtered_facts))
        
        # Check if aggregation should be used
        if not self.should_aggregate(consolidated_value, aggregated_value):
            return AggregationResult(
                concept=concept,
                aggregated_value=consolidated_value,
                dimension_count=len(filtered_facts),
                dimensions_used=dimensions_used,
                method='consolidated_preferred',
                validation_status='consolidated_exists',
                notes=f'Using consolidated value {consolidated_value}, dimensional sum was {aggregated_value}'
            )
        
        return AggregationResult(
            concept=concept,
            aggregated_value=aggregated_value,
            dimension_count=len(filtered_facts),
            dimensions_used=dimensions_used,
            method=rule['method'],
            validation_status='aggregated',
            notes=rule.get('notes', f'Aggregated {len(filtered_facts)} dimensional facts')
        )
    
    def validate_aggregation(
        self,
        xbrl,
        concept: str,
        consolidated_value: float
    ) -> Dict[str, Any]:
        """
        Check if Sum(Dimensional) ≈ Consolidated for data quality.
        
        Helps detect:
        - Orphaned dimensional data (dimensions sum to more than consolidated)
        - Missing dimensional data (dimensions sum to less than consolidated)
        
        Args:
            xbrl: XBRL object
            concept: Concept name
            consolidated_value: The consolidated (non-dimensional) value
            
        Returns:
            Dict with validation status and details
        """
        concept_name = concept.replace('us-gaap:', '').replace('us-gaap_', '')
        
        # Get dimensional sum
        result = self.aggregate_if_missing(xbrl, concept, consolidated_value=None)
        
        if result.aggregated_value is None:
            return {
                'status': 'no_dimensions',
                'consolidated': consolidated_value,
                'dimensional_sum': None,
                'variance_pct': None,
                'message': 'No dimensional data to validate'
            }
        
        # Calculate variance
        if consolidated_value == 0:
            variance_pct = 100.0 if result.aggregated_value != 0 else 0.0
        else:
            variance_pct = abs(result.aggregated_value - consolidated_value) / abs(consolidated_value) * 100
        
        is_valid = variance_pct <= self.VALIDATION_TOLERANCE * 100
        
        return {
            'status': 'valid' if is_valid else 'mismatch',
            'consolidated': consolidated_value,
            'dimensional_sum': result.aggregated_value,
            'variance_pct': variance_pct,
            'dimensions_used': result.dimensions_used,
            'message': f'Variance {variance_pct:.1f}% (tolerance {self.VALIDATION_TOLERANCE*100:.0f}%)'
        }
    
    def _get_dimensional_facts(
        self,
        xbrl,
        concept_name: str
    ) -> Dict[str, Any]:
        """Extract dimensional facts for a concept."""
        try:
            facts = xbrl.facts
            df = facts.get_facts_by_concept(concept_name)
            
            if df is None or len(df) == 0:
                return {'facts': [], 'period': None}
            
            # Filter for dimensional values only
            if 'full_dimension_label' not in df.columns:
                return {'facts': [], 'period': None}
            
            dim_rows = df[df['full_dimension_label'].notna()]
            dim_rows = dim_rows[dim_rows['numeric_value'].notna()]
            
            if len(dim_rows) == 0:
                return {'facts': [], 'period': None}
            
            # Get latest period
            latest_period = None
            if 'period_key' in dim_rows.columns:
                dim_rows = dim_rows.sort_values('period_key', ascending=False)
                latest_period = dim_rows.iloc[0]['period_key']
                dim_rows = dim_rows[dim_rows['period_key'] == latest_period]
            
            # Convert to list of dicts
            facts_list = []
            for _, row in dim_rows.iterrows():
                # Extract axis from dimension label
                dim_label = row['full_dimension_label']
                axis = self._extract_axis_from_label(dim_label)
                
                facts_list.append({
                    'value': float(row['numeric_value']),
                    'dimension_label': dim_label,
                    'axis': axis,
                    'period': row.get('period_key', None)
                })
            
            return {
                'facts': facts_list,
                'period': latest_period
            }
            
        except Exception as e:
            return {'facts': [], 'period': None, 'error': str(e)}
    
    def _extract_axis_from_label(self, dimension_label: str) -> str:
        """Extract the Axis name from a full dimension label."""
        if not dimension_label:
            return 'unknown'
        
        # Dimension labels typically look like:
        # "VariableInterestEntitiesByClassificationOfEntityAxis=ConsolidatedVIEsMember"
        # or "Segment [Axis] = Consumer Banking [Member]"
        
        if '=' in dimension_label:
            return dimension_label.split('=')[0].strip()
        elif '[Axis]' in dimension_label:
            return dimension_label.split('[Axis]')[0].strip()
        
        return dimension_label.split()[0] if dimension_label else 'unknown'
    
    def _filter_by_axes(
        self,
        facts: List[Dict],
        include_axes: List[str],
        exclude_axes: List[str]
    ) -> List[Dict]:
        """Filter facts based on axis inclusion/exclusion rules."""
        filtered = []
        
        for fact in facts:
            axis = fact.get('axis', '')
            
            # Check exclusions first
            if any(excl.lower() in axis.lower() for excl in exclude_axes):
                continue
            
            # Check inclusions
            if '*' in include_axes:
                # Include all (except excluded)
                filtered.append(fact)
            elif any(incl.lower() in axis.lower() for incl in include_axes):
                filtered.append(fact)
        
        return filtered
    
    def _aggregate_values(
        self,
        facts: List[Dict],
        method: str
    ) -> float:
        """Aggregate fact values using specified method."""
        values = [f['value'] for f in facts]
        
        if not values:
            return 0.0
        
        if method == 'sum':
            return sum(values)
        elif method == 'max':
            return max(values)
        elif method == 'avg':
            return sum(values) / len(values)
        else:
            return sum(values)  # Default to sum
