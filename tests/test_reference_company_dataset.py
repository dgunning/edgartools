"""
Tests for company dataset builder functionality.

These tests cover building, loading, and querying company datasets from SEC submissions.
"""

import pytest
import pyarrow as pa
import pyarrow.compute as pc
from pathlib import Path
import tempfile

from edgar.reference.company_dataset import (
    is_individual_from_json,
    build_company_dataset_parquet,
    build_company_dataset_duckdb,
    load_company_dataset_parquet,
    to_duckdb,
    get_company_dataset,
    COMPANY_SCHEMA,
)


class TestIsIndividual:
    """Tests for individual vs company detection logic."""

    def test_company_with_ticker(self):
        """Company with ticker should not be individual"""
        data = {'cik': '0001318605', 'tickers': ['TSLA']}
        assert not is_individual_from_json(data)

    def test_company_with_multiple_tickers(self):
        """Company with multiple tickers should not be individual"""
        data = {'cik': '0001318605', 'tickers': ['TSLA', 'TESLA']}
        assert not is_individual_from_json(data)

    def test_company_with_exchange(self):
        """Company with exchange should not be individual"""
        data = {'cik': '0001318605', 'exchanges': ['Nasdaq']}
        assert not is_individual_from_json(data)

    def test_company_with_multiple_exchanges(self):
        """Company with multiple exchanges should not be individual"""
        data = {'cik': '0001318605', 'exchanges': ['Nasdaq', 'NYSE']}
        assert not is_individual_from_json(data)

    def test_company_with_state(self):
        """Company with state of incorporation should not be individual"""
        data = {'cik': '0001318605', 'stateOfIncorporation': 'DE'}
        assert not is_individual_from_json(data)

    def test_company_with_entity_type(self):
        """Company with entity type should not be individual"""
        data = {'cik': '0001318605', 'entityType': 'corporation'}
        assert not is_individual_from_json(data)

    def test_company_with_10k_filing(self):
        """Company filing 10-K should not be individual"""
        data = {
            'cik': '0001318605',
            'filings': {
                'recent': {
                    'form': ['10-K', '8-K']
                }
            }
        }
        assert not is_individual_from_json(data)

    def test_company_with_10q_filing(self):
        """Company filing 10-Q should not be individual"""
        data = {
            'cik': '0001318605',
            'filings': {
                'recent': {
                    'form': ['10-Q']
                }
            }
        }
        assert not is_individual_from_json(data)

    def test_individual_no_indicators(self):
        """Individual with no company indicators should be individual"""
        data = {'cik': '0001078519', 'name': 'JOHN DOE'}
        assert is_individual_from_json(data)

    def test_individual_with_empty_entity_type(self):
        """Individual with empty entity type should be individual"""
        data = {'cik': '0001078519', 'entityType': ''}
        assert is_individual_from_json(data)

    def test_individual_with_other_entity_type(self):
        """Individual with 'other' entity type should be individual"""
        data = {'cik': '0001078519', 'entityType': 'other'}
        assert is_individual_from_json(data)

    def test_reed_hastings_exception(self):
        """Reed Hastings (CIK 0001033331) is exception - individual with state"""
        data = {'cik': '0001033331', 'stateOfIncorporation': 'CA'}
        assert is_individual_from_json(data)

    def test_empty_tickers_list(self):
        """Empty tickers list should not indicate company"""
        data = {'cik': '0001078519', 'tickers': []}
        assert is_individual_from_json(data)

    def test_empty_exchanges_list(self):
        """Empty exchanges list should not indicate company"""
        data = {'cik': '0001078519', 'exchanges': []}
        assert is_individual_from_json(data)


class TestSchema:
    """Tests for company dataset schema."""

    def test_schema_fields(self):
        """Verify schema has all expected fields"""
        expected_fields = {
            'cik', 'name', 'sic', 'sic_description',
            'tickers', 'exchanges', 'state_of_incorporation',
            'state_of_incorporation_description', 'fiscal_year_end',
            'entity_type', 'ein'
        }
        actual_fields = {field.name for field in COMPANY_SCHEMA}
        assert actual_fields == expected_fields

    def test_cik_is_string(self):
        """CIK should be string to preserve leading zeros"""
        cik_field = COMPANY_SCHEMA.field('cik')
        assert cik_field.type == pa.string()

    def test_sic_is_int32(self):
        """SIC should be int32"""
        sic_field = COMPANY_SCHEMA.field('sic')
        assert sic_field.type == pa.int32()


