# eiga-cli

A terminal app for finding Tamil, Tamil dubbed and English movie releases on supported public sources. It lets you choose a release, quality and server, then open the media URL in a browser, download it with `yt-dlp` or `ffmpeg`, or play it with `vlc`.

## Install

Python 3.10 or newer is required. From a checkout:

```bash
git clone https://github.com/HaimiyaKurotsuki/eiga-cli.git
cd eiga-cli
python -m pip install .
eiga-cli --help
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run eiga-cli --help
```

On Termux, install Python and the native libraries needed to build `lxml` before running `python -m pip install .`:

```bash
pkg install python clang libxml2 libxslt
```

`vlc`, `ffmpeg` and `yt-dlp` are optional external programs. Install the ones you intend to use. Browser handoff is available without them, though some servers require the source's referer or cookies and may not work in a separate browser.

To build a standalone executable on Linux or Windows, run `uv sync` followed by:

```bash
uv run pyinstaller --clean --onefile --name eiga-cli main.py
```

The executable is written to `dist/`. `install.sh` and `install.ps1` build and install it on their respective platforms.

## Use

```bash
eiga-cli --tamil -s leo -y 2023
eiga-cli --tamil --dubbed -s "Spider Man"
eiga-cli --tamil --dubbed -s virus -y 2026
eiga-cli --english -s "Spider Man"
eiga-cli --english -s avatar -y 2009
eiga-cli --tamil -s vikram --play
eiga-cli --tamil --latest
```

`--tamil` selects the moviesda provider. `--english -s MOVIE` searches isaidub's Hollywood-in-English catalogue with the same scraping and resolution flow; it requires `--search` and cannot be combined with `--tamil`, `--dubbed` or `--latest`. `--tamil --dubbed -s MOVIE` searches **both** dubbed catalogues and shows one combined result list: moviesda for Indian-language dubs (malayalam, bollywood, ...) and isaidub for overseas dubs (hollywood, china, japan, ...). Results are tagged `[Moviesda]` or `[Isaidub]`; a title present on both sites appears twice so either source can be chosen. Each catalogue is queried independently — if one fails, the other source's results are still shown with a warning. `--dubbed` requires `--search`. `--tamil --latest` uses the moviesda latest-releases endpoint; `--tamil --dubbed --latest` is not supported yet. The old `list-latest` and `list-dubbed` commands are gone. Searches are case-insensitive. A four-digit year narrows the catalogue; it is required for titles that start with a number or Tamil letter. The English catalogue has no year-based URL, so `--english -y YEAR` keeps only results whose title contains that year. Download is the default action, and `--play` launches `vlc`. Each provider owns discovery and the interactive movie, quality, episode and server selection, and returns only the final media link to the unchanged playback/download layer. Providers collect every episode/file page in a listing before prompting; if some pages fail, they remain available as `Open episode page N` choices instead of disappearing. Resolved media URLs are canonicalized (spaces encoded, existing escapes and query tokens preserved) before being handed to `vlc`, `yt-dlp`, `ffmpeg` or the browser. VLC 3.x only accepts dedicated `http-user-agent` and `http-referrer` HTTP options, passed as per-item `:name=value` arguments; it cannot send a `Cookie` header from the command line, so use the browser or download option for sources that require cookies. `eiga-cli --help` lists all options without accessing the network.

## Source configuration

At startup, the CLI fetches the `domains` from [this repository's config](https://github.com/HaimiyaKurotsuki/eiga-cli/blob/main/config/config.json). The request has an eight-second timeout. A valid response is saved as the last known good domain pair under `~/.cache/eiga-cli/config.json` (or `%LOCALAPPDATA%\eiga-cli\config.json` on Windows); the local config file itself is not rewritten. If the request fails, the saved domains are used; if there is no cache, the local config or built-in defaults are used. The remote file can change the two source domains without a CLI release. Other settings, including download path, remain local. The CLI deliberately uses its built-in repository URL as the update source, so a remote file cannot redirect future configuration requests.

When running from a source checkout, edit `config/config.json` for `download_path`, `headers`, `junk_titles`, or `endpoints`. All catalogue paths are in `endpoints` — including the `{first}` and `{year}` templates — so no source path is hardcoded in the providers. Missing or invalid endpoint values fall back to built-in defaults, so older config files keep working. A standalone executable reads local settings from `~/.config/eiga-cli/config.json` (or `%APPDATA%\eiga-cli\config.json` on Windows) if that file exists. The file may contain the same fields as the repository config. An invalid domain update never replaces the last known good domains.

The source websites may change their HTML or links independently of their domains. A domain update cannot repair those changes; the matching provider under `src/providers/` may then need a code update. Providers check paginated catalogue pages and report source errors rather than showing an empty result for a failed first page. Complete catalogue and episode lists are cached for 15 minutes under the same cache directory. Partial results from failed pages are never cached.

## Verify changes

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py src
```

## Project docs

Internal design notes derived from the source and confirmed by the maintainer are indexed in [docs/README.md](docs/README.md):

- [Architecture](docs/architecture.md) — entry point, module map, request flow
- [CLI behavior](docs/cli.md) — flags, validation, exit codes
- [Providers](docs/providers.md) — provider contract and each source's behavior
- [Configuration](docs/configuration.md) — config fields, refresh, cache paths
- [Verification](docs/verification.md) — tests and build/release workflow
- [Open questions](docs/open-questions.md) — confirmed decisions and remaining items

## Disclaimer

This project does not host media. Use it only for content you are allowed to access and download, and follow the terms of the source websites. Availability depends on those third-party sites.

Licensed under the [MIT License](LICENSE).
