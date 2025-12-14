"""Test SharesPrnAmount dtype in 13F-HR filings."""
from edgar import Filing

# Test with State Street filing
filing = Filing(
    form='13F-HR',
    filing_date='2024-11-14',
    company='STATE STREET CORP',
    cik=70858,
    accession_no='0001102113-24-000030'
)

print("=" * 80)
print("Testing SharesPrnAmount dtype in 13F-HR")
print("=" * 80)

thirteenf = filing.obj()
infotable = thirteenf.infotable

print(f"\nInfotable shape: {infotable.shape}")
print("\nColumn dtypes:")
for col in ['SharesPrnAmount', 'Value', 'SoleVoting', 'SharedVoting', 'NonVoting']:
    if col in infotable.columns:
        dtype = infotable[col].dtype
        print(f"  {col:20s}: {dtype}")

print("\nSharesPrnAmount sample values:")
print(infotable['SharesPrnAmount'].head(10))

# Check if it's int64
is_int = infotable['SharesPrnAmount'].dtype == 'int64'
print(f"\nIs SharesPrnAmount int64? {is_int}")

if not is_int:
    print(f"  ⚠️  WARNING: SharesPrnAmount is {infotable['SharesPrnAmount'].dtype}, expected int64")
else:
    print("  ✅ SharesPrnAmount has correct dtype (int64)")
