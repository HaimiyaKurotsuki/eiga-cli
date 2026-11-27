# CLI behavior

Source of truth: `src/argparser.py`, `main.py`, `README.md`,
`tests/test_argparser.py`, `tests/test_main.py`.

## Flags as implemented

| Flag | Effect |
| --- | --- |
| `--tamil` | Selects the moviesda provider; required unless `--english` is given (confirmed by the project owner: mandatory, no default) |
| `--english` | Selects the isaidub English movie catalogue; requires `--search` |
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

1. Neither `--tamil` nor `--english` →
   `Choose a source with --tamil or --english (add --dubbed with --tamil for isaidub).`
2. `--english` and `--tamil` together → `--english cannot be combined with --tamil.`
3. `--english` and `--dubbed` together → `--english cannot be combined with --dubbed.`
4. `--english` and `--latest` together → `--english --latest is not supported yet.`
5. `--dubbed` and `--latest` together → `--tamil --dubbed --latest is not supported yet.`
6. `--latest` with `--search` or `--year` → `--latest cannot be combined with --search or --year.`
   Confirmed by the project owner: the latest list is very small, so search/year
   are not useful there.
7. `--year` without `--search` → `--year requires --search.`
8. `--english` without `--search` → `--english requires --search.`
9. `--dubbed` without `--search` → `--dubbed requires --search.`
10. No `--search` and no `--latest` →
    `Enter --tamil --search MOVIE, --english --search MOVIE or --tamil --latest.`

A bare `--tamil --dubbed` is rejected, per the project owner. `--dubbed` requires
a query, while `-y` stays optional beside it. `--english` is an alternative
source flag, not an extra filter: it must be used alone, and `-y` is optional
beside its required query.

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
eiga-cli --english -s "Spider Man"
eiga-cli --english -s avatar -y 2009
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

## Language flags

`--tamil` and `--english` are the implemented language/provider flags. `--english`
searches native English movies in the isaidub catalogue; the project owner also
plans `--english --dubbed` for English dubbed movies and further languages in the
same pattern. `--english --dubbed` is deliberately rejected for now; see
[providers.md](providers.md).
