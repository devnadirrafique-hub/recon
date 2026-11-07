"""Tool-wiring tests: does the plugin register exactly the three recon tools
with Hermes, with the right schemas, and do the handlers behave through the
real wiring (not just the engine)?

Run from the plugin directory with: python -m unittest discover -s tests -v
Uses a fake ctx object that mimics what Hermes hands to register().
No network is touched: handlers are only called with missing args.
"""

import importlib.util
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeCtx:
    """Stands in for the ctx object Hermes passes to register()."""

    def __init__(self):
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "kwargs": kwargs,
        }


def load_plugin_root():
    # Mirror how Hermes loads a directory plugin: __init__.py is imported
    # as a package with __package__ set and the plugin directory as its
    # search path, so the relative imports in __init__.py resolve.
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(plugin_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        "plugin_root", path, submodule_search_locations=[plugin_dir]
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "plugin_root"
    sys.modules["plugin_root"] = module
    spec.loader.exec_module(module)
    return module


class TestToolWiring(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin_root()
        self.ctx = FakeCtx()
        self.plugin.register(self.ctx)

    def test_registers_exactly_the_three_tools(self):
        self.assertEqual(
            set(self.ctx.tools.keys()),
            {"recon_subdomains", "recon_wayback_urls", "recon_js_endpoints"},
        )

    def test_all_tools_share_the_recon_toolset(self):
        for tool in self.ctx.tools.values():
            self.assertEqual(tool["toolset"], "recon")

    def test_schemas_name_the_tool_and_require_the_input(self):
        self.assertEqual(
            self.ctx.tools["recon_subdomains"]["schema"]["name"], "recon_subdomains")
        self.assertEqual(
            self.ctx.tools["recon_subdomains"]["schema"]["parameters"]["required"],
            ["domain"])
        self.assertEqual(
            self.ctx.tools["recon_wayback_urls"]["schema"]["parameters"]["required"],
            ["domain"])
        self.assertEqual(
            self.ctx.tools["recon_js_endpoints"]["schema"]["parameters"]["required"],
            ["url"])

    def test_handlers_return_error_json_not_exceptions_on_missing_args(self):
        for name in ("recon_subdomains", "recon_wayback_urls", "recon_js_endpoints"):
            handler = self.ctx.tools[name]["handler"]
            out = json.loads(handler({}))
            self.assertFalse(out["success"])
            self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
