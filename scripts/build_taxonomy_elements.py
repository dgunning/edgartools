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

XS_ELEMENT = "{http://www.w3.org/2001/XMLSchema}element"
XBRLI = "{http://www.xbrl.org/2003/instance}"
SRT_FIRST_YEAR = 2018
# Through 2021 the schemas carry the release date in the file name.
DATED_NAMES_UNTIL = 2021
COLUMNS = ["prefix", "name", "type", "balance", "period_type", "abstract",
           "substitution_group", "last_year"]


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


def schema_rows(prefix: str, year: int, content: bytes):
    root = etree.fromstring(content)
    for element in root.iter(XS_ELEMENT):
        attrs = element.attrib
        name = attrs.get("name")
        if not name:
            continue
        yield (prefix, name, attrs.get("type"), attrs.get(f"{XBRLI}balance"),
               attrs.get(f"{XBRLI}periodType"), attrs.get("abstract") == "true",
               attrs.get("substitutionGroup"), year)


def build(years, cache_dir: Path) -> pd.DataFrame:
    rows = []
    for year in years:
        for prefix in ("us-gaap", "srt"):
            if prefix == "srt" and year < SRT_FIRST_YEAR:
                continue
            content = fetch(schema_url(prefix, year), cache_dir)
            rows.extend(schema_rows(prefix, year, content))
    df = pd.DataFrame(rows, columns=COLUMNS)
    # Newest declaration wins.
    df = (df.sort_values("last_year")
            .drop_duplicates(["prefix", "name"], keep="last")
            .sort_values(["prefix", "name"])
            .reset_index(drop=True))
    for column in ("prefix", "type", "balance", "period_type", "substitution_group"):
        df[column] = df[column].astype("category")
    df["last_year"] = df["last_year"].astype("int16")
    return df


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
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    df = build(parse_years(args.years), cache_dir)
    df.to_parquet(args.output, index=False, compression="zstd")

    print(f"elements      : {len(df):,}")
    print(f"with balance  : {int(df['balance'].notna().sum()):,}")
    print(f"abstract      : {int(df['abstract'].sum()):,}")
    print(f"by prefix     : {df['prefix'].value_counts().to_dict()}")
    print(f"size          : {Path(args.output).stat().st_size / 1024:.0f} KB")
    print(f"wrote         : {args.output}")


if __name__ == "__main__":
    main()
