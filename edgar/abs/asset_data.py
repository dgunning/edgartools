"""
ABS-EE asset-level data (EX-102) as typed DataFrames.

Every Form ABS-EE carries an EX-102 exhibit: one XML document listing every
asset in the pool for one reporting period. The schema depends on the asset
class (auto loans, auto leases, CMBS, RMBS, debt securities), and the largest
files run to hundreds of megabytes, so the reader here streams:

- It parses with an lxml pull parser fed 1 MB chunks and frees each asset as
  soon as it has been read. It never holds the document as a string.
- It reads from any byte source: a Filing, a path (.xml, .gz, or a full SGML
  submission .txt/.nc), raw bytes, or an open binary stream such as a gzip,
  zstd or cloud-object reader. A submission is scanned for its EX-102 document
  on the fly.
- It is schema-agnostic underneath. Every leaf tag under <assets> becomes a
  column, and a nested element (a CMBS <property>) becomes a row in a child
  table keyed by the asset number.

Two tiers, chosen by the document's namespace:

- **Curated** (auto loan, auto lease, CMBS). Columns are the XSD element names
  in snake_case, typed from SEC's published schemas (see absee_schemas.py),
  and every column the schema declares is present, even when a filer leaves it
  out. These names and dtypes are a versioned contract (CONTRACT_VERSION).
- **Raw** (every other ABS-EE schema: RMBS, debt securities). Original tag
  names, string values, and ``info.curated`` is False.

Typing rules for the curated tier:

======== ===================== ===========================================
kind     dtype                 rule
======== ===================== ===========================================
str      string[pyarrow]       stripped text
code     string[pyarrow]       the code as filed; ``code_meanings()`` decodes
int      Int64                 non-integers become <NA>
decimal  float64               non-numbers become NaN
date     datetime64[ns]        MM-DD-YYYY
month    datetime64[ns]        MM/YYYY, as the first day of that month
bool     boolean               true/false
======== ===================== ===========================================

A tag that may repeat within one asset (``zeroBalanceCode``,
``modificationTypeCode`` ...) is joined with ``|`` into one string. A value the
reader could not convert is counted in ``info.coercion_failures`` rather than
dropped silently, and a tag the schema does not declare is kept as a string
column and listed in ``info.unmapped_tags``.

Usage::

    from edgar import find
    data = find("0001104659-26-111517").obj()      # World Omni 2022-C, ABS-EE
    data.assets                                     # one row per loan
    data.info                                       # schema, period, accession...
    data.summary()

    from edgar.abs import AssetData
    data = AssetData.from_source("0001193125-25-323206.nc.gz")   # stored submission
"""

from __future__ import annotations

import gzip
import io
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import IO, Any, Dict, Iterable, Iterator, List, Optional, Union

import pandas as pd
from lxml import etree
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.abs.absee_schemas import CODE_MEANINGS, CONTRACT_VERSION, NAMESPACE_PREFIX, SCHEMAS, SPEC_VERSION
from edgar.exceptions import DataObjectError, ParsingError
from edgar.richtools import repr_rich

__all__ = ['AssetData', 'AssetDataInfo', 'AssetDataSummary', 'ABS_EE_FORMS', 'MULTI_VALUE_SEPARATOR']

ABS_EE_FORMS = ['ABS-EE', 'ABS-EE/A']

MULTI_VALUE_SEPARATOR = '|'

_CHUNK_SIZE = 1 << 20      # bytes fed to the parser per call
_FLUSH_ROWS = 20_000       # rows buffered as Python objects before typing them
_SNIFF_SIZE = 4096         # bytes read up front to tell a submission from bare XML
_STRING = pd.StringDtype("pyarrow")

