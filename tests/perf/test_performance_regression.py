"""
Performance regression tests for HTML parser.

These tests ensure that parser performance does not degrade over time.
Thresholds are set based on current baseline performance.
"""

import time
import gc
from pathlib import Path
import pytest
import psutil

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


# Performance thresholds based on baseline benchmarks (2025-10-08)
# These represent current performance - will be tightened after optimizations

PARSE_TIME_THRESHOLDS = {
    'tiny': 0.01,      # <100KB
    'small': 0.5,      # <5MB
    'medium': 2.0,     # 5-20MB
    'large': 10.0,     # 20-50MB
    'xlarge': 15.0,    # >50MB
}

MEMORY_RATIO_THRESHOLDS = {
    'small': 25.0,     # Small docs have high ratio (will improve)
    'medium': 20.0,    # Medium docs
    'large': 5.0,      # Large docs more efficient
    'xlarge': 1.0,     # Streaming mode very efficient
}

MEMORY_LEAK_THRESHOLD = 10.0  # MB - Maximum allowed leak after GC

@pytest.mark.skip("Performance tests - enable as needed")
class TestParseSpeedRegression:
    """Test parsing speed does not regress."""

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_small_document_speed(self):
        """Small documents (<5MB) should parse quickly."""
        html_path = Path('data/html/Apple.10-Q.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        # Warm up (first parse may be slower)
        _ = parse_html(html)

        # Measure parse time
        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        threshold = PARSE_TIME_THRESHOLDS['small']
        assert elapsed < threshold, \
            f"Parse time {elapsed:.3f}s exceeds threshold {threshold}s for {size_mb:.1f}MB doc"

        # Verify content extracted
        assert len(doc.tables) > 0, "Should extract tables"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_medium_document_speed(self):
        """Medium documents (5-20MB) should parse in reasonable time."""
        html_path = Path('data/html/MSFT.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        # Measure parse time
        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        threshold = PARSE_TIME_THRESHOLDS['medium']
        assert elapsed < threshold, \
            f"Parse time {elapsed:.3f}s exceeds threshold {threshold}s for {size_mb:.1f}MB doc"

        assert len(doc.tables) > 0, "Should extract tables"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    @pytest.mark.slow
    def test_large_document_speed(self):
        """Large documents (>50MB) should parse efficiently with streaming."""
        html_path = Path('data/html/JPM.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)
        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        # Measure parse time
        start = time.perf_counter()
        doc = parse_html(html, config=config)
        elapsed = time.perf_counter() - start

        threshold = PARSE_TIME_THRESHOLDS['xlarge']
        assert elapsed < threshold, \
            f"Parse time {elapsed:.3f}s exceeds threshold {threshold}s for {size_mb:.1f}MB doc"

        assert len(doc.tables) > 0, "Should extract tables"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_throughput_meets_minimum(self):
        """Parser should maintain minimum throughput."""
        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        throughput = size_mb / elapsed  # MB/s
        min_throughput = 1.0  # Minimum 1 MB/s

        assert throughput >= min_throughput, \
            f"Throughput {throughput:.1f}MB/s below minimum {min_throughput}MB/s"


class TestMemoryRegression:
    """Test memory usage does not regress."""

    def setup_method(self):
        """Set up test - force garbage collection."""
        gc.collect()
        self.process = psutil.Process()

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_memory_ratio_small_docs(self):
        """Small documents should not use excessive memory."""
        html_path = Path('data/html/Apple.10-Q.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        mem_before = self.process.memory_info().rss / (1024 * 1024)
        doc = parse_html(html)
        _ = doc.tables
        mem_after = self.process.memory_info().rss / (1024 * 1024)

        memory_increase = mem_after - mem_before
        memory_ratio = memory_increase / size_mb if size_mb > 0 else 0

        max_ratio = MEMORY_RATIO_THRESHOLDS['small']
        assert memory_ratio < max_ratio, \
            f"Memory ratio {memory_ratio:.1f}x exceeds threshold {max_ratio}x for {size_mb:.1f}MB doc"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_memory_ratio_medium_docs(self):
        """Medium documents should be memory efficient."""
        html_path = Path('data/html/MSFT.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        mem_before = self.process.memory_info().rss / (1024 * 1024)
        doc = parse_html(html)
        _ = doc.tables
        mem_after = self.process.memory_info().rss / (1024 * 1024)

        memory_increase = mem_after - mem_before
        memory_ratio = memory_increase / size_mb if size_mb > 0 else 0

        max_ratio = MEMORY_RATIO_THRESHOLDS['medium']
        assert memory_ratio < max_ratio, \
            f"Memory ratio {memory_ratio:.1f}x exceeds threshold {max_ratio}x for {size_mb:.1f}MB doc"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_no_memory_leak(self):
        """Parser should not leak significant memory."""
        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()

        # Baseline memory
        gc.collect()
        mem_before = self.process.memory_info().rss / (1024 * 1024)

        # Parse and access properties
        doc = parse_html(html)
        _ = doc.tables
        _ = doc.sections
        del doc

        # Clean up
        gc.collect()
        mem_after = self.process.memory_info().rss / (1024 * 1024)

        leaked = mem_after - mem_before

        assert leaked < MEMORY_LEAK_THRESHOLD, \
            f"Memory leak detected: {leaked:.1f}MB leaked (threshold: {MEMORY_LEAK_THRESHOLD}MB)"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    @pytest.mark.slow
    def test_streaming_mode_memory_efficient(self):
        """Streaming mode should be very memory efficient."""
        html_path = Path('data/html/JPM.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        size_mb = len(html) / (1024 * 1024)
        config = ParserConfig(
            max_document_size=100 * 1024 * 1024,
            streaming_threshold=10 * 1024 * 1024
        )

        mem_before = self.process.memory_info().rss / (1024 * 1024)
        doc = parse_html(html, config=config)
        _ = doc.tables
        mem_after = self.process.memory_info().rss / (1024 * 1024)

        memory_increase = mem_after - mem_before
        memory_ratio = memory_increase / size_mb if size_mb > 0 else 0

        max_ratio = MEMORY_RATIO_THRESHOLDS['xlarge']
        assert memory_ratio < max_ratio, \
            f"Streaming mode memory ratio {memory_ratio:.1f}x exceeds threshold {max_ratio}x"


class TestBatchProcessingRegression:
    """Test batch processing performance."""

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_batch_processing_throughput(self):
        """Batch processing should maintain throughput."""
        corpus_dir = Path('data/html')
        files = list(corpus_dir.glob('*.10-K.html'))[:5]  # First 5 10-K files

        if len(files) < 3:
            pytest.skip("Not enough test files for batch processing test")

        config = ParserConfig(max_document_size=100 * 1024 * 1024)  # 100MB for large docs

        start = time.perf_counter()
        for file_path in files:
            html = file_path.read_text()
            doc = parse_html(html, config=config)
            _ = doc.tables
            del doc

        elapsed = time.perf_counter() - start
        throughput = len(files) / elapsed  # docs/second

        min_throughput = 1.0  # At least 1 doc/second
        assert throughput >= min_throughput, \
            f"Batch throughput {throughput:.2f} docs/s below minimum {min_throughput}"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_no_memory_accumulation_in_batch(self):
        """Memory should not accumulate across batch processing."""
        corpus_dir = Path('data/html')
        files = list(corpus_dir.glob('*.10-K.html'))[:3]

        if len(files) < 2:
            pytest.skip("Not enough test files")

        config = ParserConfig(max_document_size=100 * 1024 * 1024)  # 100MB for large docs

        gc.collect()
        process = psutil.Process()
        mem_before = process.memory_info().rss / (1024 * 1024)

        # Process multiple documents
        for file_path in files:
            html = file_path.read_text()
            doc = parse_html(html, config=config)
            _ = doc.tables
            del doc
            gc.collect()  # Force cleanup between docs

        mem_after = process.memory_info().rss / (1024 * 1024)
        accumulated = mem_after - mem_before

        # Allow some accumulation but not excessive
        max_accumulation = 20.0  # MB per document on average
        threshold = max_accumulation * len(files)

        assert accumulated < threshold, \
            f"Memory accumulated {accumulated:.1f}MB across {len(files)} docs " \
            f"(threshold: {threshold:.1f}MB)"


class TestSpecificOperationRegression:
    """Test specific operations don't regress."""

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_table_extraction_speed(self):
        """Table extraction should be fast."""
        html_path = Path('data/html/MSFT.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        doc = parse_html(html)

        # Measure table extraction time
        start = time.perf_counter()
        tables = doc.tables
        elapsed = time.perf_counter() - start

        # Should be nearly instant (lazy loading)
        threshold = 0.1  # 100ms
        assert elapsed < threshold, \
            f"Table extraction took {elapsed:.3f}s (threshold: {threshold}s)"

        assert len(tables) > 0, "Should extract tables"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_section_extraction_speed(self):
        """Section extraction should complete in reasonable time."""
        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        doc = parse_html(html)

        # Measure section extraction time
        start = time.perf_counter()
        sections = doc.sections
        elapsed = time.perf_counter() - start

        # Current baseline - will be much faster after optimization
        threshold = 5.0  # 5 seconds (currently ~3.7s)
        assert elapsed < threshold, \
            f"Section extraction took {elapsed:.3f}s (threshold: {threshold}s)"

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_text_extraction_speed(self):
        """Text extraction should be reasonably fast."""
        html_path = Path('data/html/Apple.10-Q.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()
        doc = parse_html(html)

        # Measure text extraction time
        start = time.perf_counter()
        text = doc.text()
        elapsed = time.perf_counter() - start

        threshold = 3.0  # 3 seconds
        assert elapsed < threshold, \
            f"Text extraction took {elapsed:.3f}s (threshold: {threshold}s)"

        assert len(text) > 0, "Should extract text"


class TestPerformanceConsistency:
    """Test performance is consistent across runs."""

    @pytest.mark.skip("Performance tests - enable as needed")
    @pytest.mark.performance
    def test_consistent_parse_time(self):
        """Parse time should be consistent across multiple runs."""
        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip(f"Test file not found: {html_path}")

        html = html_path.read_text()

        times = []
        for _ in range(5):
            start = time.perf_counter()
            doc = parse_html(html)
            _ = doc.tables
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            del doc

        # Calculate variance
        avg_time = sum(times) / len(times)
        variance = sum((t - avg_time) ** 2 for t in times) / len(times)
        std_dev = variance ** 0.5

        # Standard deviation should be less than 20% of average
        max_std_dev = avg_time * 0.2
        assert std_dev < max_std_dev, \
            f"Parse time inconsistent: std_dev={std_dev:.3f}s, avg={avg_time:.3f}s"

@pytest.mark.skip("Performance tests - enable as needed")
@pytest.mark.performance
def test_performance_summary(capsys):
    """
    Print performance summary for monitoring.

    This test always passes but prints current performance metrics.
    """
    corpus_dir = Path('data/html')
    test_files = {
        'Apple.10-Q.html': 'small',
        'Apple.10-K.html': 'medium',
        'MSFT.10-K.html': 'medium',
    }

    print("\n" + "="*80)
    print("CURRENT PERFORMANCE METRICS")
    print("="*80 + "\n")

    process = psutil.Process()

    for filename, category in test_files.items():
        file_path = corpus_dir / filename
        if not file_path.exists():
            continue

        html = file_path.read_text()
        size_mb = len(html) / (1024 * 1024)

        gc.collect()
        mem_before = process.memory_info().rss / (1024 * 1024)

        start = time.perf_counter()
        doc = parse_html(html)
        _ = doc.tables
        elapsed = time.perf_counter() - start

        mem_after = process.memory_info().rss / (1024 * 1024)
        memory_increase = mem_after - mem_before
        memory_ratio = memory_increase / size_mb if size_mb > 0 else 0

        print(f"{filename:25} {size_mb:>6.1f}MB  "
              f"{elapsed:>6.3f}s  "
              f"{memory_increase:>6.1f}MB ({memory_ratio:>4.1f}x)")

        del doc

    print("\n" + "="*80)

    # This test always passes - it's just for monitoring
    assert True
