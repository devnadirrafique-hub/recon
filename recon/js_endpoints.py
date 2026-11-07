"""Find API endpoints and interesting paths inside a JavaScript file.

The file is downloaded and its quoted strings are scanned for path-like
values ("/api/users") and absolute URLs. What comes back is a list of
candidates to look at — a found path is a lead, not a finding.
"""

import re
from urllib.parse import urlparse

from .http import ReconError, fetch_text

TIMEOUT_SECONDS = 30
MAX_BYTES = 5 * 1024 * 1024
MAX_ENDPOINTS = 200

_PATH_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "._~:/?#[]@!$&'()*+,;=%-"
)
# Quoted strings, with the closing quote matching the opening one and
# backslash escapes honoured. A plain "any quoted text" pattern pairs quotes
# wrong after an empty string ("") in minified code, so the string after it
# gets swallowed into the previous one — the backreference keeps pairing
# aligned, and the escape branch keeps an escaped quote from ending a string.
_QUOTED_RE = re.compile(r"""(["'`])((?:\\.|(?!\1)[^\\\n])*)\1""")


def validate_js_url(url):
    """Return the URL, or raise ReconError if it is not an http(s) URL."""
    if not isinstance(url, str):
        raise ReconError("url must be text")
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ReconError("not an http(s) URL to a JavaScript file")
    return url


def _is_path(value):
    if not value.startswith("/") or value == "/":
        return False
    if " " in value or "\\" in value:
        return False
    if len(value) > 200:
        return False
    # A bare "//" (or slashes alone) is not an endpoint.
    if not re.search(r"[A-Za-z0-9]", value.lstrip("/")):
        return False
    return all(ch in _PATH_CHARS for ch in value)


def _is_url(value):
    if not (value.startswith("http://") or value.startswith("https://")):
        return False
    if " " in value or "\\" in value:
        return False
    return len(value) <= 500


def extract_endpoints(script):
    """Pull path-like strings and absolute URLs out of JavaScript text."""
    found = set()
    for match in _QUOTED_RE.finditer(script):
        value = match.group(2).strip()
        if _is_path(value) or _is_url(value):
            found.add(value)
    return sorted(found)


def find_js_endpoints(url):
    """Download a JavaScript file and return its endpoints (max 200)."""
    url = validate_js_url(url)
    try:
        script = fetch_text(url, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES)
    except ReconError as exc:
        raise ReconError("the JavaScript file could not be downloaded: %s" % exc)
    return extract_endpoints(script)[:MAX_ENDPOINTS]
