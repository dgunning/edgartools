"""The certifi bundle httpx verifies with no longer trusts the compromised emSign root.

Bead: edgartools-a9bak (5.62.x backport). Incident: eMudhra emSign, 2026-10-20
(https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576).

On 5.x, httpx verifies against certifi's bundle unless EDGAR_USE_SYSTEM_CERTS is
set, so an installed certifi older than 2026.10.19 kept trusting "emSign ECC Root
CA - G3". pyproject.toml now floors certifi at 2026.10.19.

Ground truth: SHA-256 86:a1:ec:ba:...:6b:be:6b is the "# SHA256 Fingerprint" header
of "emSign ECC Root CA - G3" in certifi 2026.07.22's cacert.pem; certifi 2026.10.19's
120 certificates do not include it.
"""
import hashlib
import re
import ssl
from pathlib import Path

import certifi

G3_SHA256 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)


def test_pyproject_floors_certifi_at_the_fixed_release():
    # A regex, not tomllib: 5.x still supports Python 3.10, where tomllib does not exist.
    assert re.search(r'^\s*"certifi>=2026\.10\.19"', Path("pyproject.toml").read_text(), re.M)


def test_the_installed_bundle_does_not_hold_the_compromised_root():
    pems = PEM.findall(Path(certifi.where()).read_text(encoding="ascii", errors="ignore"))
    fingerprints = {hashlib.sha256(ssl.PEM_cert_to_DER_cert(p)).hexdigest() for p in pems}
    assert len(fingerprints) > 100
    assert G3_SHA256 not in fingerprints
