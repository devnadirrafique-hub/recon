"""Engine tests for the recon plugin: parsing, validation, error paths.

Run from the plugin directory with: python -m unittest discover -s tests -v
The HTTP layer is mocked — no network is touched.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recon import js_endpoints, subdomains, wayback
from recon.http import ReconError
from recon.tools import handle_js_endpoints, handle_subdomains, handle_wayback


CRT_PAYLOAD = json.dumps([
    {"name_value": "example.com\nwww.example.com", "common_name": "example.com"},
    {"name_value": "*.api.example.com\napi.example.com", "common_name": "*.api.example.com"},
    {"name_value": "mail.example.com", "common_name": "mail.example.com"},
    {"name_value": "api.example.com", "common_name": "api.example.com"},
    {"name_value": "other.com", "common_name": "other.com"},
])

CDX_PAYLOAD = json.dumps([
    ["original"],
    ["https://example.com/"],
    ["https://example.com/about"],
    ["https://example.com/about"],
])

JS_SAMPLE = """
const API = "/api/v1/users";
fetch("/api/v1/items?page=2").then(r => r.json());
axios.get('https://api.example.com/v1/search?q=x');
const label = "hello world";
const root = "/";
const spaced = "/api/has space";
"""

# Minified-code shapes that broke the first extractor: an empty string
# shifts quote pairing, an escaped quote must not end a string, and single
# quotes are strings too. Only the real paths survive.
JS_TRICKY = (
    'const a = ""; const b = "/api/empty-test"; '
    'const c = "say \\"hi\\""; const d = \'/api/single\'; '
    'const e = Et.protocol+"//";'
)


class TestSubdomains(unittest.TestCase):
    def test_parse_names_strips_wildcards_dedupes_and_filters(self):
        names = subdomains.parse_names(CRT_PAYLOAD, "example.com")
        self.assertEqual(names, ["api.example.com", "mail.example.com", "www.example.com"])

    def test_parse_names_rejects_non_json(self):
        with self.assertRaises(ReconError):
            subdomains.parse_names("not json", "example.com")

    def test_parse_names_rejects_wrong_shape(self):
        with self.assertRaises(ReconError):
            subdomains.parse_names(json.dumps({"error": "no"}), "example.com")

    def test_validate_domain_accepts_bare_domain(self):
        self.assertEqual(subdomains.validate_domain("Example.COM"), "example.com")

    def test_validate_domain_rejects_scheme_path_and_text(self):
        for bad in ("https://example.com", "example.com/path", "not a domain", "", "example..com"):
            with self.assertRaises(ReconError, msg=bad):
                subdomains.validate_domain(bad)

    @patch("recon.subdomains.fetch_text", return_value=CRT_PAYLOAD)
    def test_find_subdomains_uses_crtsh(self, fetch):
        names = subdomains.find_subdomains("example.com")
        self.assertEqual(names, ["api.example.com", "mail.example.com", "www.example.com"])
        called_url = fetch.call_args[0][0]
        self.assertIn("crt.sh", called_url)
        self.assertIn("example.com", called_url)

    @patch("recon.subdomains.fetch_text", side_effect=ReconError("boom"))
    def test_find_subdomains_wraps_fetch_failure(self, fetch):
        with self.assertRaises(ReconError) as ctx:
            subdomains.find_subdomains("example.com")
        self.assertIn("crt.sh", str(ctx.exception))


class TestWayback(unittest.TestCase):
    def test_parse_urls_skips_header_and_dedupes(self):
        self.assertEqual(wayback.parse_urls(CDX_PAYLOAD),
                         ["https://example.com/", "https://example.com/about"])

    def test_parse_urls_empty_means_no_captures(self):
        self.assertEqual(wayback.parse_urls("[]"), [])

    def test_parse_urls_header_only_means_no_captures(self):
        self.assertEqual(wayback.parse_urls(json.dumps([["original"]])), [])

    def test_parse_urls_rejects_non_json(self):
        with self.assertRaises(ReconError):
            wayback.parse_urls("not json")

    @patch("recon.wayback.fetch_text", return_value=CDX_PAYLOAD)
    def test_find_archived_urls_uses_cdx(self, fetch):
        urls = wayback.find_archived_urls("example.com")
        self.assertEqual(urls, ["https://example.com/", "https://example.com/about"])
        called_url = fetch.call_args[0][0]
        self.assertIn("web.archive.org", called_url)
        self.assertIn("output=json", called_url)
        # No server-side collapse: it is slow enough to time out on a large
        # domain, so dedupe happens client-side instead.
        self.assertNotIn("collapse", called_url)

    @patch("recon.wayback.fetch_text", side_effect=ReconError("boom"))
    def test_find_archived_urls_wraps_fetch_failure(self, fetch):
        with self.assertRaises(ReconError) as ctx:
            wayback.find_archived_urls("example.com")
        self.assertIn("archive", str(ctx.exception))


class TestJsEndpoints(unittest.TestCase):
    def test_extract_endpoints_finds_paths_and_urls(self):
        found = js_endpoints.extract_endpoints(JS_SAMPLE)
        self.assertEqual(found, [
            "/api/v1/items?page=2",
            "/api/v1/users",
            "https://api.example.com/v1/search?q=x",
        ])

    def test_extract_endpoints_survives_empty_and_escaped_strings(self):
        found = js_endpoints.extract_endpoints(JS_TRICKY)
        self.assertEqual(found, ["/api/empty-test", "/api/single"])

    def test_validate_js_url_accepts_http(self):
        self.assertEqual(
            js_endpoints.validate_js_url("https://cdn.example.com/app.js"),
            "https://cdn.example.com/app.js")

    def test_validate_js_url_rejects_non_http(self):
        for bad in ("ftp://example.com/x.js", "example.com/x.js", "", "javascript:alert(1)"):
            with self.assertRaises(ReconError, msg=bad):
                js_endpoints.validate_js_url(bad)

    @patch("recon.js_endpoints.fetch_text", return_value=JS_SAMPLE)
    def test_find_js_endpoints_downloads_and_extracts(self, fetch):
        found = js_endpoints.find_js_endpoints("https://cdn.example.com/app.js")
        self.assertEqual(found, [
            "/api/v1/items?page=2",
            "/api/v1/users",
            "https://api.example.com/v1/search?q=x",
        ])


class TestHandlers(unittest.TestCase):
    @patch("recon.tools.find_subdomains", return_value=["a.example.com", "b.example.com"])
    def test_subdomains_handler_returns_success_json(self, find):
        out = json.loads(handle_subdomains({"domain": "example.com"}))
        self.assertTrue(out["success"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["source"], "crt.sh")

    def test_subdomains_handler_requires_domain(self):
        out = json.loads(handle_subdomains({}))
        self.assertFalse(out["success"])
        self.assertIn("domain", out["error"])

    @patch("recon.tools.find_subdomains", return_value=["a.example.com", "b.example.com", "c.example.com"])
    def test_subdomains_handler_respects_limit(self, find):
        out = json.loads(handle_subdomains({"domain": "example.com", "limit": 1}))
        self.assertEqual(out["count"], 1)

    @patch("recon.tools.find_subdomains", side_effect=ReconError("crt.sh did not answer"))
    def test_subdomains_handler_never_raises(self, find):
        out = json.loads(handle_subdomains({"domain": "example.com"}))
        self.assertFalse(out["success"])
        self.assertIn("crt.sh", out["error"])

    @patch("recon.tools.find_archived_urls", return_value=["https://example.com/"])
    def test_wayback_handler_returns_success_json(self, find):
        out = json.loads(handle_wayback({"domain": "example.com"}))
        self.assertTrue(out["success"])
        self.assertEqual(out["results"], ["https://example.com/"])

    @patch("recon.tools.find_js_endpoints", return_value=["/api/x"])
    def test_js_handler_returns_success_json(self, find):
        out = json.loads(handle_js_endpoints({"url": "https://cdn.example.com/app.js"}))
        self.assertTrue(out["success"])
        self.assertEqual(out["results"], ["/api/x"])


if __name__ == "__main__":
    unittest.main()