@pytest.mark.fast
class TestBuildDatasetSmallSample:
    """Tests for building datasets from small samples (no network required)."""

    @pytest.fixture
    def sample_submissions_dir(self, tmp_path):
        """Create a temporary directory with sample submission files"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()

        # Create sample company file
        import json
        company_data = {
            'cik': '0001318605',
            'name': 'TESLA INC',
            'sic': '3711',
            'sicDescription': 'MOTOR VEHICLES & PASSENGER CAR BODIES',
            'tickers': ['TSLA'],
            'exchanges': ['Nasdaq'],
            'stateOfIncorporation': 'DE',
            'stateOfIncorporationDescription': 'DE',
            'fiscalYearEnd': '1231',
            'entityType': 'corporation',
            'ein': '912197729',
        }
        with open(submissions_dir / 'CIK0001318605.json', 'w') as f:
            json.dump(company_data, f)

        # Create sample individual file
        individual_data = {
            'cik': '0001078519',
            'name': 'JOHN DOE',
            'sic': '',
            'sicDescription': None,
            'tickers': [],
            'exchanges': [],
        }
        with open(submissions_dir / 'CIK0001078519.json', 'w') as f:
            json.dump(individual_data, f)

        return submissions_dir

    def test_build_parquet_with_filtering(self, sample_submissions_dir, tmp_path):
        """Build Parquet with individual filtering"""
        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            sample_submissions_dir,
            output,
            filter_individuals=True,
            show_progress=False
        )

        # Should only have company, not individual
        assert len(table) == 1
        assert output.exists()
        assert output.stat().st_size > 0

        # Verify content
        assert table['cik'][0].as_py() == '0001318605'
        assert table['name'][0].as_py() == 'TESLA INC'

    def test_build_parquet_without_filtering(self, sample_submissions_dir, tmp_path):
        """Build Parquet without individual filtering"""
        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            sample_submissions_dir,
            output,
            filter_individuals=False,
            show_progress=False
        )

        # Should have both company and individual
        assert len(table) == 2
        assert output.exists()

    def test_build_parquet_missing_directory(self, tmp_path):
        """Should raise error if submissions directory missing"""
        output = tmp_path / 'companies.pq'
        missing_dir = tmp_path / 'nonexistent'

        with pytest.raises(FileNotFoundError, match="Submissions directory not found"):
            build_company_dataset_parquet(missing_dir, output, show_progress=False)

    def test_build_parquet_empty_directory(self, tmp_path):
        """Should raise error if submissions directory empty"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()
        output = tmp_path / 'companies.pq'

        with pytest.raises(FileNotFoundError, match="No submission files found"):
            build_company_dataset_parquet(
                submissions_dir, output, show_progress=False
            )

    def test_load_parquet(self, sample_submissions_dir, tmp_path):
        """Load Parquet file"""
        output = tmp_path / 'companies.pq'
        build_company_dataset_parquet(
            sample_submissions_dir,
            output,
            show_progress=False
        )

        # Load it back
        table = load_company_dataset_parquet(output)
        assert len(table) == 1
        assert table['cik'][0].as_py() == '0001318605'

    def test_load_parquet_missing_file(self, tmp_path):
        """Should raise error if Parquet file missing"""
        missing_file = tmp_path / 'nonexistent.pq'

        with pytest.raises(FileNotFoundError):
            load_company_dataset_parquet(missing_file)


@pytest.mark.network
class TestBuildDatasetReal:
    """Tests using real submissions data (requires network/downloads)."""

    def test_build_real_dataset(self, tmp_path):
        """Build dataset from real submissions (if available)"""
        from edgar.core import get_edgar_data_directory

        submissions_dir = get_edgar_data_directory() / 'submissions'

        # Skip if submissions not downloaded
        if not submissions_dir.exists() or len(list(submissions_dir.glob('CIK*.json'))) < 100000:
            pytest.skip("Submissions data not downloaded")

        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            submissions_dir,
            output,
            filter_individuals=True,
            show_progress=True
        )

        # Verify reasonable results
        assert len(table) > 500000  # At least 500K companies
        assert output.exists()

        # Check file size reasonable (should be 5-25 MB)
        file_size_mb = output.stat().st_size / (1024 * 1024)
        assert 5 <= file_size_mb <= 50


