"""
Rebuild edgar/xbrl/data/taxonomy_elements.parquet from the FASB element schemas.

A filing imports the us-gaap and srt taxonomies rather than declaring their
elements, so the element catalog parsed from the filing has no balance,
period type or abstract flag for any standard concept (GH #1728). This table
carries those declarations for every us-gaap and srt element published in the
years below.

Source: the FASB element schemas, one per taxonomy and year, e.g.
  https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-2026.xsd
  https://xbrl.fasb.org/srt/2026/elts/srt-2026.xsd
(srt starts in 2018; before that its elements were part of us-gaap).

Columns: prefix, name, type, balance, period_type, abstract,
substitution_group (attribute values copied verbatim from the schema), and
last_year, the newest taxonomy year that declares the element. Rows are keyed
by prefix:name; when several years declare an element, the newest year wins.

It also writes edgar/xbrl/data/taxonomy_enumerations.parquet: one row per
(prefix, name, year) for every year whose schema gives an element
extensible-enumeration attributes, with columns prefix, name, year, domain,
linkrole and head_usable (the enum2:domain, enum2:linkrole and
enum2:headUsable attributes, or their enum 1.0 equivalents, read by namespace
URI and copied verbatim; GH #1255). These are kept per year because they change
between releases: in 2026 FASB moved every us-gaap linkrole from
http://fasb.org/us-gaap/role/eedm/ExtensibleEnumerationLists to
http://fasb.org/srt/role/srt-eedm/ExtensibleEnumerationLists.

Usage:
  EDGAR_IDENTITY="Name email" python scripts/build_taxonomy_elements.py \
      [--years 2011-2026] [--cache-dir DIR]

The schemas are cached in --cache-dir so a rebuild does not refetch them.
The FASB terms (https://xbrl.fasb.org/terms/TaxonomiesTermsConditions.html)
require their Authorized Uses notice to travel with the data; it lives in
edgar/xbrl/data/README.md.
"""
import argparse
import os
import urllib.request
from pathlib import Path

import pandas as pd
from lxml import etree

DATA_DIR = Path(__file__).resolve().parent.parent / "edgar" / "xbrl" / "data"
TARGET = DATA_DIR / "taxonomy_elements.parquet"
ENUM_TARGET = DATA_DIR / "taxonomy_enumerations.parquet"

XS_ELEMENT = "{http://www.w3.org/2001/XMLSchema}element"
XBRLI = "{http://www.xbrl.org/2003/instance}"
SRT_FIRST_YEAR = 2018
# Through 2021 the schemas carry the release date in the file name.
DATED_NAMES_UNTIL = 2021
# Extensible enumerations: 2.0 (enum2:) and 1.0 (enum:), matched by namespace URI.
ENUM_NAMESPACES = ("{http://xbrl.org/2020/extensible-enumerations-2.0}",
                   "{http://xbrl.org/2014/extensible-enumerations}")
COLUMNS = ["prefix", "name", "type", "balance", "period_type", "abstract",
           "substitution_group", "last_year"]
ENUM_COLUMNS = ["prefix", "name", "year", "domain", "linkrole", "head_usable"]


def schema_url(prefix: str, year: int) -> str:
    suffix = f"{year}-01-31" if year <= DATED_NAMES_UNTIL else f"{year}"
    return f"https://xbrl.fasb.org/{prefix}/{year}/elts/{prefix}-{suffix}.xsd"


def fetch(url: str, cache_dir: Path) -> bytes:
    cached = cache_dir / url.rsplit("/", 1)[-1]
    if cached.exists():
        return cached.read_bytes()
    identity = os.environ.get("EDGAR_IDENTITY")
    if not identity:
        raise SystemExit("Set EDGAR_IDENTITY (\"Name email\") to send as the User-Agent.")
    request = urllib.request.Request(url, headers={"User-Agent": identity})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()
    cached.write_bytes(content)
    return content


def enum_attribute(attrs, local_name: str):
    """An extensible-enumeration attribute, from whichever enum namespace carries it."""
    for namespace in ENUM_NAMESPACES:
        value = attrs.get(f"{namespace}{local_name}")
        if value is not None:
            return value
    return None


def schema_rows(prefix: str, year: int, content: bytes):
    """(element row, enumeration row or None) for each declared element."""
    root = etree.fromstring(content)
    for element in root.iter(XS_ELEMENT):
        attrs = element.attrib
        name = attrs.get("name")
        if not name:
            continue
        row = (prefix, name, attrs.get("type"), attrs.get(f"{XBRLI}balance"),
               attrs.get(f"{XBRLI}periodType"), attrs.get("abstract") == "true",
               attrs.get("substitutionGroup"), year)
        enum = (enum_attribute(attrs, "domain"), enum_attribute(attrs, "linkrole"),
                enum_attribute(attrs, "headUsable"))
        yield row, ((prefix, name, year) + enum if any(v is not None for v in enum) else None)


def build(years, cache_dir: Path):
    """The element table (newest declaration per element) and the per-year enumeration table."""
    rows = []
    enum_rows = []
    for year in years:
        for prefix in ("us-gaap", "srt"):
            if prefix == "srt" and year < SRT_FIRST_YEAR:
                continue
            content = fetch(schema_url(prefix, year), cache_dir)
            for row, enum_row in schema_rows(prefix, year, content):
                rows.append(row)
                if enum_row is not None:
                    enum_rows.append(enum_row)
    df = pd.DataFrame(rows, columns=COLUMNS)
    # Newest declaration wins.
    df = (df.sort_values("last_year")
            .drop_duplicates(["prefix", "name"], keep="last")
            .sort_values(["prefix", "name"])
            .reset_index(drop=True))
    for column in ("prefix", "type", "balance", "period_type", "substitution_group"):
        df[column] = df[column].astype("category")
    df["last_year"] = df["last_year"].astype("int16")

    enums = (pd.DataFrame(enum_rows, columns=ENUM_COLUMNS)
               .sort_values(["prefix", "name", "year"])
               .reset_index(drop=True))
    for column in ("prefix", "domain", "linkrole", "head_usable"):
        enums[column] = enums[column].astype("category")
    enums["year"] = enums["year"].astype("int16")
    return df, enums


def parse_years(text: str):
    if "-" in text:
        first, last = (int(part) for part in text.split("-"))
        return list(range(first, last + 1))
    return [int(part) for part in text.split(",")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--years", default="2011-2026")
    parser.add_argument("--cache-dir", default=str(Path.home() / ".cache" / "edgartools" / "fasb-taxonomy"))
    parser.add_argument("--output", default=str(TARGET))
    parser.add_argument("--enum-output", default=str(ENUM_TARGET))
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df, enums = build(parse_years(args.years), cache_dir)
    df.to_parquet(args.output, index=False, compression="zstd")
    enums.to_parquet(args.enum_output, index=False, compression="zstd")

    print(f"elements      : {len(df):,}")
    print(f"with balance  : {int(df['balance'].notna().sum()):,}")
    print(f"abstract      : {int(df['abstract'].sum()):,}")
    print(f"by prefix     : {df['prefix'].value_counts().to_dict()}")
    print(f"size          : {Path(args.output).stat().st_size / 1024:.0f} KB")
    print(f"wrote         : {args.output}")
    print(f"enum rows     : {len(enums):,} ({enums[['prefix', 'name']].drop_duplicates().shape[0]:,} elements, "
          f"years {enums['year'].min()}-{enums['year'].max()})")
    print(f"enum size     : {Path(args.enum_output).stat().st_size / 1024:.0f} KB")
    print(f"wrote         : {args.enum_output}")


if __name__ == "__main__":
    main()
