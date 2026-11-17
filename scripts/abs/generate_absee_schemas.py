"""Generate edgar/abs/absee_schemas.py from SEC's ABS-EE XML schemas.

The curated tier of edgar.abs.AssetData types its columns from SEC's published
XSDs, not from sample files. This script turns those XSDs into a plain Python
module so the library carries no XSD at runtime and the column contract is a
reviewable diff.

Usage (from the repo root):

    curl -A "$EDGAR_IDENTITY" -O https://www.sec.gov/info/edgar/specifications/absxml-1.8_d.zip
    unzip absxml-1.8_d.zip && unzip "ABS XML Schema Files.zip" -d absee_xsd
    python scripts/abs/generate_absee_schemas.py absee_xsd > edgar/abs/absee_schemas.py
    ruff format edgar/abs/absee_schemas.py   # optional

Renaming or retyping a curated column changes a public contract consumed by
edgar-storage: bump CONTRACT_VERSION and add an upgrade-guide entry.
"""
import re
import sys
from pathlib import Path

from lxml import etree

XS = "{http://www.w3.org/2001/XMLSchema}"

SPEC_VERSION = "1.8"
CONTRACT_VERSION = "1.0"

# schema key -> (XSD file, curated?)
SCHEMA_FILES = {
    "autoloan": ("eis_ABS_AutoLoanAssetData.xsd", True),
    "autolease": ("eis_ABS_AutoLeaseAssetData.xsd", True),
    "cmbs": ("eis_ABS_CMBSAssetData.xsd", True),
    "rmbs": ("eis_ABS_RMBSAssetData.xsd", False),
    "debtsecurities": ("eis_ABS_DebtSecuritiesAssetData.xsd", False),
}
COMMON_FILES = ("eis_Common.xsd", "eis_ABS_Common.xsd")

# Declared as strings in the XSD but numeric in meaning. Values that are not
# integers (a filer's "NONE", "Unknown") become missing.
KIND_OVERRIDES = {
    "obligorCreditScore": "int",
    "lesseeCreditScore": "int",
    "vehicleModelYear": "int",
}

# SEC typos in element names, fixed in the column name only.
COLUMN_OVERRIDES = {
    "mostRecentDebtServiceCoverageNetCashFlowpercentage": "most_recent_debt_service_coverage_net_cash_flow_percentage",
    "netCashFlowFlowSecuritizationAmount": "net_cash_flow_securitization_amount",
    "DemandResolutionDate": "demand_resolution_date",
}


def snake_case(name: str) -> str:
    if name in COLUMN_OVERRIDES:
        return COLUMN_OVERRIDES[name]
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    return s.lower()


class TypeResolver:
    def __init__(self, docs):
        self.simple = {}
        for doc in docs:
            for st in doc.iter(f"{XS}simpleType"):
                if st.get("name"):
                    self.simple[st.get("name")] = st

    def kind(self, type_name: str) -> str:
        local = type_name.split(":")[-1]
        if type_name.startswith("xs:"):
            return {"decimal": "decimal", "integer": "int", "int": "int", "boolean": "bool"}.get(local, "str")
        st = self.simple.get(local)
        if st is None:
            raise KeyError(f"unknown type {type_name}")
        restriction = st.find(f"{XS}restriction")
        if restriction.find(f"{XS}enumeration") is not None:
            return "code"
        pattern = restriction.find(f"{XS}pattern")
        if pattern is not None:
            if pattern.get("value") == r"\d{1,2}-\d{1,2}-\d{4}":
                return "date"
            if pattern.get("value") == r"\d{2,2}/\d{4,4}":
                return "month"
        return self.kind(restriction.get("base"))

    def code_meanings(self, type_name: str) -> dict:
        st = self.simple.get(type_name.split(":")[-1])
        if st is None:
            return {}
        codes = [e.get("value") for e in st.iter(f"{XS}enumeration")]
        doc = st.find(f"{XS}annotation/{XS}documentation")
        if not codes or doc is None or not doc.text:
            return {}
        text = " ".join(doc.text.split())
        text = text.split("Enumerated values and descriptions:", 1)[-1].strip()
        # Split on "<code>: " for the declared codes only, so commas inside a
        # description do not cut it short.
        alternatives = "|".join(re.escape(c) for c in sorted(codes, key=len, reverse=True))
        parts = re.split(rf"(?:^|,\s*)({alternatives}):\s", text)
        meanings = {}
        for code, desc in zip(parts[1::2], parts[2::2], strict=False):
            meanings[code] = desc.strip().rstrip(",").strip()
        return meanings


