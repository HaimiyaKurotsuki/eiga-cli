# Configuration

Source of truth: `src/config.py`, `src/cache.py`, `config/config.json`,
`tests/test_config.py`, `src/logger.py`.

## Defaults (`DEFAULT_CONFIG` in `src/config.py`)

| Field | Default |
| --- | --- |
| `domains.moviesda` | `https://moviesda.ski` |
| `domains.isaidub` | `https://isaiidub.com` |
| `download_path` | `~/Downloads/` |
| `endpoints.moviesda_home` | `/home.html` |
| `endpoints.moviesda_atoz` | `/tamil-atoz-movies/` |
| `endpoints.moviesda_by_letter` | `/tamil-movies/{first}/` |
| `endpoints.moviesda_by_year` | `/tamil-{year}-movies/` |
| `endpoints.dubbed_movies` | `/tamil-dubbed-movies/` |
| `endpoints.isaidub_atoz_dubbed` | `/tamil-atoz-dubbed-movies/` |
| `endpoints.isaidub_by_letter_dubbed` | `/tamil-atoz-dubbed-movies/{first}` |
| `endpoints.isaidub_by_year_dubbed` | `/tamil-{year}-dubbed-movies/` |
| `endpoints.isaidub_english_movies` | `/movie/hollywood-movies-in-english/` |
| `headers` | `{"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}` |
| `junk_titles` | `[]` |

## Field purposes (stated by the project owner)

- `domains`: the maintainer keeps the current source domains in the repository
  config; the tool fetches them from GitHub at startup. The remote GitHub file
  is the source of truth for domains, and the local file/cache is the fallback.
- `download_path`: where downloaded movies are saved.
- `endpoints`: all catalogue paths are configurable instead of hardcoded. The
  `{first}` and `{year}` placeholders are filled by `Config.endpoint()`.
  `dubbed_movies` is used by moviesda in `--dubbed` and by isaidub for direct
  no-query callers; the CLI itself requires `-s` with `--dubbed`.
  `isaidub_english_movies` is the English catalogue used by `--english`; it
  has no `{year}` template because that catalogue is not year-based.
- `headers`: the owner does not know why this field was introduced (it came from
  AI-generated configuration). It is kept because the code uses it: it is passed
  to the `httpx` client and to `Media`/VLC/yt-dlp/ffmpeg handoff.
- `junk_titles`: manually collected unnecessary texts that should not appear in
  movie lists. `src/utils.py::is_valid()` filters titles matching these exactly.

`config_url` was removed from `config/config.json`. It was never read by the
code: `Config.__init__()` sets `self.config_url` to the built-in
`REMOTE_CONFIG_URL`. Keeping the URL built in is deliberate — a downloaded
config cannot redirect future updates. `tests/test_config.py` verifies that a
local `config_url` is ignored.

## File locations

- Local config: repository `config/config.json` when the app is not frozen and
  that file exists; otherwise `XDG_CONFIG_HOME/eiga-cli/config.json`, with
  `APPDATA` used instead of `XDG_CONFIG_HOME` on Windows.
- Config cache (last known good domains): `XDG_CACHE_HOME/eiga-cli/config.json`,
  with `LOCALAPPDATA` used instead on Windows.
- Catalogue cache: `config.cache_path.parent / "catalogue"`, i.e.
  `~/.cache/eiga-cli/catalogue` with default paths on Linux.
- Log file: `$XDG_CACHE_HOME/eiga-cli/logs.txt` (see `src/logger.py`; this one
  does not use `LOCALAPPDATA`).

## Load order in `Config.load_config()`

1. Start from `DEFAULT_CONFIG`.
2. Merge local config fields except `domains`. If `domains` is present it is
   validated separately; invalid local domains are logged and ignored.
3. If the config cache exists, its validated `domains` override the domains
   from step 2. Malformed cache files are logged and ignored.
4. `_apply()` derives the public attributes.

`_apply()` sets `moviesda`, `isaidub`, endpoint path attributes for every
`endpoints` key, plus `moviesda_home_endpoint`,
`moviesda_dubbed_movies_endpoint`, `isaidub_english_movies_endpoint`,
`download_path`, `headers` and `junks`.
Header keys/values must be strings without CR/LF; non-conforming entries are
dropped. Each endpoint path must be a string starting with `/` or it falls back
to the default from `DEFAULT_CONFIG` and logs a message. Missing keys in a local
`endpoints` object also fall back to defaults, so older config files keep working.

`Config.endpoint(name, **values)` fills a path template with `.format()`. If a
configured template has unbalanced or unknown placeholders, it is logged and
returned unchanged rather than raising.

## Domain validation

`validate_domain()` accepts only an HTTPS URL with a hostname containing `.`,
no username/password, no query/fragment, path `""` or `/`, and no port other
than 443. It returns `https://<hostname>`.

## Remote refresh (`fetch_config()`)

- URL: `REMOTE_CONFIG_URL` in `src/config.py`, pointing at
  `config/config.json` on the `main` branch of the GitHub repository named in
  that constant. This is the only update URL; no config field can change it.
- `Config._download()` uses an 8-second timeout, reads at most 64,001 bytes,
  rejects a response over 64,000 bytes, and rejects a non-HTTPS final URL.
- `_ssl_context()` loads the bundled `certifi` roots first, then the platform
  store; failure to load the platform store is ignored.
- On success the validated domains are written to the cache via a temporary
  file and atomic replace, then `load_config()` runs again. The **cache file**,
  not the local config file, is what gets rewritten; the local config file is
  left untouched. From the next `load_config()` onward the cached domains win.
- On failure (`OSError`, `ValueError`, `KeyError`, `urllib.error.URLError`),
  any temporary file is removed, the failure is logged, prior domains are kept,
  and the method returns `False`. `main.py` prints a warning on `False`.

The remote file only supplies `domains`; other settings stay local. This is
implemented in `fetch_config()`, which writes only `{"domains": ...}` to the
cache. `tests/test_config.py` verifies that a successful refresh leaves the
local config file unchanged, keeps local `download_path`, and is still used on
the next offline start.
