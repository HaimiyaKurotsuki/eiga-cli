# Providers

Source of truth: `src/providers/base.py`, `src/providers/moviesda/provider.py`,
`src/providers/isaidub/provider.py`, `src/providers/dubbed/provider.py`,
`src/providers/__init__.py`, `tests/test_providers.py`.

## Contract

`src/providers/base.py` defines:

- `ProviderRequest(query=None, year=None, latest=False)` — the same input shape
  for both providers.
- `ResolvedLink(url, title, referer="")` — the final media URL plus the metadata
  `main.py` needs for the filename and headers.
- `Provider`, an abstract class whose only required method is
  `async list_movies(client, request) -> list[Link]`.
- `Provider.resolve(client, request)`, implemented once in the base class: list
  movies, raise `ValueError("No movies found. Try another title, year or source.")`
  on an empty list, prompt with `choose_link()` using `Provider.label()` for each
  choice name, call `resolve_link()`, and return a `ResolvedLink`.
- `choose_link(message, links, labels=None)` wraps `inquirer.fuzzy()` with
  integer-valued `Choice` objects; the comment in the code says this avoids
  InquirerPy recursively converting `Link` objects. `labels` lets a provider
  show extra text (such as a source tag) without changing the chosen `Link`.
- `Provider.label(link)` defaults to `link.title`; `DubbedProvider` overrides it
  to prefix `[Moviesda]` or `[Isaidub]`.

`get_provider(config, *, dubbed=False)` in `src/providers/__init__.py` returns
`DubbedProvider(config)` when `dubbed` is true, otherwise `MoviesdaProvider(config)`.
`DubbedProvider` owns a `MoviesdaProvider` and an `IsaidubProvider` and delegates
the two catalogue queries to them.

## Shared steps in `Provider`

- `validate_search(query, year)` requires a non-empty normalized query, a
  four-digit `(19|20)\d{2}` year when given, and a year for titles whose first
  normalized character is not an ASCII lowercase letter.
- `catalogue_root(client, home_url, category)` fetches the home page and follows
  an anchor whose path equals `category`; otherwise it uses the fetched page URL.
- `collect(client, start, query, referer)` walks catalogue pages up to 80 visited
  pages, collects `.f`/`.folder` entries, follows pagination from the same host,
  filters titles by the normalized query, and caches only complete listings.
- `_paginated_choices()` walks later pages of one release listing up to 50
  visited pages. `_same_listing()` keeps the walk on the same host and on the
  same path or a numeric/`page/N` suffix of that path. Failed or unvisited pages
  become `Open episode page N` choices.
- `resolve_link(client, initial)` walks up to 25 hops: detects loops, rejects HLS
  pages, canonicalizes a media URL with `canonical_url()`, asks for a
  release/quality/server choice when there is more than one option, and keeps
  backup servers when all choices look like servers/mirrors. `ScrapeError` from
  a server falls back to a backup if one exists.

All three providers use the same `ProviderRequest`; they differ in catalogue
paths and in whether `latest` is supported. All catalogue paths now come from
`config/config.json` via `Config.endpoint()`; the defaults are listed in
[configuration.md](configuration.md). No source path is hardcoded in a provider.

## Moviesda (`--tamil`, `--tamil --latest`)

`list_movies()`:

- `latest=True`: fetch `config.moviesda_home_endpoint` and return
  `scraper.latest(page)`; no query or year is used.
- otherwise: validate the search, find the root via
  `catalogue_root(..., config.moviesda_atoz_path)`, then use
  `config.endpoint("moviesda_by_year", year=...)` when a year is given, or
  `config.endpoint("moviesda_by_letter", first=...)` where `first` is the first
  normalized query character. It calls `collect()` with the query as a title
  filter.

`dubbed_movies()` (used by `DubbedProvider`) validates the search, finds the root
with `catalogue_root(..., config.moviesda_atoz_path)`, then opens
`config.dubbed_movies_path` on that root and runs `collect()` with the query.

## Isaidub (dubbed source used by `--tamil --dubbed`)

`list_movies()`:

- `latest=True`: raises `ValueError("--latest is only supported by the moviesda
  provider.")`. This is also rejected by `ArgParse.parse()`.
- otherwise: find the root via
  `catalogue_root(config.isaidub + "/", config.isaidub_atoz_dubbed_path)`.
- with a query: validate it, then use
  `config.endpoint("isaidub_by_year_dubbed", year=...)` when a year is given, or
  `config.endpoint("isaidub_by_letter_dubbed", first=...)` otherwise.
- without a query: use `config.dubbed_movies_path`. Direct callers can still do
  this, but the CLI rejects `--dubbed` without `--search`.
- In both cases it calls `collect()` with the query (if any).

## Dubbed (`--tamil --dubbed -s MOVIE`)

`src/providers/dubbed/provider.py` defines `DubbedProvider`, which replaces the
old isaidub-only behavior. The project owner reported that the old `list-dubbed`
showed movies from both sites: moviesda covers Indian-language dubs
(malayalam/bollywood etc.), isaidub covers overseas dubs (hollywood/china/japan
etc.). The flag now has to cover both.

`list_movies()`:

- `latest=True`: raises the same "only supported by the moviesda provider" error
  as isaidub; the CLI rejects it earlier.
- otherwise: validates the search once, then calls `moviesda.dubbed_movies()` and
  `isaidub.list_movies()` concurrently with `asyncio.gather(..., return_exceptions=True)`.
- results are combined in order (moviesda first, then isaidub) without deduping,
  so the same title on both sites appears twice.
- each link is wrapped in `TaggedLink(Link)` with a `source` field; `label()`
  renders it as `[Moviesda] Title` or `[Isaidub] Title`. The source tag is only
  for the picker — `resolve()` passes `chosen.title` (without the tag) to the
  media layer, so filenames are unaffected.
- a `ScrapeError` from either source is logged and shown as a yellow warning;
  results from the other source are still returned. Other exceptions are
  re-raised. `self.warnings` collects the warning text for tests.

## Site markup status

The project owner confirms that the sources still use the paths and selectors
the code relies on (`div.latest`, `.f`, `.dlink`, `a.coral`, pagination classes),
but notes that site features may have changed. This documentation was written
from the source and mocked tests, not from a live check of either site.

**Shared scraping logic is an implementation fact, not a verified property of
the two websites.** `MoviesdaProvider` and `IsaidubProvider` both inherit the
same `collect()`/`resolve_link()` flow and both use the same `Scraper` class for
`.f`/`.folder` entries, pagination and `.dlink`/server choices. Each provider
instance constructs its own `Scraper` in `Provider.__init__`, so a future
per-site scraper override can be added without changing the `DubbedProvider`
merge logic. The project owner raised the possibility that the sites differ;
that has not been verified against live pages, and no per-site scraper strategy
exists yet. See [open-questions.md](open-questions.md).

## Adding another source

The current structure is: one package under `src/providers/`, one `Provider`
subclass implementing `list_movies()`, and one branch in `get_provider()` to
select it. `DubbedProvider` is a special case: it is a `Provider` that composes
two other providers instead of scraping a site itself. This is an observation
of how moviesda, isaidub and dubbed are wired, not a published extension API;
no other source is implemented in this tree.

## Planned language flags (not implemented)

The project owner stated the intended direction: more language flags should
follow the current `--tamil` pattern. Examples given:

- `--english` — native English movies.
- `--english --dubbed` — English dubbed movies.
- Further languages would be added the same way as Tamil.

These flags are **not** in `src/argparser.py` and no such providers exist. This
section records owner-stated intent only, not implemented behavior.
