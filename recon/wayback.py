"""Find archived pages from the Wayback Machine's public CDX index.

The CDX API lists every URL the archive captured for a domain. The first
row of a JSON answer is always the field names; the data starts after it.
CDX is slow, so this tool waits up to 60 seconds for an answer.
"""

import json

from .http import ReconError, fetch_text
from .subdomains import validate_domain

CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url={domain}/*&output=json&fl=original&limit=5000"
)
# No server-side collapse: a prefix query collapsed by urlkey is slow — it
# timed out at 60 s on a large domain (2026-11-08). Dedupe happens
# client-side instead (parse_urls), over up to 5000 raw rows.
TIMEOUT_SECONDS = 60
MAX_BYTES = 2 * 1024 * 1024
MAX_URLS = 500

_CDX_FIELDS = {
    "urlkey", "timestamp", "original", "mimetype",
    "statuscode", "digest", "length",
}


def parse_urls(payload):
    """Pull archived URLs out of a CDX JSON payload (header row skipped)."""
    try:
        rows = json.loads(payload)
    except (ValueError, TypeError):
        raise ReconError("the archive answered with data that is not JSON")
    if not isinstance(rows, list):
        raise ReconError("the archive answered with an unexpected shape")
    if not rows:
        return []
    # The first row is the field names when the answer has a header.
    start = 0
    first = rows[0]
    if isinstance(first, list) and first and first[0] in _CDX_FIELDS:
        start = 1
    urls = set()
    for row in rows[start:]:
        if isinstance(row, list) and row and isinstance(row[0], str):
            url = row[0].strip()
            if url:
                urls.add(url)
    return sorted(urls)


def find_archived_urls(domain):
    """Return the sorted, deduplicated archived URLs of domain (max 500)."""
    domain = validate_domain(domain)
    url = CDX_URL.format(domain=domain)
    try:
        payload = fetch_text(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
    except ReconError as exc:
        raise ReconError("the archive did not answer: %s" % exc)
    return parse_urls(payload)[:MAX_URLS]
