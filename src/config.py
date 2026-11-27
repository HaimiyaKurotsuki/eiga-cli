"""Validated configuration with a last-known-good remote domain cache."""

import json
import os
import ssl
import tempfile
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import certifi

from src.logger import Logger


REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/HaimiyaKurotsuki/eiga-cli/refs/heads/main/config/config.json"
DEFAULT_CONFIG = {
    "domains": {"moviesda": "https://moviesda.ski", "isaidub": "https://isaiidub.com"},
    "download_path": "~/Downloads/",
    "endpoints": {
        "moviesda_home": "/home.html",
        "moviesda_atoz": "/tamil-atoz-movies/",
        "moviesda_by_letter": "/tamil-movies/{first}/",
        "moviesda_by_year": "/tamil-{year}-movies/",
        "dubbed_movies": "/tamil-dubbed-movies/",
        "isaidub_atoz_dubbed": "/tamil-atoz-dubbed-movies/",
        "isaidub_by_letter_dubbed": "/tamil-atoz-dubbed-movies/{first}",
        "isaidub_by_year_dubbed": "/tamil-{year}-dubbed-movies/",
    },
    "headers": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
    "junk_titles": [],
}


class ConfigError(ValueError):
    pass


def _ssl_context() -> ssl.SSLContext:
    """Return a TLS context that works on any of the shipped platforms.

    Frozen binaries bundle the build container's OpenSSL, whose compiled-in CA
    paths (e.g. /etc/pki/tls/certs on manylinux) often do not exist on the
    target machine. Always load the certifi roots bundled by PyInstaller, then
    add the platform store as well so locally installed/custom CAs keep working
    on Windows, Termux and Linux. A missing store is harmless.
    """
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        context.load_default_certs()
    except (OSError, ValueError, ssl.SSLError):
        pass
    return context


def validate_domain(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigError("Source domain must be a string")
    url = urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.port not in (None, 443) or url.path not in ("", "/")
            or url.query or url.fragment or "." not in url.hostname):
        raise ConfigError(f"Invalid HTTPS source domain: {value}")
    return f"https://{url.hostname}"


def validate_domains(data: object) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ConfigError("Config must contain a domains object")
    try:
        return {name: validate_domain(data[name]) for name in ("moviesda", "isaidub")}
    except KeyError as exc:
        raise ConfigError(f"Missing source domain: {exc.args[0]}") from exc


class Config:
    def __init__(self, config_path: Path | None = None, cache_path: Path | None = None,
                 fetcher=None):
        config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        if os.name == "nt":
            config_root = Path(os.environ.get("APPDATA", config_root))
        repo_path = Path(__file__).resolve().parents[1] / "config/config.json"
        default_path = (repo_path if not getattr(sys, "frozen", False) and repo_path.exists()
                        else config_root / "eiga-cli/config.json")
        self.config_path = config_path or default_path
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        if os.name == "nt":
            cache_root = Path(os.environ.get("LOCALAPPDATA", cache_root))
        self.cache_path = cache_path or cache_root / "eiga-cli/config.json"
        self.fetcher = fetcher or self._download
        self.config_url = REMOTE_CONFIG_URL
        self.load_config()

    @staticmethod
    def _download(url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "eiga-cli/0.6.5"})
        with urllib.request.urlopen(request, timeout=8, context=_ssl_context()) as response:
            if urlsplit(response.url).scheme != "https":
                raise ConfigError("Remote config redirected to an insecure URL")
            data = response.read(64_001)
        if len(data) > 64_000:
            raise ConfigError("Remote config is too large")
        return data

    def load_config(self) -> None:
        config = dict(DEFAULT_CONFIG)
        try:
            local = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(local, dict):
                raise ConfigError("Local config must be an object")
            config.update({key: value for key, value in local.items() if key != "domains"})
            if "domains" in local:
                try:
                    config["domains"] = validate_domains(local["domains"])
                except ConfigError as exc:
                    Logger.log(f"Ignoring invalid local domains: {exc}")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            Logger.log(f"Ignoring invalid local config: {exc}")
            config = dict(DEFAULT_CONFIG)

        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            config["domains"] = validate_domains(cached.get("domains"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            Logger.log(f"Ignoring invalid cached config: {exc}")

        self._apply(config)

    def _apply(self, config: dict) -> None:
        self.domains = validate_domains(config["domains"])
        self.moviesda = self.domains["moviesda"]
        self.isaidub = self.domains["isaidub"]
        defaults = DEFAULT_CONFIG["endpoints"]
        endpoints = config.get("endpoints") if isinstance(config.get("endpoints"), dict) else {}

        def path(name: str) -> str:
            value = endpoints.get(name, defaults[name])
            if not isinstance(value, str) or not value.startswith("/"):
                Logger.log(f"Ignoring invalid {name} endpoint; using default")
                value = defaults[name]
            return value

        self.moviesda_home_path = path("moviesda_home")
        self.moviesda_atoz_path = path("moviesda_atoz")
        self.moviesda_by_letter_path = path("moviesda_by_letter")
        self.moviesda_by_year_path = path("moviesda_by_year")
        self.dubbed_movies_path = path("dubbed_movies")
        self.isaidub_atoz_dubbed_path = path("isaidub_atoz_dubbed")
        self.isaidub_by_letter_dubbed_path = path("isaidub_by_letter_dubbed")
        self.isaidub_by_year_dubbed_path = path("isaidub_by_year_dubbed")
        self.moviesda_home_endpoint = self.moviesda + self.moviesda_home_path
        self.moviesda_dubbed_movies_endpoint = self.moviesda + self.dubbed_movies_path
        download_path = config.get("download_path")
        self.download_path = download_path if isinstance(download_path, str) and download_path else "~/Downloads/"
        headers = config.get("headers")
        self.headers = ({str(key): value for key, value in headers.items()
                         if isinstance(key, str) and isinstance(value, str)
                         and "\r" not in key + value and "\n" not in key + value}
                        if isinstance(headers, dict) else {})
        junk_titles = config.get("junk_titles")
        self.junks = [title for title in junk_titles if isinstance(title, str)] if isinstance(junk_titles, list) else []

    def endpoint(self, name: str, **values: str) -> str:
        """Fill a configured path template, e.g. `year=` or `first=`."""
        template = getattr(self, f"{name}_path")
        try:
            return template.format(**values)
        except (KeyError, ValueError, IndexError) as exc:
            Logger.log(f"Invalid {name} endpoint template {template!r}: {exc}")
            return template

    def fetch_config(self) -> bool:
        """Refresh domains from the trusted repository, retaining prior values on failure."""
        temporary = None
        try:
            remote = json.loads(self.fetcher(self.config_url))
            domains = validate_domains(remote["domains"])
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.cache_path.parent,
                                             delete=False) as stream:
                json.dump({"domains": domains}, stream)
                temporary = Path(stream.name)
            temporary.replace(self.cache_path)
            self.load_config()
            return True
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            Logger.log(f"Config refresh failed; using last known domains: {exc}")
            return False
