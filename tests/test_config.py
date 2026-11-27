import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import certifi

from src.config import Config, _ssl_context


class ConfigTests(unittest.TestCase):
    def test_refresh_applies_new_domains_before_search_and_caches_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            cache = root / "cache.json"
            local.write_text(json.dumps({
                "domains": {"moviesda": "https://old.example", "isaidub": "https://old-dub.example"},
                "download_path": "~/Movies",
            }))
            remote = {"domains": {"moviesda": "https://new.example", "isaidub": "https://new-dub.example/"}}
            config = Config(local, cache, lambda _: json.dumps(remote).encode())
            self.assertTrue(config.fetch_config())
            self.assertEqual("https://new.example/home.html", config.moviesda_home_endpoint)
            self.assertEqual("https://new-dub.example", config.isaidub)
            self.assertEqual("~/Movies", config.download_path)
            offline = Config(local, cache, lambda _: (_ for _ in ()).throw(OSError("offline")))
            self.assertEqual("https://new.example", offline.moviesda)
            self.assertEqual("https://old.example", json.loads(local.read_text())["domains"]["moviesda"])
            self.assertEqual({"domains"}, set(json.loads(cache.read_text())))

    def test_invalid_update_never_replaces_last_good_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache.json"
            cache.write_text(json.dumps({"domains": {
                "moviesda": "https://good.example", "isaidub": "https://good-dub.example"}}))
            config = Config(root / "missing.json", cache,
                            lambda _: b'{"domains":{"moviesda":"http://bad.example"}}')
            self.assertFalse(config.fetch_config())
            self.assertEqual("https://good.example", config.moviesda)
            self.assertEqual("https://good.example", json.loads(cache.read_text())["domains"]["moviesda"])

    def test_ssl_context_always_loads_bundled_roots_and_then_platform_store(self):
        # Frozen builds may have no usable system CA store; the bundled
        # certifi roots must still be present, while custom local CAs are
        # retained by loading the platform store as well.
        context = mock.MagicMock()
        with mock.patch("src.config.ssl.create_default_context", return_value=context) as create:
            self.assertIs(context, _ssl_context())
            self.assertEqual(certifi.where(), create.call_args.kwargs["cafile"])
            context.load_default_certs.assert_called_once_with()

            context.load_default_certs.side_effect = OSError("no platform store")
            self.assertIs(context, _ssl_context())

    def test_local_settings_work_without_domain_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            local.write_text(json.dumps({"download_path": "~/Movies"}))
            config = Config(local, root / "cache.json")
            self.assertEqual("~/Movies", config.download_path)
            self.assertEqual("https://moviesda.ski", config.moviesda)

    def test_custom_endpoints_are_applied_and_templates_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            local.write_text(json.dumps({"endpoints": {
                "moviesda_home": "/start.html",
                "moviesda_atoz": "/all/",
                "moviesda_by_year": "/year/{year}/",
                "moviesda_by_letter": "/letter/{first}/",
                "dubbed_movies": "/dubbed-all/",
                "isaidub_atoz_dubbed": "/dubbed/{first}/",
                "isaidub_by_letter_dubbed": "/dubbed/letter/{first}",
                "isaidub_by_year_dubbed": "/dubbed/{year}/",
            }}))
            config = Config(local, root / "cache.json")
        self.assertEqual("https://moviesda.ski/start.html", config.moviesda_home_endpoint)
        self.assertEqual("/year/2024/", config.endpoint("moviesda_by_year", year="2024"))
        self.assertEqual("/letter/a/", config.endpoint("moviesda_by_letter", first="a"))
        self.assertEqual("/dubbed/2025/", config.endpoint("isaidub_by_year_dubbed", year="2025"))
        self.assertEqual("/dubbed/letter/a", config.endpoint("isaidub_by_letter_dubbed", first="a"))
        self.assertEqual("/dubbed-all/", config.dubbed_movies_path)

    def test_missing_and_invalid_endpoints_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            local.write_text(json.dumps({"endpoints": {
                "moviesda_atoz": "not-a-path",
                "dubbed_movies": 42,
            }}))
            config = Config(local, root / "cache.json")
        self.assertEqual("/tamil-atoz-movies/", config.moviesda_atoz_path)
        self.assertEqual("/tamil-dubbed-movies/", config.dubbed_movies_path)
        self.assertEqual("/tamil-movies/{first}/", config.moviesda_by_letter_path)
        self.assertEqual("/tamil-atoz-dubbed-movies/{first}",
                         config.isaidub_by_letter_dubbed_path)

    def test_builtin_remote_url_is_used_even_if_local_config_url_differs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "local.json"
            local.write_text(json.dumps({
                "config_url": "https://attacker.example/config.json",
            }))
            requested = []
            config = Config(local, root / "cache.json",
                            lambda url: (requested.append(url), b'{"domains":{}}')[1])
            config.fetch_config()
        self.assertEqual([config.config_url], requested)
        self.assertIn("raw.githubusercontent.com", config.config_url)


if __name__ == "__main__":
    unittest.main()
