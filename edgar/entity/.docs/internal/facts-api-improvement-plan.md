# Entity Facts API Improvement Plan & Design

## Executive Summary

This improvement plan transforms the Entity Facts API from a basic data access layer into an AI-ready, investment-focused analytics platform. Building on the strategic assessments, we prioritize developer experience, AI integration, and investment utility while maintaining backward compatibility.

## Vision & Goals

### Primary Vision
Transform the Entity Facts API into the premier interface for company-wide historical financial analysis, optimized for both traditional quantitative workflows and modern AI-powered investment strategies.

### Core Goals
1. **Unified Experience**: Consistent APIs and data models across entity and XBRL facts
2. **AI-First Design**: Rich contextual data optimized for LLMs and autonomous agents
3. **Investment Focus**: Built-in calculations, comparisons, and quality indicators
4. **Developer Delight**: Intuitive fluent APIs with comprehensive type safety
5. **Performance**: Sub-second responses with intelligent caching

## Design Principles

### 1. Progressive Disclosure
```python
# Simple usage for common tasks
company.facts.revenue()  # Just get revenue trend

# Advanced usage for power users
company.facts.query()\
    .by_concept('Revenue')\
    .with_dimensions('Geographic')\
    .time_series(periods=20)\
    .to_dataframe()
```

### 2. AI-Ready by Default
Every data point includes:
- Semantic context for LLMs
- Natural language descriptions
- Relationship metadata
- Confidence indicators

### 3. Investment-Centric
Built-in support for:
- Financial ratios and metrics
- Peer comparisons
- Trend analysis
- Anomaly detection

## Core Architecture

### Unified Data Model

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Union, Literal
from enum import Enum

class DataQuality(Enum):
    """Data quality indicators"""
    HIGH = "high"          # Direct from XBRL, validated
    MEDIUM = "medium"      # Derived or calculated
    LOW = "low"           # Estimated or inferred

@dataclass
class FinancialFact:
    """
    Unified fact representation optimized for both traditional analysis and AI consumption.
    """
    # Core identification
    concept: str                    # Standardized concept (e.g., 'us-gaap:Revenue')
    taxonomy: str                   # Taxonomy namespace
    label: str                      # Human-readable label
    
    # Values with proper typing
    value: Union[float, int, str]   # The actual value
    numeric_value: Optional[float]  # Numeric representation for calculations
    unit: str                       # Unit of measure (USD, shares, etc.)
    scale: Optional[int]            # Scale factor (thousands, millions)
    
    # Temporal context
    period_start: Optional[date]
    period_end: date
    period_type: Literal['instant', 'duration']
    fiscal_year: int
    fiscal_period: str              # FY, Q1, Q2, Q3, Q4
    
    # Filing context
    filing_date: date
    form_type: str                  # 10-K, 10-Q, 8-K, etc.
    accession: str                  # SEC accession number
    
    # Quality and provenance
    data_quality: DataQuality
    is_audited: bool
    is_restated: bool
    is_estimated: bool
    confidence_score: float         # 0.0 to 1.0
    
    # AI-ready context
    semantic_tags: list[str]        # ['revenue', 'recurring', 'operating']
    business_context: str           # "Product revenue from iPhone sales"
    calculation_context: Optional[str]  # "Derived from segment data"
    
    # Optional XBRL specifics
    context_ref: Optional[str] = None
    dimensions: Dict[str, str] = None
    statement_type: Optional[str] = None
    line_item_sequence: Optional[int] = None
    
    def to_llm_context(self) -> Dict[str, any]:
        """Generate rich context for LLM consumption"""
        return {
            "concept": self.label,
            "value": f"{self.numeric_value:,.0f}" if self.numeric_value else self.value,
            "unit": self.unit,
            "period": f"{self.fiscal_period} {self.fiscal_year}",
            "context": self.business_context,
            "quality": self.data_quality.value,
            "confidence": self.confidence_score,
            "tags": self.semantic_tags
        }
