# CLI behavior

Source of truth: `src/argparser.py`, `main.py`, `README.md`,
`tests/test_argparser.py`, `tests/test_main.py`.

## Flags as implemented

| Flag | Effect |
| --- | --- |
| `--tamil` | Required by validation; selects the moviesda provider (confirmed by the project owner: mandatory, no default) |
| `--tamil --dubbed -s MOVIE` | Searches **both** dubbed catalogues (moviesda + isaidub) and merges the results; `-y` is optional |
| `--tamil --latest` | Uses the moviesda home endpoint's latest-release cards |
| `-s`, `--search MOVIE...` | Search words joined with spaces into one query |
| `-y`, `--year YEAR` | Passed to the provider; requires `--search` |
| `-p`, `--play` | Play via `Media.stream()` |
| `-d`, `--download` | Download via `Media.download()` (default when neither is given) |

`-p` and `-d` are in one `argparse` mutually exclusive group. The positional
`list-latest` / `list-dubbed` commands no longer exist.

## Validation in `ArgParse.parse()`

Each condition calls `self.parser.error(...)`:

1. `--tamil` missing → `Choose a source with --tamil (add --dubbed for isaidub).`
2. `--dubbed` and `--latest` together → `--tamil --dubbed --latest is not supported yet.`
3. `--latest` with `--search` or `--year` → `--latest cannot be combined with --search or --year.`
   Confirmed by the project owner: the latest list is very small, so search/year
   are not useful there.
4. `--year` without `--search` → `--year requires --search.`
5. `--dubbed` without `--search` → `--dubbed requires --search.`
6. No `--search` and no `--latest` →
   `Enter --tamil --search MOVIE or --tamil --latest.`

A bare `--tamil --dubbed` is rejected, per the project owner. `--dubbed` requires
a query, while `-y` stays optional beside it.

`--tamil --dubbed -s MOVIE` uses `DubbedProvider`, which queries the moviesda
dubbed catalogue and the isaidub catalogue in parallel and returns one merged
list. Choices are tagged `[Moviesda]` / `[Isaidub]`. Duplicate titles from the
two sources are both kept. If one source raises `ScrapeError`, a warning is
printed and results from the other source are used.

## Examples from `README.md`

```bash
eiga-cli --tamil -s leo -y 2023
eiga-cli --tamil --dubbed -s "Spider Man"
eiga-cli --tamil --dubbed -s virus -y 2026
eiga-cli --tamil -s vikram --play
eiga-cli --tamil --latest
```

## Exit codes from `main.py`

- `0` — `run()` returned success, i.e. `Media.process()` returned `True`.
- `1` — `Media.process()` returned `False`, or a `ScrapeError`/`ValueError`
  reached `main()` and was printed in red.
- `130` — `KeyboardInterrupt`.

`--help` exits during `ArgParse().parse()`, before `Config()` and before any
network request (also noted in `main.py`).

## Planned language flags (not implemented)

`--tamil` is currently the only language/provider flag. The project owner plans
to add others in the same pattern, e.g. `--english` for native English movies
and `--english --dubbed` for English dubbed movies. These are not in the parser
yet; see [providers.md](providers.md).