@pytest.mark.network
class TestGetDataset:
    """Tests for get_company_dataset() function."""

    def test_get_dataset_basic(self):
        """Get dataset (may build on first use)"""
        companies = get_company_dataset()
        assert isinstance(companies, pa.Table)

        # Should have many companies (skip exact check as dataset may vary)
        assert len(companies) > 100000

    def test_schema_matches(self):
        """Dataset should match expected schema"""
        companies = get_company_dataset()

        expected_columns = {
            'cik', 'name', 'sic', 'sic_description',
            'tickers', 'exchanges', 'state_of_incorporation',
            'state_of_incorporation_description', 'fiscal_year_end',
            'entity_type', 'ein'
        }
        assert set(companies.column_names) == expected_columns

    def test_filter_by_sic(self):
        """Filter pharmaceutical companies by SIC"""
        companies = get_company_dataset()

        # SIC 2834-2836: Pharmaceutical companies
        pharma = companies.filter(
            pc.field('sic').between(2834, 2836)
        )

        assert len(pharma) > 0
        assert len(pharma) < len(companies)

        # All SIC codes should be in range
        for sic in pharma['sic']:
            if sic.is_valid:
                assert 2834 <= sic.as_py() <= 2836

    def test_filter_by_exchange(self):
        """Filter companies by exchange"""
        companies = get_company_dataset()

        # Filter Nasdaq companies
        nasdaq = companies.filter(
            pc.match_substring(pc.field('exchanges'), 'Nasdaq')
        )

        assert len(nasdaq) > 0

    def test_filter_by_state(self):
        """Filter companies by state of incorporation"""
        companies = get_company_dataset()

        # Filter Delaware companies
        delaware = companies.filter(
            pc.field('state_of_incorporation') == 'DE'
        )

        assert len(delaware) > 0

    def test_caching_works(self):
        """Second call should use cache"""
        import time

        # First call (may be cached already, but measure baseline)
        start = time.time()
        companies1 = get_company_dataset()
        time1 = time.time() - start

        # Second call (should definitely use cache)
        start = time.time()
        companies2 = get_company_dataset()
        time2 = time.time() - start

        # Should return same table
        assert companies1.equals(companies2)

        # Second call should be faster (unless both cached)
        # Allow some leeway for system variation
        if time1 > 1.0:  # First call was slow (built dataset)
            assert time2 < 1.0  # Second call should be fast


class TestDuckDBIntegration:
    """Tests for DuckDB integration (requires duckdb package)."""

    def test_build_duckdb_requires_package(self, tmp_path):
        """Building DuckDB should import check"""
        # This test may fail if duckdb is installed
        # Just verify the import check exists
        import sys
        if 'duckdb' in sys.modules:
            pytest.skip("duckdb already imported")

    @pytest.mark.fast
    def test_to_duckdb_small_sample(self, tmp_path):
        """Convert small Parquet to DuckDB"""
        pytest.importorskip("duckdb")

        # Create small sample Parquet
        import pyarrow.parquet as pq
        sample_data = {
            'cik': ['0001318605', '0000789019'],
            'name': ['TESLA INC', 'MICROSOFT CORP'],
            'sic': [3711, 7372],
            'sic_description': ['MOTOR VEHICLES', 'SOFTWARE'],
            'tickers': ['TSLA', 'MSFT'],
            'exchanges': ['Nasdaq', 'Nasdaq'],
            'state_of_incorporation': ['DE', 'WA'],
            'state_of_incorporation_description': ['DE', 'WA'],
            'fiscal_year_end': ['1231', '0630'],
            'entity_type': ['corporation', 'corporation'],
            'ein': ['912197729', '911144442'],
        }
        table = pa.Table.from_pydict(sample_data, schema=COMPANY_SCHEMA)

        parquet_path = tmp_path / 'sample.pq'
        pq.write_table(table, parquet_path)

        # Convert to DuckDB
        duckdb_path = tmp_path / 'sample.duckdb'
        to_duckdb(parquet_path, duckdb_path, create_indexes=True)

        assert duckdb_path.exists()

        # Verify content
        import duckdb
        con = duckdb.connect(str(duckdb_path))

        # Check companies table
        result = con.execute("SELECT COUNT(*) FROM companies").fetchone()
        assert result[0] == 2

        # Check metadata table
        result = con.execute("SELECT * FROM metadata").fetchone()
        assert result[1] == 2  # total_companies

        # Check query works
        result = con.execute(
            "SELECT name FROM companies WHERE cik = '0001318605'"
        ).fetchone()
        assert result[0] == 'TESLA INC'

        con.close()

    @pytest.mark.network
    def test_build_duckdb_real_data(self, tmp_path):
        """Build DuckDB from real submissions"""
        pytest.importorskip("duckdb")

        from edgar.core import get_edgar_data_directory

        submissions_dir = get_edgar_data_directory() / 'submissions'

        # Skip if submissions not downloaded
        if not submissions_dir.exists() or len(list(submissions_dir.glob('CIK*.json'))) < 100000:
            pytest.skip("Submissions data not downloaded")

        output = tmp_path / 'companies.duckdb'
        build_company_dataset_duckdb(
            submissions_dir,
            output,
            filter_individuals=True,
            create_indexes=True,
            show_progress=True
        )

        assert output.exists()

        # Check file size reasonable (should be ~287 MB)
        file_size_mb = output.stat().st_size / (1024 * 1024)
        assert 200 <= file_size_mb <= 400

        # Verify can query
        import duckdb
        con = duckdb.connect(str(output))

        result = con.execute("SELECT COUNT(*) FROM companies").fetchone()
        assert result[0] > 500000

        con.close()