```

### Enhanced EntityFacts Class

```python
from typing import List, Dict, Optional, Iterator
import pandas as pd
from datetime import datetime

class EntityFacts:
    """
    AI-ready company facts with investment-focused analytics.
    """
    
    def __init__(self, cik: int, name: str, facts: List[FinancialFact]):
        self.cik = cik
        self.name = name
        self._facts = facts
        self._fact_index = self._build_indices()
        self._cache = {}
        
    def _build_indices(self) -> Dict:
        """Build optimized indices for fast querying"""
        return {
            'by_concept': defaultdict(list),
            'by_period': defaultdict(list),
            'by_statement': defaultdict(list),
            'by_form': defaultdict(list)
        }
    
    # Core query interface
    def query(self) -> 'FactQuery':
        """Start building a facts query"""
        return FactQuery(self._facts, self._fact_index)
    
    # Convenience methods for common queries
    def get_fact(self, concept: str, period: Optional[str] = None) -> Optional[FinancialFact]:
        """Get a single fact by concept and optional period"""
        query = self.query().by_concept(concept)
        if period:
            query = query.by_fiscal_period(period)
        facts = query.latest(1)
        return facts[0] if facts else None
    
    def time_series(self, concept: str, periods: int = 20) -> pd.DataFrame:
        """Get time series data for a concept"""
        return self.query()\
            .by_concept(concept)\
            .latest(periods)\
            .to_dataframe(columns=['period_end', 'numeric_value', 'fiscal_period'])
    
    # Financial statement helpers
    def income_statement(self, periods: int = 4) -> pd.DataFrame:
        """Get income statement facts for recent periods"""
        return self.query()\
            .by_statement_type('IncomeStatement')\
            .latest_periods(periods)\
            .pivot_by_period()
    
    def balance_sheet(self, as_of: Optional[date] = None) -> pd.DataFrame:
        """Get balance sheet facts as of a specific date"""
        query = self.query().by_statement_type('BalanceSheet')
        if as_of:
            query = query.as_of(as_of)
        else:
            query = query.latest_instant()
        return query.to_dataframe()
    
    def cash_flow(self, periods: int = 4) -> pd.DataFrame:
        """Get cash flow statement facts"""
        return self.query()\
            .by_statement_type('CashFlow')\
            .latest_periods(periods)\
            .pivot_by_period()
    
    # Investment analytics
    def calculate_ratios(self) -> Dict[str, float]:
        """Calculate common financial ratios"""
        analyzer = RatioAnalyzer(self)
        return analyzer.calculate_all()
    
    def peer_comparison(self, peer_ciks: List[int], 
                       metrics: Optional[List[str]] = None) -> pd.DataFrame:
        """Compare key metrics with peer companies"""
        comparator = PeerComparator(self)
        return comparator.compare(peer_ciks, metrics)
    
    def detect_anomalies(self) -> List[Dict[str, any]]:
        """Detect unusual patterns or potential red flags"""
        detector = AnomalyDetector(self)
        return detector.analyze()
    
    # AI-ready methods
    def to_llm_context(self, 
                      focus_areas: Optional[List[str]] = None,
                      time_period: str = "recent") -> Dict[str, any]:
        """
        Generate comprehensive context for LLM analysis.
        
        Args:
            focus_areas: Specific areas to emphasize (e.g., ['profitability', 'growth'])
            time_period: Time period to analyze ('recent', '5Y', '10Y', 'all')
        """
        context_builder = LLMContextBuilder(self)
        return context_builder.build(focus_areas, time_period)
    
    def to_agent_tools(self) -> List[Dict[str, any]]:
        """
        Export facts as tools for AI agents (MCP-compatible).
        """
        return [
            {
                "name": f"get_{self.name}_financials",
                "description": f"Retrieve financial data for {self.name}",
                "parameters": {
                    "statement": "Financial statement type",
                    "period": "Time period",
                    "concept": "Specific concept to retrieve"
                },
                "returns": "Financial data with context"
            },
            {
                "name": f"analyze_{self.name}_trends",
                "description": f"Analyze trends for {self.name}",
                "parameters": {
                    "metric": "Financial metric to analyze",
                    "periods": "Number of periods"
                },
                "returns": "Trend analysis with insights"
            }
        ]
    
    # Rich display
    def __rich__(self):
        """Rich display for interactive environments"""
        from rich.table import Table
        from rich.panel import Panel
        
        # Summary statistics
        total_facts = len(self._facts)
        unique_concepts = len(set(f.concept for f in self._facts))
        date_range = self._get_date_range()
        
        # Recent key metrics
        recent_metrics = self._get_recent_key_metrics()
        
        table = Table(title=f"{self.name} ({self.cik})")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Period", style="yellow")
        
        for metric in recent_metrics:
            table.add_row(metric['label'], metric['value'], metric['period'])
        
        summary = f"""
Total Facts: {total_facts:,}
Unique Concepts: {unique_concepts:,}
Date Range: {date_range}
        """
        
        return Panel(Group(summary, table))