def _walk(type_name, table, complex_types, resolver, tables):
    """Collect a complex type's leaf elements; an element of complex type becomes a child table."""
    columns = tables.setdefault(table, [])
    for el in complex_types[type_name].iter(f"{XS}element"):
        name, typ = el.get("name"), el.get("type")
        if typ in complex_types:
            _walk(typ, name, complex_types, resolver, tables)
            continue
        kind = KIND_OVERRIDES.get(name) or resolver.kind(typ)
        multi = el.get("maxOccurs") == "unbounded"
        meanings = resolver.code_meanings(typ) if kind == "code" else {}
        columns.append((name, snake_case(name), kind, multi, meanings))


def build(xsd_dir: Path):
    common = [etree.parse(str(xsd_dir / f)) for f in COMMON_FILES]
    out = {}
    for key, (filename, curated) in SCHEMA_FILES.items():
        doc = etree.parse(str(xsd_dir / filename))
        namespace = doc.getroot().get("targetNamespace")
        resolver = TypeResolver(common + [doc])
        complex_types = {ct.get("name"): ct for ct in doc.iter(f"{XS}complexType") if ct.get("name")}
        tables = {}

        _walk("ASSET_TYPE", "assets", complex_types, resolver, tables)
        for table, columns in tables.items():
            names = [c[1] for c in columns]
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                raise SystemExit(f"{key}.{table}: duplicate columns {dupes}")
        out[key] = (namespace, curated, tables)
    return out


def render(schemas) -> str:
    lines = [
        '"""ABS-EE asset data column specs, generated from SEC\'s ABS XML schemas.',
        "",
        "DO NOT EDIT. Regenerate with scripts/abs/generate_absee_schemas.py.",
        "",
        f"Source: EDGAR ABS XML Technical Specification {SPEC_VERSION}",
        "(https://www.sec.gov/info/edgar/specifications/absxml-1.8_d.zip).",
        "",
        "Each table maps an XML tag to (column, kind, multi):",
        "  kind  -- str, code, int, decimal, date (MM-DD-YYYY), month (MM/YYYY), bool",
        "  multi -- the tag may repeat within one asset (maxOccurs=unbounded)",
        "",
        "The curated schemas' column names and kinds are a versioned public contract",
        "(CONTRACT_VERSION). Renaming or retyping one is a breaking change.",
        '"""',
        "",
        f'SPEC_VERSION = "{SPEC_VERSION}"',
        f'CONTRACT_VERSION = "{CONTRACT_VERSION}"',
        "",
        "NAMESPACE_PREFIX = \"http://www.sec.gov/edgar/document/absee/\"",
        "",
        "SCHEMAS = {",
    ]
    meanings_lines = ["CODE_MEANINGS = {"]
    for key, (namespace, curated, tables) in schemas.items():
        lines.append(f"    {key!r}: {{")
        lines.append(f"        'namespace': {namespace!r},")
        lines.append(f"        'curated': {curated!r},")
        lines.append("        'tables': {")
        meanings_lines.append(f"    {key!r}: {{")
        for table, columns in tables.items():
            lines.append(f"            {table!r}: {{")
            for tag, column, kind, multi, meanings in columns:
                lines.append(f"                {tag!r}: ({column!r}, {kind!r}, {multi!r}),")
                if meanings:
                    meanings_lines.append(f"        {column!r}: {meanings!r},")
            lines.append("            },")
        lines.append("        },")
        lines.append("    },")
        meanings_lines.append("    },")
    lines.append("}")
    meanings_lines.append("}")
    return "\n".join(lines + ["", "# schema -> column -> {code: meaning}, from the XSD enumerations' documentation", *meanings_lines]) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(build(Path(sys.argv[1]))))