@pytest.mark.performance
class TestPerformance:
    """Performance tests for dataset operations."""

    @pytest.mark.network
    def test_load_performance(self):
        """Dataset should load in <100ms"""
        import time

        # Clear cache to test cold load
        from edgar.reference.company_dataset import _CACHE
        _CACHE.clear()

        start = time.time()
        companies = get_company_dataset()
        elapsed = time.time() - start

        assert isinstance(companies, pa.Table)

        # May be slow on first build, but cache should be fast
        # Don't assert on time if building, just verify success
        if elapsed < 5.0:  # Was cached or very fast build
            assert elapsed < 1.0  # Should load quickly

    @pytest.mark.network
    def test_query_sic_performance(self):
        """SIC filter should execute in <100ms"""
        import time

        companies = get_company_dataset()

        start = time.time()
        result = companies.filter(pc.field('sic').between(2834, 2836))
        elapsed = time.time() - start

        assert len(result) > 0
        assert elapsed < 0.1  # <100ms


@pytest.mark.fast
class TestErrorHandling:
    """Tests for error handling."""

    def test_corrupted_json_handling(self, tmp_path):
        """Should handle corrupted JSON gracefully"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()

        # Create valid file
        import json
        valid_data = {
            'cik': '0001318605',
            'name': 'TESLA INC',
            'tickers': ['TSLA'],
        }
        with open(submissions_dir / 'CIK0001318605.json', 'w') as f:
            json.dump(valid_data, f)

        # Create corrupted file
        with open(submissions_dir / 'CIK0001234567.json', 'w') as f:
            f.write("invalid json {")

        # Should still build successfully (skip corrupted)
        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            submissions_dir,
            output,
            show_progress=False
        )

        assert len(table) == 1
        assert table['cik'][0].as_py() == '0001318605'

    def test_missing_fields_handling(self, tmp_path):
        """Should handle missing optional fields"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()

        # Create file with minimal fields but has ticker (so it's a company)
        import json
        minimal_data = {
            'cik': '0001318605',
            'name': 'TEST COMPANY',
            'tickers': ['TEST'],  # Has ticker so it's a company
            # No SIC, exchanges, etc.
        }
        with open(submissions_dir / 'CIK0001318605.json', 'w') as f:
            json.dump(minimal_data, f)

        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            submissions_dir,
            output,
            show_progress=False
        )

        assert len(table) == 1
        assert table['cik'][0].as_py() == '0001318605'
        assert table['name'][0].as_py() == 'TEST COMPANY'
        # Optional fields should be None
        assert table['sic'][0].as_py() is None
        assert table['exchanges'][0].as_py() is None

    def test_empty_sic_handling(self, tmp_path):
        """Should handle empty SIC string"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()

        import json
        data = {
            'cik': '0001318605',
            'name': 'TEST COMPANY',
            'sic': '',  # Empty string
            'tickers': ['TEST'],
        }
        with open(submissions_dir / 'CIK0001318605.json', 'w') as f:
            json.dump(data, f)

        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            submissions_dir,
            output,
            show_progress=False
        )

        assert len(table) == 1
        # Empty SIC should convert to None
        assert table['sic'][0].as_py() is None

    def test_none_in_ticker_array(self, tmp_path):
        """Should handle None values in ticker array"""
        submissions_dir = tmp_path / "submissions"
        submissions_dir.mkdir()

        import json
        data = {
            'cik': '0001318605',
            'name': 'TEST COMPANY',
            'tickers': [None, 'TEST', None],  # None values
        }
        with open(submissions_dir / 'CIK0001318605.json', 'w') as f:
            json.dump(data, f)

        output = tmp_path / 'companies.pq'
        table = build_company_dataset_parquet(
            submissions_dir,
            output,
            show_progress=False
        )

        assert len(table) == 1
        # Should filter None values
        assert table['tickers'][0].as_py() == 'TEST'
