"""Quick test of TenK migration to new HTMLParser."""
import time

from edgar import Filing

print("Creating Filing object...")
filing = Filing(
    form='10-K',
    filing_date='2023-04-06',
    company='Frontier Masters Fund',
    cik=1450722,
    accession_no='0001213900-23-028058'
)

print("Getting TenK object...")
start = time.time()
tenk = filing.obj()
print(f"TenK object created in {time.time() - start:.2f}s")

print("\nTenK type:", type(tenk))
print("Has document property:", hasattr(tenk, 'document'))
print("Has sections property:", hasattr(tenk, 'sections'))

print("\nTrying to access document (may trigger new parser)...")
start = time.time()
doc = tenk.document
print(f"Document accessed in {time.time() - start:.2f}s")
print("Document type:", type(doc))
print("Document is None:", doc is None)

if doc:
    print("\nTrying to access sections...")
    start = time.time()
    sections = tenk.sections
    print(f"Sections accessed in {time.time() - start:.2f}s")
    print("Number of sections:", len(sections) if sections else 0)
    if sections:
        print("Section keys:", list(sections.keys())[:5], "..." if len(sections) > 5 else "")

print("\nTrying to get Item 1 using __getitem__...")
start = time.time()
try:
    item1 = tenk['Item 1']
    print(f"Item 1 accessed in {time.time() - start:.2f}s")
    if item1:
        print(f"Item 1 length: {len(item1)} characters")
        print(f"Item 1 preview: {item1[:200]}...")
    else:
        print("Item 1 is None")
except Exception as e:
    print(f"ERROR accessing Item 1: {e}")
    import traceback
    traceback.print_exc()

print("\nTest complete!")
