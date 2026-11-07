"""Find subdomains from public certificate records (crt.sh).

crt.sh publishes every certificate it has seen, as JSON, with no key and no
login. A subdomain that ever got a certificate shows up here.
"""

import json
import re

from .http import ReconError, fetch_text

CRT_SH_URL = "https://crt.sh/?q=%25.{domain}&output=json"
# crt.sh is a slow public service; 30 s was not enough for a large domain
# (2026-11-08). 60 s gives it a fair chance without hanging the agent.
TIMEOUT_SECONDS = 60
MAX_BYTES = 2 * 1024 * 1024
MAX_NAMES = 500

_DOMAIN_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def validate_domain(domain):
    """Return the domain lowercased, or raise ReconError if not a bare domain."""
    if not isinstance(domain, str):
        raise ReconError("domain must be text")
    domain = domain.strip().lower()
    if len(domain) > 253 or not _DOMAIN_RE.match(domain):
        raise ReconError("not a bare domain (give just the domain, e.g. example.com)")
    return domain


def parse_names(payload, domain):
    """Pull subdomain names out of a crt.sh JSON payload.

    Each entry has a name_value field with one name per line; wildcard
    entries start with "*.". Only names under the queried domain are kept.
    """
    try:
        entries = json.loads(payload)
    except (ValueError, TypeError):
        raise ReconError("crt.sh answered with data that is not JSON")
    if not isinstance(entries, list):
        raise ReconError("crt.sh answered with an unexpected shape")
    names = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("name_value") or ""
        for line in raw.splitlines():
            name = line.strip().lower()
            if name.startswith("*."):
                name = name[2:]
            if not name or name == domain:
                continue
            if name.endswith("." + domain):
                names.add(name)
    return sorted(names)


def find_subdomains(domain):
    """Return the sorted, deduplicated subdomains of domain (max 500)."""
    domain = validate_domain(domain)
    url = CRT_SH_URL.format(domain=domain)
    try:
        payload = fetch_text(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
    except ReconError as exc:
        raise ReconError("crt.sh did not answer: %s" % exc)
    return parse_names(payload, domain)[:MAX_NAMES]