SourceType = Union[str, bytes, Path, IO[bytes]]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssetDataInfo:
    """What one EX-102 document is, independent of its rows."""
    schema: str                                  # autoloan, autolease, cmbs, rmbs, debtsecurities, or the namespace's last-but-one segment
    namespace: str
    curated: bool
    row_count: int
    table_counts: Dict[str, int]
    reporting_period_start: Optional[date] = None
    reporting_period_end: Optional[date] = None
    spec_version: str = SPEC_VERSION             # EDGAR ABS XML Technical Specification the curated types come from
    contract_version: Optional[str] = None       # None for the raw tier
    accession_no: Optional[str] = None
    cik: Optional[int] = None
    company: Optional[str] = None
    form: Optional[str] = None
    filing_date: Optional[date] = None
    is_amendment: Optional[bool] = None
    document: Optional[str] = None               # EX-102 file name, when known
    unmapped_tags: tuple = ()
    coercion_failures: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssetDataSummary:
    """Pool-level figures. Fields the schema has no column for stay None."""
    schema: str
    num_assets: int
    num_properties: Optional[int] = None
    total_original_amount: Optional[float] = None
    total_current_balance: Optional[float] = None
    weighted_avg_interest_rate: Optional[float] = None   # by current balance
    avg_credit_score: Optional[float] = None
    delinquent_30_plus: Optional[int] = None             # current delinquency status of 30+ days
    top_states: Dict[str, int] = field(default_factory=dict)
    top_makes: Dict[str, int] = field(default_factory=dict)
    property_types: Dict[str, int] = field(default_factory=dict)


# Columns summary() reads, per curated schema.
_SUMMARY_COLUMNS = {
    'autoloan': dict(original='original_loan_amount', balance='reporting_period_actual_end_balance_amount',
                     rate='reporting_period_interest_rate_percentage', score='obligor_credit_score',
                     state=('assets', 'obligor_geographic_location'), delinquency='current_delinquency_status',
                     make='vehicle_manufacturer_name'),
    'autolease': dict(original='acquisition_cost', balance='reporting_period_securitization_value_amount',
                      score='lessee_credit_score', state=('assets', 'lessee_geographic_location'),
                      delinquency='current_delinquency_status', make='vehicle_manufacturer_name'),
    'cmbs': dict(original='original_loan_amount', balance='report_period_end_actual_balance_amount',
                 rate='report_period_interest_rate_percentage', state=('property', 'property_state'),
                 property_type=('property', 'property_type_code')),
}


# ---------------------------------------------------------------------------
# Byte sources
# ---------------------------------------------------------------------------

