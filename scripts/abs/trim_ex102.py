"""Cut an EX-102 document down to its first N assets, byte for byte.

Test fixtures for the ABS-EE reader (tests/fixtures/absee/). Everything up to
the end of the Nth </assets> is copied verbatim, then the root is closed, so
every asset in the fixture is exactly as filed.

    python scripts/abs/trim_ex102.py full_ex102.xml 25 > tests/fixtures/absee/<name>.xml
"""
import re
import sys

path, count = sys.argv[1], int(sys.argv[2])
data = open(path, 'rb').read()
ends = [m.end() for m in re.finditer(rb'</(?:\w+:)?assets>', data)]
if len(ends) < count:
    raise SystemExit(f"{path} has only {len(ends)} assets")
root = re.search(rb'<((?:\w+:)?assetData)\b', data).group(1)
sys.stdout.buffer.write(data[:ends[count - 1]] + b'\n</' + root + b'>\n')
