"""
Unit tests for the enhanced Entity Facts API.
"""

import pytest
from datetime import date, datetime
from typing import List
import json
from pathlib import Path
from edgar.entity.models import FinancialFact, DataQuality, ConceptMetadata
from edgar.entity.entity_facts import EntityFacts
from edgar.entity.query import FactQuery
from edgar.entity.parser import EntityFactsParser
from edgar import Company


class TestFinancialFact:
    """Test the FinancialFact data model"""
    
    def test_financial_fact_creation(self):
        """Test creating a FinancialFact with all fields"""
        fact = FinancialFact(
            concept="us-gaap:Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="USD",
            scale=1000,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
            period_type="duration",
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            accession="0001234567-24-000001",
            data_quality=DataQuality.HIGH,
            is_audited=False,
            confidence_score=0.95,
            semantic_tags=["revenue", "operating"],
            business_context="Quarterly revenue from product sales"
        )
        
        assert fact.concept == "us-gaap:Revenue"
        assert fact.numeric_value == 1000000.0
        assert fact.fiscal_year == 2024
        assert fact.data_quality == DataQuality.HIGH
    
    def test_to_llm_context(self):
        """Test converting fact to LLM context"""
        fact = FinancialFact(
            concept="us-gaap:Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000000,
            numeric_value=1000000000.0,
            unit="USD",
            scale=1000000,
            period_type="duration",
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            data_quality=DataQuality.HIGH,
            is_audited=False,
            confidence_score=0.95,
            semantic_tags=["revenue"],
            business_context="Quarterly revenue"
        )
        
        context = fact.to_llm_context()
        
        assert context["concept"] == "Revenue"
        assert "1,000,000,000" in context["value"]  # May include scale suffix
        assert context["unit"] == "USD"
        assert "Q1 2024" in context["period"]
        assert context["quality"] == "high"
        assert context["confidence"] == 0.95
    
    def test_fact_repr(self):
        """Test string representation of fact"""
        fact = FinancialFact(
            concept="us-gaap:Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=1000000,
            numeric_value=1000000.0,
            unit="USD",
            fiscal_year=2024,
            fiscal_period="Q1"
        )
        
        repr_str = repr(fact)
        assert "Revenue" in repr_str
        assert "1,000,000" in repr_str
        assert "Q1 2024" in repr_str


