# Verification and build

Source of truth: `README.md`, `CONTRIBUTING.md`, `pyproject.toml`,
`.github/workflows/release.yml`, `install.sh`, `install.ps1`, `PKGBUILD`,
`tests/*`.

## Local commands (from README / CONTRIBUTING)

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py src
```

With `uv`, the same commands are prefixed with `uv run`, and `uv sync` sets up
the environment. `uv run eiga-cli --help` checks the installed console script
without network access.

At the time these notes were written, the full suite reported 70 tests, all OK,
and `compileall` produced no output.

## Test layout

| File | Covers |
| --- | --- |
| `tests/test_argparser.py` | Language flag combinations, including `--english`, and rejected combinations |
| `tests/test_config.py` | Domain refresh, last-known-good cache, SSL context, local settings, custom/missing/invalid endpoints (including the English catalogue), built-in update URL |
| `tests/test_main.py` | `run()` wiring from `ProviderRequest` through `Media`, including the English flag |
| `tests/test_media.py` | Filename safety, VLC/yt-dlp arguments, header handling |
| `tests/test_providers.py` | All three providers, movie/server selection, pagination, caching, HLS fallback, combined dubbed merge and source tags, English search and year filtering |
| `tests/test_scraper.py` | HTTPS/redirect checks, media detection, link discovery |
| `tests/test_utils.py` | URL canonicalization and rejected URLs |

Async tests use `unittest.IsolatedAsyncioTestCase`. HTTP behavior is simulated
with `httpx.MockTransport` and `unittest.mock.AsyncMock`/`patch`; the suite does
not make live source-site requests.

The project owner reports manually testing VLC/yt-dlp/ffmpeg playback and
downloads with real media and that they work fine. No live playback test was
added to this repository; the automated tests remain mocked.

## Packaging

- `pyproject.toml` requires Python `>=3.10`, declares the runtime dependencies,
  uses setuptools with `py-modules = ["main"]` and package discovery `src*`,
  and registers the `eiga-cli` console script.
- `install.sh`, `install.ps1` and `PKGBUILD` build a one-file binary with
  PyInstaller from `main.py`. `install.sh` requires `uv`; it installs to
  `~/.local/bin`. `install.ps1` requires `uv`; it installs to
  `%LOCALAPPDATA%\Programs\eiga-cli`.
- `eiga-cli.spec` is a PyInstaller spec with no hidden imports or extra data.

## Release workflow (`.github/workflows/release.yml`)

- Triggers on pushes to `main`/`master` (ignoring config-only changes) and on
  `workflow_dispatch`. Bot commits and `[skip ci]` commits do not trigger a run.
- The `version` job bumps the patch version by default, or major/minor when the
  commit message contains `[major]`/`[minor]`. It updates `pyproject.toml`,
  `src/config.py` (the User-Agent version) and `PKGBUILD`, commits the bump,
  and creates or verifies a tag.
- The `build` job produces four one-file binaries: `linux-x86_64`,
  `linux-aarch64`, `windows-x86_64` and `termux-aarch64`. Linux builds run in
  manylinux_2_28 shared CPython images; the Termux build compiles the
  PyInstaller bootloader with Termux clang and runs on a native aarch64 runner
  (no QEMU emulation, which made it ~14x slower).
- The `release` job publishes a GitHub release with the four artifacts.
- The workflow comments describe the `RELEASE_TOKEN` secret for cases where
  `GITHUB_TOKEN` lacks workflow scope. The project owner reports that the
  automatic release build works without problems; whether that secret is
  configured is not visible in the repository files.
