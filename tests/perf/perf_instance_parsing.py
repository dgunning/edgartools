import timeit
from pathlib import Path
from edgar.xbrl import XBRLInstance

instance_xml = None

def setup_code():
    global instance_xml
    instance_xml = Path('data/xbrl/datafiles/aapl/aapl-20230930_htm.xml').read_text()

def parse_function():
    global instance_xml
    XBRLInstance.parse(instance_xml)

if __name__ == "__main__":
    # Warm-up run
    setup_code()
    parse_function()

    # Number of repetitions for each test
    number = 10
    # Number of times to repeat the test
    repeat = 5

    # Run the benchmark
    results = timeit.repeat(
        stmt="parse_function()",
        setup="from __main__ import setup_code, parse_function; setup_code()",
        number=number,
        repeat=repeat,
        globals=globals()
    )

    # Process and print results
    avg_time = sum(results) / len(results)
    best_time = min(results)
    worst_time = max(results)

    print(f"Average time: {avg_time:.6f} seconds")
    print(f"Best time: {best_time:.6f} seconds")
    print(f"Worst time: {worst_time:.6f} seconds")
    print(f"Standard deviation: {(sum((x - avg_time) ** 2 for x in results) / len(results)) ** 0.5:.6f} seconds")