```

### Fluent Query Interface

```python
class FactQuery:
    """
    Fluent query builder for financial facts with AI-ready features.
    """
    
    def __init__(self, facts: List[FinancialFact], indices: Dict):
        self._facts = facts
        self._indices = indices
        self._filters = []
        self._sort = None
        self._limit = None
        
    # Concept filtering
    def by_concept(self, concept: str, exact: bool = False) -> 'FactQuery':
        """Filter by concept name or pattern"""
        if exact:
            self._filters.append(lambda f: f.concept == concept)
        else:
            # Smart concept matching (handles variations)
            matcher = ConceptMatcher(concept)
            self._filters.append(lambda f: matcher.matches(f.concept))
        return self
    
    def by_label(self, label: str, fuzzy: bool = True) -> 'FactQuery':
        """Filter by human-readable label"""
        if fuzzy:
            from fuzzywuzzy import fuzz
            self._filters.append(
                lambda f: fuzz.partial_ratio(label.lower(), f.label.lower()) > 80
            )
        else:
            self._filters.append(lambda f: f.label == label)
        return self
    
    # Time-based filtering
    def by_fiscal_year(self, year: int) -> 'FactQuery':
        """Filter by fiscal year"""
        self._filters.append(lambda f: f.fiscal_year == year)
        return self
    
    def by_fiscal_period(self, period: str) -> 'FactQuery':
        """Filter by fiscal period (FY, Q1, Q2, Q3, Q4)"""
        self._filters.append(lambda f: f.fiscal_period == period)
        return self
    
    def date_range(self, start: date, end: date) -> 'FactQuery':
        """Filter by date range"""
        self._filters.append(
            lambda f: start <= f.period_end <= end
        )
        return self
    
    def as_of(self, date: date) -> 'FactQuery':
        """Get facts as of a specific date (point-in-time)"""
        self._filters.append(
            lambda f: f.filing_date <= date
        )
        return self
    
    # Quality filtering
    def high_quality_only(self) -> 'FactQuery':
        """Filter to only high-quality, audited facts"""
        self._filters.append(
            lambda f: f.data_quality == DataQuality.HIGH and f.is_audited
        )
        return self
    
    def min_confidence(self, threshold: float) -> 'FactQuery':
        """Filter by minimum confidence score"""
        self._filters.append(lambda f: f.confidence_score >= threshold)
        return self
    
    # Statement and form filtering
    def by_statement_type(self, statement_type: str) -> 'FactQuery':
        """Filter by financial statement type"""
        self._filters.append(lambda f: f.statement_type == statement_type)
        return self
    
    def by_form_type(self, form_type: Union[str, List[str]]) -> 'FactQuery':
        """Filter by SEC form type"""
        if isinstance(form_type, str):
            form_type = [form_type]
        self._filters.append(lambda f: f.form_type in form_type)
        return self
    
    # Sorting and limiting
    def sort_by(self, field: str, ascending: bool = True) -> 'FactQuery':
        """Sort results by field"""
        self._sort = (field, ascending)
        return self
    
    def latest(self, n: int = 1) -> List[FinancialFact]:
        """Get the n most recent facts"""
        self._sort = ('filing_date', False)
        self._limit = n
        return self.execute()
    
    def latest_periods(self, n: int = 4) -> 'FactQuery':
        """Get facts from the n most recent periods"""
        # Complex logic to get n distinct periods
        return self
    
    # Execution methods
    def execute(self) -> List[FinancialFact]:
        """Execute query and return facts"""
        results = self._facts
        
        # Apply filters
        for filter_func in self._filters:
            results = [f for f in results if filter_func(f)]
        
        # Apply sorting
        if self._sort:
            field, ascending = self._sort
            results.sort(key=lambda f: getattr(f, field), reverse=not ascending)
        
        # Apply limit
        if self._limit:
            results = results[:self._limit]
        
        return results
    
    def to_dataframe(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Convert results to pandas DataFrame"""
        facts = self.execute()
        if not facts:
            return pd.DataFrame()
        
        # Convert to records
        records = [self._fact_to_record(f) for f in facts]
        df = pd.DataFrame(records)
        
        # Select columns if specified
        if columns:
            df = df[columns]
        
        return df
    
    def to_llm_context(self) -> List[Dict[str, any]]:
        """Convert results to LLM-friendly context"""
        facts = self.execute()
        return [f.to_llm_context() for f in facts]
    
    def pivot_by_period(self) -> pd.DataFrame:
        """Pivot facts to show concepts as rows and periods as columns"""
        df = self.to_dataframe()
        if df.empty:
            return df
        
        return df.pivot_table(
            index='label',
            columns='fiscal_period_year',
            values='numeric_value',
            aggfunc='first'
        )
```

### Investment Analytics Components

```python
class RatioAnalyzer:
    """Calculate financial ratios with context"""
    
    def __init__(self, facts: EntityFacts):
        self.facts = facts
        
    def calculate_all(self) -> Dict[str, Dict[str, any]]:
        """Calculate all standard ratios with context"""
        return {
            "profitability": self._profitability_ratios(),
            "liquidity": self._liquidity_ratios(),
            "leverage": self._leverage_ratios(),
            "efficiency": self._efficiency_ratios(),
            "valuation": self._valuation_ratios()
        }
    
    def _profitability_ratios(self) -> Dict[str, any]:
        """Calculate profitability ratios"""
        revenue = self.facts.get_fact('Revenue')
        net_income = self.facts.get_fact('NetIncome')
        total_assets = self.facts.get_fact('Assets')
        
        return {
            "gross_margin": {
                "value": self._calculate_ratio('GrossProfit', 'Revenue'),
                "context": "Gross profit as percentage of revenue",
                "benchmark": "Industry average: 35%",
                "trend": self._get_trend('GrossMargin', 5)
            },
            "net_margin": {
                "value": net_income.numeric_value / revenue.numeric_value if revenue else None,
                "context": "Net income as percentage of revenue",
                "quality": "High confidence - audited values"
            },
            "roa": {
                "value": net_income.numeric_value / total_assets.numeric_value if total_assets else None,
                "context": "Return on assets - efficiency of asset utilization"
            }
        }

class AnomalyDetector:
    """Detect unusual patterns in financial data"""
    
    def __init__(self, facts: EntityFacts):
        self.facts = facts
        
    def analyze(self) -> List[Dict[str, any]]:
        """Run anomaly detection algorithms"""
        anomalies = []
        
        # Benford's Law check
        benford_anomalies = self._check_benfords_law()
        anomalies.extend(benford_anomalies)
        
        # Unusual growth patterns
        growth_anomalies = self._check_growth_patterns()
        anomalies.extend(growth_anomalies)
        
        # Round number frequency
        round_anomalies = self._check_round_numbers()
        anomalies.extend(round_anomalies)
        
        return anomalies

class LLMContextBuilder:
    """Build rich context for LLM consumption"""
    
    def __init__(self, facts: EntityFacts):
        self.facts = facts
        
    def build(self, focus_areas: Optional[List[str]] = None, 
              time_period: str = "recent") -> Dict[str, any]:
        """Build comprehensive context for LLM analysis"""
        
        context = {
            "company": {
                "name": self.facts.name,
                "identifier": self.facts.cik,
                "summary": self._generate_company_summary()
            },
            "financial_overview": self._build_financial_overview(time_period),
            "key_metrics": self._extract_key_metrics(time_period),
            "trends": self._analyze_trends(time_period),
            "quality_indicators": self._assess_data_quality(),
            "notable_changes": self._identify_notable_changes()
        }
        
        # Add focus area analysis
        if focus_areas:
            context["focus_analysis"] = {}
            for area in focus_areas:
                context["focus_analysis"][area] = self._analyze_focus_area(area)
        
        return context
```

### Caching and Performance

```python
from functools import lru_cache
from datetime import datetime, timedelta
from pathlib import Path
import json
import orjson

class FactsCache:
    """Simple, efficient caching system for company facts"""
    
    def __init__(self, 
                 cache_dir: Optional[Path] = None,
                 ttl_hours: int = 24,
                 max_entries: int = 100):
        self.cache_dir = cache_dir or self._get_default_cache_dir()
        self.ttl = timedelta(hours=ttl_hours)
        self.max_entries = max_entries
        self._memory_cache = {}
        self._ensure_cache_dir()
        
    def _get_default_cache_dir(self) -> Path:
        """Get default cache directory"""
        from edgar.core import get_edgar_data_directory
        return get_edgar_data_directory() / "facts_cache"
        
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    @lru_cache(maxsize=100)
    def get_facts(self, cik: int) -> Optional[EntityFacts]:
        """Get facts from cache or fetch from SEC"""
        # Check memory cache first
        cache_key = str(cik)
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if datetime.utcnow() - entry['timestamp'] < self.ttl:
                return entry['facts']
        
        # Check disk cache
        cache_file = self.cache_dir / f"{cik}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = orjson.loads(f.read())
                    cache_time = datetime.fromisoformat(data['timestamp'])
                    if datetime.utcnow() - cache_time < self.ttl:
                        facts = self._deserialize_facts(data['facts'])
                        self._update_memory_cache(cik, facts)
                        return facts
            except Exception:
                # Invalid cache file, will re-fetch
                pass
        
        # Fetch from SEC
        facts = self._fetch_from_sec(cik)
        if facts:
            self._cache_facts(cik, facts)
        
        return facts
        
    def _fetch_from_sec(self, cik: int) -> Optional[EntityFacts]:
        """Fetch facts from SEC API"""
        from edgar.entity.facts import download_company_facts_from_sec, parse_company_facts
        
        try:
            json_data = download_company_facts_from_sec(cik)
            raw_facts = parse_company_facts(json_data)
            
            # Convert to new EntityFacts format
            return self._convert_to_entity_facts(raw_facts)
        except Exception as e:
            log.error(f"Failed to fetch facts for CIK {cik}: {e}")
            return None
            
    def _cache_facts(self, cik: int, facts: EntityFacts):
        """Cache facts to disk and memory"""
        # Update memory cache
        self._update_memory_cache(cik, facts)
        
        # Write to disk
        cache_file = self.cache_dir / f"{cik}.json"
        data = {
            'timestamp': datetime.utcnow().isoformat(),
            'facts': self._serialize_facts(facts)
        }
        
        with open(cache_file, 'wb') as f:
            f.write(orjson.dumps(data))
            
        # Manage cache size
        self._evict_old_entries()
        
    def _evict_old_entries(self):
        """Remove old entries if cache is too large"""
        cache_files = sorted(
            self.cache_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime
        )
        
        if len(cache_files) > self.max_entries:
            for f in cache_files[:-self.max_entries]:
                f.unlink()
                
    def clear_cache(self, cik: Optional[int] = None):
        """Clear cache for specific CIK or all"""
        if cik:
            # Clear specific CIK
            cache_key = str(cik)
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            cache_file = self.cache_dir / f"{cik}.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Clear all
            self._memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
```

## Implementation Strategy

### Phase 1: Core Foundation (Weeks 1-3)

#### Objectives
- Implement unified `FinancialFact` data model
- Create enhanced `EntityFacts` class with basic query interface
- Establish consistent type system

#### Deliverables
1. `models.py` - Unified data models with Pydantic validation
2. `entity_facts.py` - Enhanced EntityFacts class
3. `query.py` - Basic query interface implementation
4. Unit tests with 90%+ coverage

### Phase 2: Query Interface (Weeks 4-5)

#### Objectives
- Complete fluent query interface
- Add time series and pivot functionality
- Implement smart concept matching

#### Deliverables
1. Complete `FactQuery` implementation
2. Concept matching and fuzzy search
3. DataFrame conversion with optimized column selection
4. Integration tests with real SEC data

### Phase 3: Investment Analytics (Weeks 6-8)

#### Objectives
- Build ratio calculation engine
- Implement peer comparison
- Add anomaly detection

#### Deliverables
1. `analytics/ratios.py` - Comprehensive ratio calculations
2. `analytics/comparison.py` - Peer comparison engine
3. `analytics/anomalies.py` - Anomaly detection algorithms
4. Jupyter notebook examples

### Phase 4: AI Integration (Weeks 9-10)

#### Objectives
- Implement LLM context generation
- Add MCP protocol support
- Create agent tool definitions

#### Deliverables
1. `ai/context.py` - LLM context builder
2. `ai/agents.py` - Agent tool definitions
3. `ai/mcp.py` - MCP protocol implementation
4. AI integration examples

### Phase 5: Performance & Polish (Weeks 11-12)

#### Objectives
- Implement local caching system
- Optimize query performance
- Complete documentation

#### Deliverables
1. File-based caching with LRU memory cache
2. Performance benchmarks
3. Comprehensive documentation
4. Examples and tutorials

## Migration Strategy

### Clean Break Approach

Since backward compatibility is not required, we can implement a clean, modern API without legacy constraints:

```python
# New API only
from edgar import Company

company = Company("AAPL")
facts = company.get_facts()  # Returns new EntityFacts

# Direct usage
revenue_trend = facts.query().by_concept("Revenue").time_series()
ratios = facts.calculate_ratios()

# AI-ready usage
context = facts.to_llm_context(focus_areas=["profitability", "growth"])
```

### Migration Path
1. **Phase 1**: Release new API with comprehensive documentation
2. **Phase 2**: Provide migration examples and tutorials
3. **Phase 3**: Remove old API completely
4. **Phase 4**: Focus on new features and enhancements

## Success Metrics

### Performance Targets
- Query response time: < 100ms for cached data
- Memory usage: < 500MB for 5 years of company data
- Cache hit rate: > 90% for common queries

### Quality Metrics
- Type safety: 100% of public APIs typed
- Test coverage: > 95% for core functionality
- Documentation: All public methods documented

### User Adoption
- 50% of users migrated within 3 months
- 90% of users migrated within 6 months
- User satisfaction score > 4.5/5

## Risk Mitigation

### Technical Risks
1. **SEC API Changes**: Monitor for API changes, implement retry logic
2. **Data Quality**: Validate all incoming data, flag anomalies
3. **Performance**: Load test with large datasets, optimize queries

### User Experience Risks
1. **Breaking Changes**: Maintain compatibility layer
2. **Learning Curve**: Provide extensive examples and tutorials
3. **Migration Effort**: Offer automated migration tools

## Conclusion

This improvement plan transforms the Entity Facts API into a modern, AI-ready platform for investment analysis. By focusing on developer experience, investment utility, and AI integration, we create a powerful tool that serves both traditional analysts and next-generation AI-powered workflows.

The phased implementation ensures we can deliver value incrementally while maintaining system stability. The emphasis on backward compatibility ensures existing users can adopt the new features at their own pace.

With this design, EdgarTools' Entity Facts API becomes not just a data access layer, but a comprehensive investment intelligence platform ready for the AI era.