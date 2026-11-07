"""Recon plugin for Hermes Agent.

Registers three read-only recon tools (see recon/tools.py). The engines in
recon/ have no Hermes dependency, so they can be unit-tested without Hermes
installed. This file is only the wiring between Hermes and the engines.
"""

from .recon.tools import (
    JS_ENDPOINTS_SCHEMA,
    SUBDOMAINS_SCHEMA,
    WAYBACK_SCHEMA,
    handle_js_endpoints,
    handle_subdomains,
    handle_wayback,
)

_TOOLS = (
    ("recon_subdomains", "recon", SUBDOMAINS_SCHEMA, handle_subdomains, "🔍"),
    ("recon_wayback_urls", "recon", WAYBACK_SCHEMA, handle_wayback, "🗄️"),
    ("recon_js_endpoints", "recon", JS_ENDPOINTS_SCHEMA, handle_js_endpoints, "🧩"),
)


def register(ctx):
    for name, toolset, schema, handler, emoji in _TOOLS:
        ctx.register_tool(name=name, toolset=toolset, schema=schema,
                          handler=handler, emoji=emoji)