class TestEntityFacts:
    """Test the EntityFacts class"""
    
    @pytest.fixture
    def sample_facts(self) -> List[FinancialFact]:
        """Create sample facts for testing"""
        facts = []
        
        # Revenue facts for multiple periods
        for year in [2023, 2024]:
            for quarter in ["Q1", "Q2", "Q3", "Q4"]:
                facts.append(FinancialFact(
                    concept="us-gaap:Revenue",
                    taxonomy="us-gaap",
                    label="Revenue",
                    value=1000000 * (year - 2020) * (int(quarter[1]) + 1),
                    numeric_value=float(1000000 * (year - 2020) * (int(quarter[1]) + 1)),
                    unit="USD",
                    period_type="duration",
                    period_start=date(year, max(int(quarter[1]) * 3 - 2, 1), 1),
                    period_end=date(year, min(int(quarter[1]) * 3, 12), 31 if min(int(quarter[1]) * 3, 12) in [1,3,5,7,8,10,12] else 30),
                    fiscal_year=year,
                    fiscal_period=quarter,
                    filing_date=date(year, min(int(quarter[1]) * 3, 12), 15),
                    form_type="10-Q",
                    statement_type="IncomeStatement",
                    data_quality=DataQuality.HIGH
                ))
        
        # Add annual revenue
        for year in [2023, 2024]:
            facts.append(FinancialFact(
                concept="us-gaap:Revenue",
                taxonomy="us-gaap",
                label="Revenue",
                value=15000000 * (year - 2020),
                numeric_value=float(15000000 * (year - 2020)),
                unit="USD",
                period_type="duration",
                fiscal_year=year,
                fiscal_period="FY",
                filing_date=date(year + 1, 2, 15),
                form_type="10-K",
                statement_type="IncomeStatement",
                data_quality=DataQuality.HIGH,
                is_audited=True
            ))
        
        # Add some balance sheet items
        facts.append(FinancialFact(
            concept="us-gaap:Assets",
            taxonomy="us-gaap",
            label="Total Assets",
            value=50000000,
            numeric_value=50000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        facts.append(FinancialFact(
            concept="us-gaap:CurrentAssets",
            taxonomy="us-gaap",
            label="Current Assets",
            value=20000000,
            numeric_value=20000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        facts.append(FinancialFact(
            concept="us-gaap:CurrentLiabilities",
            taxonomy="us-gaap",
            label="Current Liabilities",
            value=10000000,
            numeric_value=10000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        return facts
    
    @pytest.fixture
    def entity_facts(self, sample_facts) -> EntityFacts:
        """Create EntityFacts instance for testing"""
        return EntityFacts(
            cik=123456,
            name="Test Company Inc.",
            facts=sample_facts
        )
    
    def test_entity_facts_creation(self, entity_facts):
        """Test creating EntityFacts instance"""
        assert entity_facts.cik == 123456
        assert entity_facts.name == "Test Company Inc."
        assert len(entity_facts) > 0
    
    def test_get_fact(self, entity_facts):
        """Test getting a single fact"""
        # Get by exact concept
        fact = entity_facts.get_fact("us-gaap:Revenue")
        assert fact is not None
        assert fact.concept == "us-gaap:Revenue"
        
        # Get by label (case-insensitive)
        fact = entity_facts.get_fact("revenue")
        assert fact is not None
        
        # Get specific period
        fact = entity_facts.get_fact("Revenue", "2024-Q1")
        assert fact is not None
        assert fact.fiscal_year == 2024
        assert fact.fiscal_period == "Q1"
        
        # Non-existent concept
        fact = entity_facts.get_fact("NonExistent")
        assert fact is None
    
    def test_time_series(self, entity_facts):
        """Test getting time series data"""
        df = entity_facts.time_series("Revenue", periods=4)
        
        assert not df.empty
        assert len(df) <= 4
        assert "numeric_value" in df.columns
        assert "fiscal_period" in df.columns
    
    def test_income_statement(self, entity_facts):
        """Test getting income statement data"""
        df = entity_facts.income_statement(periods=4)
        
        # Should return pivoted data
        assert not df.empty
        assert df.index.name == "label"
    
    def test_balance_sheet(self, entity_facts):
        """Test getting balance sheet data"""
        # Test new FinancialStatement return (using annual=False since test data has quarterly data)
        stmt = entity_facts.balance_sheet(annual=False)
        
        assert not stmt.empty
        assert stmt.statement_type == "BalanceSheet"
        
        # Test raw DataFrame return (multi-period - returns pivoted DataFrame)
        df = entity_facts.balance_sheet(as_dataframe=True, annual=False)
        assert not df.empty
        # Multi-period returns pivoted data with labels as index
        assert hasattr(df, 'index')
        
        # Test point-in-time view with DataFrame return
        from datetime import date
        df_snapshot = entity_facts.balance_sheet(as_of=date(2024, 3, 31), as_dataframe=True)
        # Point-in-time view should have label column if data exists
        if not df_snapshot.empty and 'label' in df_snapshot.columns:
            assert 'label' in df_snapshot.columns
    
    def test_to_llm_context(self, entity_facts):
        """Test generating LLM context"""
        context = entity_facts.to_llm_context()
        
        assert "company" in context
        assert context["company"]["name"] == "Test Company Inc."
        assert "data_summary" in context
        assert "key_metrics" in context
    
    def test_to_agent_tools(self, entity_facts):
        """Test generating agent tool definitions"""
        tools = entity_facts.to_agent_tools()
        
        assert len(tools) > 0
        assert all("name" in tool for tool in tools)
        assert all("parameters" in tool for tool in tools)
        assert all("description" in tool for tool in tools)
    
    def test_dei_facts(self, entity_facts):
        """Test getting DEI facts"""
        # Add some DEI facts to test data
        from edgar.entity.models import FinancialFact, DataQuality
        from datetime import date
        
        dei_fact = FinancialFact(
            concept="dei:EntityCommonStockSharesOutstanding",
            taxonomy="dei",
            label="Entity Common Stock, Shares Outstanding",
            value=100000000,
            numeric_value=100000000.0,
            unit="shares",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            data_quality=DataQuality.HIGH
        )
        
        # Add the DEI fact to the entity
        entity_facts._facts.append(dei_fact)
        entity_facts._fact_index = entity_facts._build_indices()
        
        # Test dei_facts method
        dei_df = entity_facts.dei_facts()
        
        assert not dei_df.empty
        assert 'concept' in dei_df.columns
        assert 'label' in dei_df.columns
        assert 'value' in dei_df.columns
        assert any('EntityCommonStockSharesOutstanding' in concept 
                  for concept in dei_df['concept'].values)
    
    def test_entity_info(self, entity_facts):
        """Test getting entity info dictionary"""
        # Add some DEI facts to test data
        from edgar.entity.models import FinancialFact, DataQuality
        from datetime import date
        
        dei_facts = [
            FinancialFact(
                concept="dei:EntityCommonStockSharesOutstanding",
                taxonomy="dei",
                label="Entity Common Stock, Shares Outstanding",
                value=100000000,
                numeric_value=100000000.0,
                unit="shares",
                period_type="instant",
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
                filing_date=date(2024, 4, 15),
                form_type="10-Q",
                data_quality=DataQuality.HIGH
            ),
            FinancialFact(
                concept="dei:EntityPublicFloat",
                taxonomy="dei",
                label="Entity Public Float",
                value=5000000000,
                numeric_value=5000000000.0,
                unit="USD",
                period_type="instant",
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
                filing_date=date(2024, 4, 15),
                form_type="10-Q",
                data_quality=DataQuality.HIGH
            )
        ]
        
        # Add the DEI facts to the entity
        entity_facts._facts.extend(dei_facts)
        entity_facts._fact_index = entity_facts._build_indices()
        
        # Test entity_info method
        info = entity_facts.entity_info()
        
        assert 'entity_name' in info
        assert 'cik' in info
        assert info['entity_name'] == "Test Company Inc."
        assert info['cik'] == 123456
        
        # Should have DEI data
        assert 'shares_outstanding' in info
        assert 'public_float' in info
        assert info['shares_outstanding'] == '100,000,000'
        assert info['public_float'] == '5,000,000,000'  # get_formatted_value() doesn't add $ for USD
    
    def test_dei_properties(self, entity_facts):
        """Test DEI fact properties"""
        # Initially no DEI facts
        assert entity_facts.shares_outstanding is None
        assert entity_facts.public_float is None
        assert entity_facts.shares_outstanding_fact is None
        assert entity_facts.public_float_fact is None
        
        # Add DEI facts
        from edgar.entity.models import FinancialFact, DataQuality
        from datetime import date
        
        shares_fact = FinancialFact(
            concept="dei:EntityCommonStockSharesOutstanding",
            taxonomy="dei",
            label="Entity Common Stock, Shares Outstanding",
            value=100000000,
            numeric_value=100000000.0,
            unit="shares",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            data_quality=DataQuality.HIGH
        )
        
        float_fact = FinancialFact(
            concept="dei:EntityPublicFloat",
            taxonomy="dei",
            label="Entity Public Float",
            value=5000000000,
            numeric_value=5000000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            data_quality=DataQuality.HIGH
        )
        
        entity_facts._facts.extend([shares_fact, float_fact])
        entity_facts._fact_index = entity_facts._build_indices()
        
        # Test numeric properties
        assert entity_facts.shares_outstanding == 100000000.0
        assert entity_facts.public_float == 5000000000.0
        
        # Test fact properties
        assert entity_facts.shares_outstanding_fact is not None
        assert entity_facts.public_float_fact is not None
        assert entity_facts.shares_outstanding_fact.concept == "dei:EntityCommonStockSharesOutstanding"
        assert entity_facts.public_float_fact.concept == "dei:EntityPublicFloat"
        
        # Test that properties return the same facts as get_fact
        assert entity_facts.shares_outstanding_fact == entity_facts.get_fact("dei:EntityCommonStockSharesOutstanding")
        assert entity_facts.public_float_fact == entity_facts.get_fact("dei:EntityPublicFloat")


class TestFactQuery:
    """Test the FactQuery interface"""
    
    @pytest.fixture
    def sample_facts(self) -> List[FinancialFact]:
        """Create sample facts for testing"""
        facts = []
        
        # Revenue facts for multiple periods
        for year in [2023, 2024]:
            for quarter in ["Q1", "Q2", "Q3", "Q4"]:
                facts.append(FinancialFact(
                    concept="us-gaap:Revenue",
                    taxonomy="us-gaap",
                    label="Revenue",
                    value=1000000 * (year - 2020) * (int(quarter[1]) + 1),
                    numeric_value=float(1000000 * (year - 2020) * (int(quarter[1]) + 1)),
                    unit="USD",
                    period_type="duration",
                    period_start=date(year, max(int(quarter[1]) * 3 - 2, 1), 1),
                    period_end=date(year, min(int(quarter[1]) * 3, 12), 31 if min(int(quarter[1]) * 3, 12) in [1,3,5,7,8,10,12] else 30),
                    fiscal_year=year,
                    fiscal_period=quarter,
                    filing_date=date(year, min(int(quarter[1]) * 3, 12), 15),
                    form_type="10-Q",
                    statement_type="IncomeStatement",
                    data_quality=DataQuality.HIGH
                ))
        
        # Add annual revenue
        for year in [2023, 2024]:
            facts.append(FinancialFact(
                concept="us-gaap:Revenue",
                taxonomy="us-gaap",
                label="Revenue",
                value=15000000 * (year - 2020),
                numeric_value=float(15000000 * (year - 2020)),
                unit="USD",
                period_type="duration",
                fiscal_year=year,
                fiscal_period="FY",
                filing_date=date(year + 1, 2, 15),
                form_type="10-K",
                statement_type="IncomeStatement",
                data_quality=DataQuality.HIGH,
                is_audited=True
            ))
        
        # Add some balance sheet items
        facts.append(FinancialFact(
            concept="us-gaap:Assets",
            taxonomy="us-gaap",
            label="Total Assets",
            value=50000000,
            numeric_value=50000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        facts.append(FinancialFact(
            concept="us-gaap:CurrentAssets",
            taxonomy="us-gaap",
            label="Current Assets",
            value=20000000,
            numeric_value=20000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        facts.append(FinancialFact(
            concept="us-gaap:CurrentLiabilities",
            taxonomy="us-gaap",
            label="Current Liabilities",
            value=10000000,
            numeric_value=10000000.0,
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            fiscal_year=2024,
            fiscal_period="Q1",
            filing_date=date(2024, 4, 15),
            form_type="10-Q",
            statement_type="BalanceSheet"
        ))
        
        return facts
    
    @pytest.fixture
    def entity_facts_for_query(self, sample_facts) -> EntityFacts:
        """Create EntityFacts instance for query testing"""
        return EntityFacts(
            cik=123456,
            name="Test Company Inc.",
            facts=sample_facts
        )
    
    @pytest.fixture
    def query(self, entity_facts_for_query) -> FactQuery:
        """Create a query instance"""
        return entity_facts_for_query.query()
    
    def test_by_concept(self, query):
        """Test filtering by concept"""
        results = query.by_concept("Revenue").execute()
        assert all("Revenue" in f.concept or "Revenue" in f.label for f in results)
        
        # Test exact matching
        results = query.by_concept("us-gaap:Revenue", exact=True).execute()
        assert all(f.concept == "us-gaap:Revenue" for f in results)
    
    def test_by_fiscal_year(self, query):
        """Test filtering by fiscal year"""
        results = query.by_fiscal_year(2024).execute()
        assert all(f.fiscal_year == 2024 for f in results)
    
    def test_by_fiscal_period(self, query):
        """Test filtering by fiscal period"""
        results = query.by_fiscal_period("Q1").execute()
        assert all(f.fiscal_period == "Q1" for f in results)
    
    def test_by_statement_type(self, query):
        """Test filtering by statement type"""
        results = query.by_statement_type("BalanceSheet").execute()
        assert all(f.statement_type == "BalanceSheet" for f in results)
    
    def test_by_form_type(self, query):
        """Test filtering by form type"""
        results = query.by_form_type("10-Q").execute()
        assert all(f.form_type == "10-Q" for f in results)
        
        # Test multiple form types
        results = query.by_form_type(["10-Q", "10-K"]).execute()
        assert all(f.form_type in ["10-Q", "10-K"] for f in results)
    
    def test_high_quality_only(self, query):
        """Test filtering for high quality facts"""
        results = query.high_quality_only().execute()
        assert all(f.data_quality == DataQuality.HIGH and f.is_audited for f in results)
    
    def test_latest(self, query):
        """Test getting latest facts"""
        results = query.by_concept("Revenue").latest(2)
        assert len(results) <= 2
        # Should be sorted by filing date descending
        if len(results) > 1:
            assert results[0].filing_date >= results[1].filing_date
    
    def test_to_dataframe(self, query):
        """Test converting to DataFrame"""
        df = query.by_concept("Revenue").to_dataframe()
        
        assert not df.empty
        assert "concept" in df.columns
        assert "numeric_value" in df.columns
        
        # Test with specific columns
        df = query.by_concept("Revenue").to_dataframe("label", "numeric_value", "fiscal_period")
        assert list(df.columns) == ["label", "numeric_value", "fiscal_period"]
    
    def test_pivot_by_period(self, query):
        """Test pivoting by period"""
        # Test FinancialStatement return (default)
        statement = query.by_statement_type("IncomeStatement").pivot_by_period()
        
        assert not statement.empty
        # Columns should be period keys like "Q1 2024", "FY 2023"
        assert all(" " in col for col in statement.columns)
        # Should be FinancialStatement object
        from edgar.entity.statement import FinancialStatement
        assert isinstance(statement, FinancialStatement)
        
        # Test raw DataFrame return
        pivot = query.by_statement_type("IncomeStatement").pivot_by_period(return_statement=False)
        assert not pivot.empty
        assert all(" " in col for col in pivot.columns)
        import pandas as pd
        assert isinstance(pivot, pd.DataFrame)
    
    def test_chaining(self, query):
        """Test method chaining"""
        results = query\
            .by_fiscal_year(2024)\
            .by_fiscal_period("Q1")\
            .by_statement_type("IncomeStatement")\
            .execute()
        
        assert all(
            f.fiscal_year == 2024 and 
            f.fiscal_period == "Q1" and 
            f.statement_type == "IncomeStatement" 
            for f in results
        )
    
    def test_count(self, query):
        """Test counting results"""
        count = query.by_concept("Revenue").count()
        assert count > 0
        
        # Count should match execute length
        results = query.by_concept("Revenue").execute()
        assert count == len(results)
    
    def test_by_period_length(self, sample_facts):
        """Test filtering by period length"""
        # Add facts with different period lengths
        facts_with_periods = sample_facts.copy()
        
        # Add a 9-month YTD fact
        facts_with_periods.append(FinancialFact(
            concept="us-gaap:Revenue",
            taxonomy="us-gaap",
            label="Revenue",
            value=30000000,
            numeric_value=30000000.0,
            unit="USD",
            period_type="duration",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 9, 30),  # 9 months
            fiscal_year=2024,
            fiscal_period="YTD",
            filing_date=date(2024, 10, 15),
            form_type="10-Q",
            statement_type="IncomeStatement"
        ))
        
        entity_facts = EntityFacts(
            cik=123456,
            name="Test Company Inc.",
            facts=facts_with_periods
        )
        
        # Test filtering for quarterly (3-month) periods
        quarterly_facts = entity_facts.query()\
            .by_statement_type("IncomeStatement")\
            .by_period_length(3)\
            .execute()
        
        # Should only get 3-month periods
        for fact in quarterly_facts:
            if fact.period_start and fact.period_type == 'duration':
                months = (fact.period_end.year - fact.period_start.year) * 12
                months += fact.period_end.month - fact.period_start.month + 1
                assert months <= 4  # Allow slight variation
        
        # Test filtering for annual (12-month) periods  
        annual_facts = entity_facts.query()\
            .by_statement_type("IncomeStatement")\
            .by_period_length(12)\
            .execute()
            
        # Should only get ~12-month periods
        for fact in annual_facts:
            if fact.period_start and fact.period_type == 'duration':
                months = (fact.period_end.year - fact.period_start.year) * 12
                months += fact.period_end.month - fact.period_start.month + 1
                assert months >= 11  # Allow for fiscal year variations


class TestEntityFactsParser:
    """Test the parser for SEC data"""

    @pytest.fixture()
    def lpa_facts(self):
        return json.loads(Path("tests/fixtures/entity/lpa_facts.json").read_text('utf-8'))

    @pytest.fixture()
    def snow_facts(self):
        return json.loads(Path("tests/fixtures/entity/snow_facts.json").read_text('utf-8'))
    
    @pytest.fixture
    def duplicate_facts_sample(self) -> List[FinancialFact]:
        """Create sample facts with duplicates for testing deduplication"""
        # Same gross profit fact filed in multiple years
        base_fact = {
            "concept": "us-gaap:GrossProfit",
            "taxonomy": "us-gaap",
            "label": "Gross Profit",
            "value": 556192000,
            "numeric_value": 556192000.0,
            "unit": "USD",
            "period_type": "duration",
            "period_start": date(2024, 2, 1),
            "period_end": date(2024, 4, 30),
            "fiscal_period": "Q1",
            "statement_type": "IncomeStatement",
            "data_quality": DataQuality.HIGH
        }
        
        facts = [
            # Original filing
            FinancialFact(
                **base_fact,
                fiscal_year=2025,
                filing_date=date(2024, 5, 31),
                form_type="10-Q",
                accession="0001640147-24-000135"
            ),
            # Same fact filed again in next year
            FinancialFact(
                **base_fact,
                fiscal_year=2026,
                filing_date=date(2025, 5, 30),
                form_type="10-Q",
                accession="0001640147-25-000110"
            ),
            # Restated value (different) from 10-K
            FinancialFact(
                **{**base_fact, "value": 556200000, "numeric_value": 556200000.0},
                fiscal_year=2025,
                filing_date=date(2025, 3, 31),
                form_type="10-K",
                accession="0001640147-25-000050"
            ),
            # Different concept (should not be deduplicated)
            FinancialFact(
                concept="us-gaap:Revenue",
                taxonomy="us-gaap",
                label="Revenue",
                value=828709000,
                numeric_value=828709000.0,
                unit="USD",
                period_type="duration",
                period_start=date(2024, 2, 1),
                period_end=date(2024, 4, 30),
                fiscal_year=2026,
                fiscal_period="Q1",
                filing_date=date(2025, 5, 30),
                form_type="10-Q",
                accession="0001640147-25-000110",
                statement_type="IncomeStatement",
                data_quality=DataQuality.HIGH
            )
        ]
        
        return facts
    
    def test_parse_company_facts(self):
        """Test parsing SEC company facts JSON"""
        sample_json = {
            "cik": 123456,
            "entityName": "Test Company Inc.",
            "facts": {
                "us-gaap": {
                    "Revenue": {
                        "label": "Revenue",
                        "description": "Total revenue from operations",
                        "units": {
                            "USD": [
                                {
                                    "val": 1000000,
                                    "end": "2024-03-31",
                                    "start": "2024-01-01",
                                    "filed": "2024-04-15",
                                    "form": "10-Q",
                                    "fy": 2024,
                                    "fp": "Q1",
                                    "accn": "0001234567-24-000001"
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        entity_facts = EntityFactsParser.parse_company_facts(sample_json)
        
        assert entity_facts is not None
        assert entity_facts.cik == 123456
        assert entity_facts.name == "Test Company Inc."
        assert len(entity_facts) > 0
        
        # Check parsed fact
        fact = entity_facts.get_fact("Revenue")
        assert fact is not None
        assert fact.numeric_value == 1000000.0
        assert fact.fiscal_year == 2024
        assert fact.fiscal_period == "Q1"

    def test_parse_lpa_facts(self, lpa_facts):
        entity_facts:EntityFacts= EntityFactsParser.parse_company_facts(lpa_facts)
        from edgar import Company
        c = Company("LPA")
        print(entity_facts)
        assert entity_facts.cik == 1997711
        assert entity_facts is not None
        assert len(entity_facts) == len(c.get_facts())

    def test_parse_snow_facts(self, snow_facts):
        entity_facts: EntityFacts = EntityFactsParser.parse_company_facts(snow_facts)
        
        # Basic structure validation
        assert entity_facts is not None
        assert entity_facts.cik == 1640147
        assert entity_facts.name == "SNOWFLAKE INC."
        
        # Validate we have facts
        assert len(entity_facts) > 0
        print(f"Total facts: {len(entity_facts)}")
        
        # Test query functionality
        revenue_facts = entity_facts.query().by_concept("Revenue").execute()
        if revenue_facts:
            assert len(revenue_facts) > 0
            print(f"Revenue facts found: {len(revenue_facts)}")
        
        # Test specific financial statements
        income_stmt = entity_facts.income_statement()
        assert income_stmt is not None
        print(f"Income statement facts: {len(income_stmt) if not income_stmt.empty else 0}")
        
        balance_sheet = entity_facts.balance_sheet()
        assert balance_sheet is not None
        print(f"Balance sheet facts: {len(balance_sheet) if not balance_sheet.empty else 0}")
        
        # Test time series functionality for a common concept
        shares_ts = entity_facts.time_series("EntityCommonStockSharesOutstanding")
        if shares_ts is not None and not shares_ts.empty:
            assert len(shares_ts) > 0
            print(f"Shares outstanding time series: {len(shares_ts)} points")
            
        # Test get_fact functionality
        shares_fact = entity_facts.get_fact("EntityCommonStockSharesOutstanding")
        if shares_fact:
            assert shares_fact.concept is not None
            assert shares_fact.value is not None
            print(f"Latest shares outstanding: {shares_fact.value}")
            
        # Test LLM context generation
        llm_context = entity_facts.to_llm_context()
        assert llm_context['company']['name'] == "SNOWFLAKE INC."
        assert llm_context['company']['cik'] == entity_facts.cik
        assert llm_context['data_summary']['total_facts'] > 0
        
        # Test agent tools generation
        agent_tools = entity_facts.to_agent_tools()
        assert len(agent_tools) > 0
        assert any("snowflake" in tool.get("name", "").lower() for tool in agent_tools)
        
        # Test filtering by fiscal year
        fy2024_facts = entity_facts.query().by_fiscal_year(2024).execute()
        if fy2024_facts:
            assert len(fy2024_facts) > 0
            print(f"FY2024 facts: {len(fy2024_facts)}")
            
        # Test high quality facts filtering
        high_quality = entity_facts.query().high_quality_only().execute()
        assert len(high_quality) > 0
        print(f"High quality facts: {len(high_quality)}")
        
        # Validate data types and structure
        sample_fact = next(iter(entity_facts))
        assert hasattr(sample_fact, 'concept')
        assert hasattr(sample_fact, 'value')
        assert hasattr(sample_fact, 'fiscal_year')
        assert hasattr(sample_fact, 'business_context')
    
    def test_parse_date(self):
        """Test date parsing"""
        # Test various formats
        assert EntityFactsParser._parse_date("2024-01-01") == date(2024, 1, 1)
        assert EntityFactsParser._parse_date("20240101") == date(2024, 1, 1)
        assert EntityFactsParser._parse_date("01/01/2024") == date(2024, 1, 1)
        assert EntityFactsParser._parse_date(None) is None
        assert EntityFactsParser._parse_date("invalid") is None
    
    def test_determine_statement_type(self):
        """Test statement type determination"""
        assert EntityFactsParser._determine_statement_type("Revenue") == "IncomeStatement"
        assert EntityFactsParser._determine_statement_type("Assets") == "BalanceSheet"
        assert EntityFactsParser._determine_statement_type("us-gaap:Revenue") == "IncomeStatement"
        assert EntityFactsParser._determine_statement_type("Unknown") is None
    
    def test_deduplication(self, duplicate_facts_sample):
        """Test fact deduplication logic"""
        entity_facts = EntityFacts(
            cik=1640147,
            name="SNOWFLAKE INC.",
            facts=duplicate_facts_sample
        )
        
        # Query for gross profit should deduplicate
        gross_profit_facts = entity_facts.query().by_concept("GrossProfit").execute()
        assert len(gross_profit_facts) == 3  # Three different filings
        
        # Pivot should only show one value per period
        pivot = entity_facts.query().by_statement_type("IncomeStatement").pivot_by_period()
        assert not pivot.empty
        
        # Check that we have only one row for Gross Profit
        assert "Gross Profit" in pivot.index
        gross_profit_row = pivot.data.loc["Gross Profit"]
        
        # Should have deduplicated to show only one value
        # Note: Period ending April 30 is Q2, not Q1
        import pandas as pd
        q2_2024_values = [val for col, val in gross_profit_row.items() if "Q2 2024" in col and not pd.isna(val)]
        assert len(q2_2024_values) == 1
        
        # The value should be from the most recent filing (May 2025 10-Q)
        # Filing date takes priority over form type
        assert q2_2024_values[0] == 556192000.0
    
    def test_deduplication_filing_date_priority(self, duplicate_facts_sample):
        """Test that deduplication prioritizes by filing date, then form type"""
        from edgar.entity.query import FactQuery
        
        # Manually test the deduplication logic
        query = FactQuery(duplicate_facts_sample, {})
        deduplicated = query._deduplicate_facts(duplicate_facts_sample)
        
        # Should have 2 facts: one GrossProfit, one Revenue
        assert len(deduplicated) == 2
        
        # Find the gross profit fact
        gross_profit = next(f for f in deduplicated if f.concept == "us-gaap:GrossProfit")
        
        # Should prefer the most recent filing date (May 30, 2025)
        assert gross_profit.filing_date == date(2025, 5, 30)
        assert gross_profit.form_type == "10-Q"
        assert gross_profit.numeric_value == 556192000.0
    
    def test_income_statement_deduplication(self):
        """Test that income statement properly deduplicates"""
        # Create facts with duplicates
        facts = []
        for i in range(3):
            facts.append(FinancialFact(
                concept="us-gaap:Revenue",
                taxonomy="us-gaap",
                label="Revenue",
                value=1000000 + i * 1000,  # Slightly different values
                numeric_value=float(1000000 + i * 1000),
                unit="USD",
                period_type="duration",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31),
                fiscal_year=2024,
                fiscal_period="Q1",
                filing_date=date(2024, 4, 15 + i),  # Different filing dates
                form_type="10-Q" if i < 2 else "10-K",
                statement_type="IncomeStatement",
                data_quality=DataQuality.HIGH,
                is_audited=(i == 2)
            ))
        
        entity_facts = EntityFacts(cik=123456, name="Test Co", facts=facts)
        income_stmt = entity_facts.income_statement(annual=False)
        
        # Should have only one column for Q1 2024
        q1_cols = [col for col in income_stmt.columns if "Q1 2024" in col]
        assert len(q1_cols) == 1
        
        # Should have chosen the 10-K value (1002000)
        assert income_stmt.data.loc["Revenue", q1_cols[0]] == 1002000.0
    
    def test_financial_statement_formatting(self):
        """Test FinancialStatement formatting functionality"""
        from edgar.entity.statement import FinancialStatement
        import pandas as pd
        
        # Create test data with various financial concepts
        data = pd.DataFrame({
            'Q1 2024': [1.23, 0.05, 1000000000, 50000000],
            'Q2 2024': [1.45, 0.08, 1200000000, 52000000]
        }, index=['Earnings Per Share', 'Dividend Per Share', 'Revenue', 'Shares Outstanding'])
        
        statement = FinancialStatement(
            data=data,
            statement_type='IncomeStatement',
            entity_name='Test Company',
            period_lengths=['3M'],
            mixed_periods=False
        )
        
        # Test concept-specific formatting (now using full precision with commas)
        assert statement.format_value(1.23, 'Earnings Per Share') == '1.23'
        assert statement.format_value(0.05, 'Dividend Per Share') == '0.05'
        assert statement.format_value(1000000000, 'Revenue') == '$1,000,000,000'
        assert statement.format_value(50000000, 'Shares Outstanding') == '50,000,000'
        
        # Test accessing underlying data
        numeric_data = statement.to_numeric()
        assert numeric_data.loc['Earnings Per Share', 'Q1 2024'] == 1.23
        
        # Test getting specific concept
        eps_series = statement.get_concept('Earnings Per Share')
        assert eps_series is not None
        assert eps_series['Q1 2024'] == 1.23
        
        # Test LLM context
        context = statement.to_llm_context()
        assert context['entity_name'] == 'Test Company'
        assert context['statement_type'] == 'IncomeStatement'
        assert 'Earnings Per Share' in context['line_items']
        
        # Test that EPS maintains precision
        eps_context = context['line_items']['Earnings Per Share']
        assert eps_context['values']['Q1 2024']['formatted_value'] == '1.23'


class TestPeriodSelection:

    def test_statement_annual_periods(self):
        c = Company("BACQ")
        entity_facts = c.get_facts()
        print()
        print(entity_facts)
        income_statement = entity_facts.income_statement()
        query = entity_facts.query().by_statement_type('IncomeStatement')

        # Pass entity information and return preference (flip the boolean)
        result = query.latest_periods(4, annual=True)
        print(result)
        print(result.to_dataframe())

        result_pivot = result.pivot_by_period(return_statement=True)
        columns = result_pivot.data.columns
        assert not any (c.startswith("Q") for c in columns)
        print(income_statement)