def _iter_stream(stream: IO[bytes]) -> Iterator[bytes]:
    while True:
        chunk = stream.read(_CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


def _ex102_from_submission(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """The EX-102 document's bytes out of a streamed SGML submission.

    Scans for ``<TYPE>EX-102``, then for ``<TEXT>`` (and an optional ``<XML>``
    wrapper), and yields what follows until ``</XML>`` or ``</TEXT>``. Markers may
    straddle chunk boundaries, so the tail of each chunk is carried over.
    """
    markers = [b'<TYPE>EX-102', b'<TEXT>']
    buffer = b''
    it = iter(chunks)
    for marker in markers:
        while True:
            pos = buffer.find(marker)
            if pos >= 0:
                buffer = buffer[pos + len(marker):]
                break
            buffer = buffer[-(len(marker) - 1):]
            chunk = next(it, None)
            if chunk is None:
                raise DataObjectError(
                    "This submission has no EX-102 document, which is where ABS-EE asset-level data lives.")
            buffer += chunk
    # Skip whitespace and an optional <XML> wrapper.
    while len(buffer) < 16:
        chunk = next(it, None)
        if chunk is None:
            break
        buffer += chunk
    buffer = buffer.lstrip()
    if buffer[:5].upper() == b'<XML>':
        buffer = buffer[5:].lstrip()  # an XML declaration must come first
    tail = 7  # len(b'</TEXT>')
    while True:
        cut = min((p for p in (buffer.find(b'</XML>'), buffer.find(b'</TEXT>')) if p >= 0), default=-1)
        if cut >= 0:
            yield buffer[:cut]
            return
        if len(buffer) > tail:
            yield buffer[:-tail]
            buffer = buffer[-tail:]
        chunk = next(it, None)
        if chunk is None:
            yield buffer
            return
        buffer += chunk


def _is_submission(head: bytes) -> bool:
    head = head.lstrip()[:2048].upper()
    return (head.startswith(b'<SEC-DOCUMENT>') or head.startswith(b'<SUBMISSION>') or head.startswith(b'<DOCUMENT>')
            or head.startswith(b'-----BEGIN PRIVACY') or head.startswith(b'<SEC-HEADER>'))


def _chunks_from(source: SourceType) -> Iterator[bytes]:
    """Bytes of the EX-102 XML from any supported source, in chunks."""
    if isinstance(source, str) and source.lstrip().startswith('<'):
        source = source.encode('utf-8')
    if isinstance(source, (bytes, bytearray, memoryview)):
        data = bytes(source)
        chunks = (data[i:i + _CHUNK_SIZE] for i in range(0, len(data), _CHUNK_SIZE))
        return _ex102_from_submission(chunks) if _is_submission(data[:2048]) else chunks
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"No such file: {path}")
        opener = gzip.open if path.suffix == '.gz' else open
        return _chunks_from_stream(opener(path, 'rb'), close=True)
    if hasattr(source, 'read'):
        return _chunks_from_stream(source, close=False)
    raise TypeError(f"Cannot read ABS-EE asset data from {type(source).__name__}: "
                    "pass XML text or bytes, a path, or a binary stream")


def _chunks_from_stream(stream: IO[bytes], close: bool) -> Iterator[bytes]:
    try:
        first = stream.read(max(_CHUNK_SIZE, _SNIFF_SIZE))
        if isinstance(first, str):
            raise TypeError("Open the stream in binary mode ('rb')")

        def rest():
            yield first
            yield from _iter_stream(stream)

        if _is_submission(first[:2048]):
            yield from _ex102_from_submission(rest())
        else:
            yield from rest()
    finally:
        if close:
            stream.close()


# ---------------------------------------------------------------------------
# Streaming parse
# ---------------------------------------------------------------------------

class _ColumnBuffer:
    """Rows accumulated column-wise, typed in blocks of _FLUSH_ROWS."""

    def __init__(self, typer):
        self.columns: Dict[str, List[Optional[str]]] = {}
        self.n = 0
        self.frames: List[pd.DataFrame] = []
        self.typer = typer

    def append(self, row: Dict[str, str]):
        columns = self.columns
        for tag in row:
            if tag not in columns:
                columns[tag] = [None] * self.n
        for tag, values in columns.items():
            values.append(row.get(tag))
        self.n += 1
        if self.n >= _FLUSH_ROWS:
            self.flush()

    def flush(self):
        if self.n:
            self.frames.append(self.typer(self.columns, self.n))
        self.columns = {}
        self.n = 0

    def frame(self) -> Optional[pd.DataFrame]:
        self.flush()
        if not self.frames:
            return None
        if len(self.frames) == 1:
            return self.frames[0]
        return pd.concat(self.frames, ignore_index=True)


def _local(tag: str) -> str:
    return tag[tag.index('}') + 1:] if tag[0] == '{' else tag


def _schema_key(namespace: str) -> str:
    for key, spec in SCHEMAS.items():
        if spec['namespace'] == namespace:
            return key
    # .../absee/<schema>/assetdata
    parts = namespace.rstrip('/').split('/')
    return parts[-2] if len(parts) >= 2 else namespace


class _Parse:
    """One pass over an EX-102 document."""

    def __init__(self):
        self.namespace: Optional[str] = None
        self.schema: Optional[str] = None
        self.spec: Optional[Dict] = None
        self.buffers: Dict[str, _ColumnBuffer] = {}
        self.coercion_failures: Dict[str, int] = {}
        self.unmapped: Dict[str, set] = {}

    # -- typing ---------------------------------------------------------
    def _typer(self, table: str):
        spec_table = self.spec['tables'].get(table, {}) if self.spec else None

        def typed(columns: Dict[str, List], n: int) -> pd.DataFrame:
            if spec_table is None:  # raw tier
                return pd.DataFrame({tag: pd.array(values, dtype=_STRING) for tag, values in columns.items()})
            data = {}
            for tag, (column, kind, multi) in spec_table.items():
                values = columns.get(tag)
                data[column] = self._convert(column, values if values is not None else [None] * n,
                                             'str' if multi and kind not in ('str', 'code') else kind)
            for tag, values in columns.items():
                if tag not in spec_table and tag != '__key__':
                    self.unmapped.setdefault(table, set()).add(tag)
                    data[_snake(tag)] = pd.array(values, dtype=_STRING)
            if '__key__' in columns:
                data = {'asset_number': pd.array(columns['__key__'], dtype=_STRING), **data}
            return pd.DataFrame(data)
        return typed

    def _convert(self, column: str, values: List[Optional[str]], kind: str):
        if kind in ('str', 'code'):
            return pd.array(values, dtype=_STRING)
        raw = pd.Series(values, dtype=object)
        present = raw.notna() & (raw != '')
        if kind == 'decimal':
            out = pd.to_numeric(raw, errors='coerce').astype('float64')
        elif kind == 'int':
            num = pd.to_numeric(raw, errors='coerce')
            num = num.where(num.isna() | (num == num.round()))
            out = num.astype('Int64')
        elif kind == 'date':
            out = pd.to_datetime(raw, format='%m-%d-%Y', errors='coerce').astype('datetime64[ns]')
        elif kind == 'month':
            out = pd.to_datetime(raw, format='%m/%Y', errors='coerce').astype('datetime64[ns]')
        elif kind == 'bool':
            out = raw.str.lower().map({'true': True, 'false': False, '1': True, '0': False}).astype('boolean')
        else:  # pragma: no cover - generator emits only the kinds above
            raise ParsingError(f"absee_schemas.py declares an unknown column kind {kind!r} for {column}")
        failed = int((present & out.isna()).sum())
        if failed:
            self.coercion_failures[column] = self.coercion_failures.get(column, 0) + failed
        return out.to_numpy() if kind == 'decimal' else out.array

    # -- events ---------------------------------------------------------
    def _start_schema(self, namespace: str):
        self.namespace = namespace
        self.schema = _schema_key(namespace)
        spec = SCHEMAS.get(self.schema)
        self.spec = spec if spec and spec['curated'] else None

    def _buffer(self, table: str) -> _ColumnBuffer:
        buffer = self.buffers.get(table)
        if buffer is None:
            buffer = self.buffers[table] = _ColumnBuffer(self._typer(table))
        return buffer

    def _asset(self, el):
        row: Dict[str, str] = {}
        children: List = []
        for child in el:
            tag = child.tag
            if not isinstance(tag, str):  # comment or processing instruction
                continue
            if len(child):
                children.append(child)
                continue
            name = _local(tag)
            text = (child.text or '').strip()
            if name in row:
                row[name] = f"{row[name]}{MULTI_VALUE_SEPARATOR}{text}"
            else:
                row[name] = text
        self._buffer('assets').append(row)
        key = row.get('assetNumber')
        for child in children:
            sub: Dict[str, str] = {'__key__': key} if self.spec else {'assetNumber': key}
            for leaf in child.iter():
                if leaf is child or not isinstance(leaf.tag, str) or len(leaf):
                    continue
                name = _local(leaf.tag)
                text = (leaf.text or '').strip()
                sub[name] = f"{sub[name]}{MULTI_VALUE_SEPARATOR}{text}" if name in sub else text
            self._buffer(_local(child.tag)).append(sub)

    def run(self, chunks: Iterable[bytes]) -> Dict[str, pd.DataFrame]:
        # 'end' events only: the root is checked at the first one, which arrives
        # after a few hundred bytes, so a non-ABS-EE document fails fast.
        parser = etree.XMLPullParser(events=('end',), huge_tree=True, resolve_entities=False,
                                     no_network=True)
        root_seen = False
        fed = 0
        try:
            for chunk in chunks:
                if not chunk:
                    continue
                fed += len(chunk)
                parser.feed(chunk)
                for _event, el in parser.read_events():
                    if not root_seen:
                        root_seen = True
                        self._check_root(el.getroottree().getroot())
                    tag = el.tag
                    if not isinstance(tag, str):
                        continue
                    parent = el.getparent()
                    if _local(tag) == 'assets' and parent is not None and parent.getparent() is None:
                        self._asset(el)
                        el.clear()
                        while el.getprevious() is not None:
                            del parent[0]
            if fed == 0:
                raise ParsingError("The EX-102 source is empty: no XML was found to parse.")
            parser.close()
        except etree.XMLSyntaxError as e:
            raise ParsingError(f"The EX-102 document is not well-formed XML: {e}") from e
        if not root_seen:
            raise ParsingError("The EX-102 source is empty: no XML was found to parse.")
        tables = {}
        for table, buffer in self.buffers.items():
            frame = buffer.frame()
            if frame is not None:
                tables[table] = frame
        if 'assets' not in tables:
            tables['assets'] = self._typer('assets')({}, 0)
        if self.spec:
            for table in self.spec['tables']:
                if table not in tables:
                    empty = self._typer(table)({'__key__': []}, 0) if table != 'assets' else None
                    if empty is not None:
                        tables[table] = empty
        return tables

    def _check_root(self, el):
        tag = el.tag if isinstance(el.tag, str) else ''
        namespace = etree.QName(tag).namespace if tag.startswith('{') else None
        if _local(tag) != 'assetData' or not namespace or not namespace.startswith(NAMESPACE_PREFIX):
            raise DataObjectError(
                f"This XML is not ABS-EE asset data: its root element is <{_local(tag)}> in namespace "
                f"{namespace!r}, and ABS-EE asset data is an <assetData> document in a "
                f"{NAMESPACE_PREFIX}<schema>/assetdata namespace.")
        self._start_schema(namespace)


def _snake(name: str) -> str:
    import re
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower()


# ---------------------------------------------------------------------------
# The data object
# ---------------------------------------------------------------------------

class AssetData:
    """
    Asset-level data from one ABS-EE EX-102 exhibit.

    ``assets`` has one row per asset; ``tables`` holds it plus any child tables
    (``property`` for CMBS). ``info`` says what the document is: schema, tier,
    reporting period, row counts and, when read from a Filing, which filing.

    Build one with ``filing.obj()`` on an ABS-EE filing, ``AssetData.from_filing``,
    or ``AssetData.from_source`` for a file, bytes or a stream.
    """

    def __init__(self, tables: Dict[str, pd.DataFrame], info: AssetDataInfo):
        self.tables = tables
        self.info = info
        for frame in tables.values():
            frame.attrs['absee'] = info.to_dict()

    # -- construction ---------------------------------------------------
    @classmethod
    def from_source(cls, source: SourceType, **filing_fields) -> 'AssetData':
        """
        Parse an EX-102 document from XML text or bytes, a path (``.xml``, ``.gz``,
        or a full SGML submission such as ``<accession>.nc`` / ``.nc.gz`` / ``.txt``),
        or an open binary stream.

        Raises:
            DataObjectError: the source has no EX-102 document, or its XML is not
                ABS-EE asset data.
            ParsingError: the XML is malformed or empty.
        """
        parse = _Parse()
        tables = parse.run(_chunks_from(source))
        info = _build_info(parse, tables, **filing_fields)
        return cls(tables, info)

    @classmethod
    def from_xml(cls, xml: Union[str, bytes]) -> 'AssetData':
        """Parse an EX-102 XML document held in memory."""
        return cls.from_source(xml.encode('utf-8') if isinstance(xml, str) else xml)

    @classmethod
    def from_filing(cls, filing) -> 'AssetData':
        """
        Read the EX-102 exhibit of a filing (normally ABS-EE or ABS-EE/A).

        The exhibit is streamed: from the stored submission when local storage
        holds it, otherwise straight from its URL on sec.gov, so a 400 MB file is
        never held in memory as text.

        Raises:
            DataObjectError: the filing has no EX-102 exhibit, or it is not ABS-EE
                asset data.
        """
        fields = dict(accession_no=filing.accession_no, cik=int(filing.cik), company=filing.company,
                      form=filing.form, filing_date=_as_date(filing.filing_date),
                      is_amendment=filing.form.endswith('/A'))
        try:
            source, document = _filing_source(filing)
        except DataObjectError as e:
            raise DataObjectError(
                f"Form {filing.form} filing {filing.accession_no} has no EX-102 exhibit, so there is no "
                f"asset-level data to read. ABS-EE asset data is filed as EX-102.",
                form=filing.form, accession_no=filing.accession_no) from e
        return cls.from_source(source, document=document, **fields)

    # -- access ---------------------------------------------------------
    @property
    def assets(self) -> pd.DataFrame:
        """One row per asset."""
        return self.tables['assets']

    @property
    def properties(self) -> Optional[pd.DataFrame]:
        """CMBS only: one row per property, keyed by ``asset_number``. None for other schemas."""
        return self.tables.get('property')

    @property
    def schema(self) -> str:
        return self.info.schema

    @property
    def curated(self) -> bool:
        return self.info.curated

    def code_meanings(self, column: str) -> Dict[str, str]:
        """The SEC descriptions of a code column's values, e.g. ``{'1': 'Car', ...}``."""
        meanings = CODE_MEANINGS.get(self.schema, {})
        if column not in meanings:
            raise KeyError(f"{column!r} is not a code column of the {self.schema} schema. "
                           f"Code columns: {sorted(meanings)}")
        return dict(meanings[column])

    def __len__(self) -> int:
        return len(self.assets)

    # -- summary --------------------------------------------------------
    def summary(self) -> AssetDataSummary:
        """Pool-level totals and distributions. Raw-tier schemas get the asset count only."""
        df = self.assets
        result = AssetDataSummary(schema=self.schema, num_assets=len(df))
        columns = _SUMMARY_COLUMNS.get(self.schema) if self.curated else None
        if not columns or df.empty:
            return result
        if self.properties is not None:
            result.num_properties = len(self.properties)
        if 'original' in columns:
            result.total_original_amount = float(df[columns['original']].sum())
        if 'balance' in columns:
            result.total_current_balance = float(df[columns['balance']].sum())
        if 'rate' in columns and 'balance' in columns:
            rate, balance = df[columns['rate']], df[columns['balance']]
            mask = rate.notna() & balance.notna() & (balance > 0)
            if mask.any():
                result.weighted_avg_interest_rate = float((rate[mask] * balance[mask]).sum() / balance[mask].sum())
        if 'score' in columns:
            scores = df[columns['score']].dropna()
            if len(scores):
                result.avg_credit_score = float(scores.mean())
        if 'delinquency' in columns:
            result.delinquent_30_plus = int((df[columns['delinquency']].fillna(0) >= 30).sum())
        if 'state' in columns:
            table, column = columns['state']
            frame = self.tables.get(table)
            if frame is not None:
                result.top_states = _top(frame[column])
        if 'make' in columns:
            result.top_makes = _top(df[columns['make']].str.strip().str.upper())
        if 'property_type' in columns:
            table, column = columns['property_type']
            frame = self.tables.get(table)
            if frame is not None:
                result.property_types = _top(frame[column], n=None)
        return result

    # -- display --------------------------------------------------------
    def __str__(self) -> str:
        return f"AssetData({self.schema}, {len(self):,} assets)"

    def __repr__(self) -> str:
        return repr_rich(self.__rich__())

    def __rich__(self):
        info, s = self.info, self.summary()
        title = Text.assemble((f"ABS-EE Asset Data · {info.schema}", "bold deep_sky_blue1"),
                              (f"  {s.num_assets:,} assets", "dim"))
        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column("Label", style="grey70")
        table.add_column("Value")
        if info.company:
            table.add_row("Issuer", info.company)
        if info.accession_no:
            table.add_row("Accession", f"{info.accession_no} ({info.form})")
        if info.reporting_period_start or info.reporting_period_end:
            table.add_row("Period", f"{info.reporting_period_start} to {info.reporting_period_end}")
        table.add_row("Tier", "curated" if info.curated else "raw (original tags, string values)")
        if s.num_properties is not None:
            table.add_row("Properties", f"{s.num_properties:,}")
        if s.total_original_amount is not None:
            table.add_row("Original Amount", f"${s.total_original_amount:,.0f}")
        if s.total_current_balance is not None:
            table.add_row("Current Balance", f"${s.total_current_balance:,.0f}")
        if s.weighted_avg_interest_rate is not None:
            table.add_row("WA Interest Rate", f"{s.weighted_avg_interest_rate:.4g}")
        if s.avg_credit_score is not None:
            table.add_row("Avg Credit Score", f"{s.avg_credit_score:.0f}")
        if s.delinquent_30_plus is not None:
            table.add_row("30+ Days Delinquent", f"{s.delinquent_30_plus:,}")
        for label, dist in (("Top Makes", s.top_makes), ("Top States", s.top_states),
                            ("Property Types", s.property_types)):
            if dist:
                table.add_row(label, ", ".join(f"{k}: {v:,}" for k, v in list(dist.items())[:5]))
        return Panel(Group(table), title=title, box=box.ROUNDED)


def _top(series: pd.Series, n: Optional[int] = 10) -> Dict[str, int]:
    counts = series.dropna()
    counts = counts[counts != ''].value_counts()
    if n is not None:
        counts = counts.head(n)
    return {str(k): int(v) for k, v in counts.items()}


def _as_date(value) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _build_info(parse: _Parse, tables: Dict[str, pd.DataFrame], **filing_fields) -> AssetDataInfo:
    assets = tables['assets']
    start = end = None
    # reportingPeriodBeginningDate, reportingPeriodBeginDate, reportPeriodBeginningDate ...
    for column in assets.columns:
        lowered = column.lower().replace('_', '').replace('reporting', 'report')
        if not lowered.endswith('date'):
            continue
        if lowered.startswith('reportperiodbegin') and start is None:
            start = _first_date(assets[column])
        elif lowered.startswith('reportperiodend') and end is None:
            end = _first_date(assets[column])
    unmapped = tuple(sorted(f"{t}.{tag}" if t != 'assets' else tag
                            for t, tags in parse.unmapped.items() for tag in tags))
    return AssetDataInfo(
        schema=parse.schema, namespace=parse.namespace, curated=parse.spec is not None,
        row_count=len(assets), table_counts={k: len(v) for k, v in tables.items()},
        reporting_period_start=start, reporting_period_end=end,
        contract_version=CONTRACT_VERSION if parse.spec is not None else None,
        unmapped_tags=unmapped, coercion_failures=dict(parse.coercion_failures), **filing_fields)


def _first_date(series: pd.Series) -> Optional[date]:
    values = series.dropna()
    if values.empty:
        return None
    value = values.iloc[0]
    if isinstance(value, str):
        try:
            value = pd.to_datetime(value, format='%m-%d-%Y')
        except (ValueError, TypeError):
            return None
    return value.date() if hasattr(value, 'date') else None


# ---------------------------------------------------------------------------
# Finding the exhibit on a filing
# ---------------------------------------------------------------------------

def _is_ex102(document_type: Optional[str]) -> bool:
    return bool(document_type) and document_type.strip().upper().startswith('EX-102')


def _filing_source(filing):
    """(source, document name) for a filing's EX-102, preferring streams over strings."""
    # 1. Already loaded in memory: use it as is.
    sgml = getattr(filing, '_sgml', None)
    if sgml is not None:
        return _from_attachments(sgml.attachments)

    # 2. Local storage holds the submission: stream it from disk.
    from edgar.storage._local import is_using_local_storage, resolve_local_filing_path
    if is_using_local_storage():
        path = resolve_local_filing_path(str(filing.filing_date), filing.accession_no)
        if path is not None:
            return Path(path), None

    # 3. Datamule storage hands back a parsed submission.
    from edgar.storage.datamule import is_using_datamule_storage
    if is_using_datamule_storage():
        return _from_attachments(filing.attachments)

    # 4. Stream the exhibit itself from sec.gov, found through the index page.
    for attachment in filing.homepage.attachments:
        if _is_ex102(attachment.document_type):
            return _UrlStream(attachment.url), attachment.document
    raise DataObjectError("no EX-102")


def _from_attachments(attachments):
    for attachment in attachments:
        if _is_ex102(attachment.document_type):
            content = attachment.content
            if isinstance(content, str):
                content = content.encode('utf-8')
            return content, attachment.document
    raise DataObjectError("no EX-102")


class _UrlStream(io.RawIOBase):
    """A read()-able view of a streamed HTTP response, so the parser pulls 1 MB at a time."""

    def __init__(self, url: str):
        from edgar.httprequests import stream_with_retry
        self._responses = stream_with_retry(url, bypass_cache=True)
        self._response = next(self._responses)
        if self._response.status_code >= 400:
            raise DataObjectError(f"sec.gov answered {self._response.status_code} for {url}")
        self._chunks = self._response.iter_bytes(_CHUNK_SIZE)
        self._pending = b''

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        while size < 0 or len(self._pending) < size:
            chunk = next(self._chunks, None)
            if chunk is None:
                break
            self._pending += chunk
        if size < 0:
            data, self._pending = self._pending, b''
        else:
            data, self._pending = self._pending[:size], self._pending[size:]
        if not data:
            self.close()
        return data

    def close(self):
        if not self.closed:
            self._responses.close()
        super().close()
