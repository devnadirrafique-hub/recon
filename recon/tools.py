"""Hermes tool definitions for the recon plugin.

Each handler takes the args dict Hermes passes, runs the engine, and returns
a JSON string: {"success": true, ...results...} or {"success": false,
"error": ...}. A handler never raises — a failure is an error result, so the
agent can read it and decide what to do next.
"""

import json

from .js_endpoints import find_js_endpoints
from .subdomains import find_subdomains
from .wayback import find_archived_urls


def _str(description):
    return {"type": "string", "description": description}


def _int(description, minimum=None):
    prop = {"type": "integer", "description": description}
    if minimum is not None:
        prop["minimum"] = minimum
    return prop


def _schema(name, description, properties, required):
    params = {"type": "object", "properties": properties, "required": required}
    params["additionalProperties"] = False
    return {"name": name, "description": description, "parameters": params}


SUBDOMAINS_SCHEMA = _schema(
    "recon_subdomains",
    "Find subdomains of a domain from public certificate records (crt.sh). "
    "Read-only: it asks a public index, it never touches the target. Give a bare domain.",
    {"domain": _str("Bare domain to look up, e.g. example.com. Required."),
     "limit": _int("Maximum subdomains to return (1-500). Default 100.", minimum=1)},
    required=["domain"])

WAYBACK_SCHEMA = _schema(
    "recon_wayback_urls",
    "Find archived pages of a domain from the Wayback Machine's public index. "
    "Read-only. Slow — the archive can take up to a minute to answer.",
    {"domain": _str("Bare domain to look up, e.g. example.com. Required."),
     "limit": _int("Maximum archived URLs to return (1-500). Default 100.", minimum=1)},
    required=["domain"])

JS_ENDPOINTS_SCHEMA = _schema(
    "recon_js_endpoints",
    "Download a JavaScript file and list the API paths and absolute URLs quoted inside it. "
    "Read-only. What comes back are candidates to look at — a found path is a lead, not a finding.",
    {"url": _str("Full http(s) URL of the JavaScript file. Required."),
     "limit": _int("Maximum endpoints to return (1-200). Default 100.", minimum=1)},
    required=["url"])


def _ok(tool, source, results, limit):
    capped = results[:limit]
    return json.dumps({"success": True, "tool": tool, "source": source,
                       "count": len(capped), "results": capped})


def _err(message):
    return json.dumps({"success": False, "error": message})


def _limit(args, default, maximum):
    try:
        limit = int(args.get("limit")) if args.get("limit") is not None else default
    except (TypeError, ValueError):
        limit = default
    return max(1, min(maximum, limit))


def handle_subdomains(args, **kwargs):
    try:
        domain = (args or {}).get("domain")
        if not domain:
            return _err("domain is required")
        limit = _limit(args, 100, 500)
        results = find_subdomains(domain)
        return _ok("recon_subdomains", "crt.sh", results, limit)
    except Exception as exc:
        return _err(str(exc))


def handle_wayback(args, **kwargs):
    try:
        domain = (args or {}).get("domain")
        if not domain:
            return _err("domain is required")
        limit = _limit(args, 100, 500)
        results = find_archived_urls(domain)
        return _ok("recon_wayback_urls", "web.archive.org CDX", results, limit)
    except Exception as exc:
        return _err(str(exc))


def handle_js_endpoints(args, **kwargs):
    try:
        url = (args or {}).get("url")
        if not url:
            return _err("url is required")
        limit = _limit(args, 100, 200)
        results = find_js_endpoints(url)
        return _ok("recon_js_endpoints", url, results, limit)
    except Exception as exc:
        return _err(str(exc))
