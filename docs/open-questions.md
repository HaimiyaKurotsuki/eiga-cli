# Resolved decisions

This file records what the project owner has confirmed. Every item below is
also reflected in the relevant documents. There are no unresolved questions at
this point.

1. `--tamil` is mandatory; there is no default provider.
2. `--latest` with `--search`/`--year` stays rejected: the latest list is very
   small, so search/year are not useful there.
3. `ResolvedLink(url, title, referer)` is the right provider return value; the
   extra fields are needed by the media layer.
4. The sources still use the paths and selectors in the code, although site
   features may have changed. No live check was done here.
5. The automatic release build works without problems. Whether the
   `RELEASE_TOKEN` secret is configured is still unknown, but no change is
   needed based on the owner's report.
6. `--tamil --dubbed` requires `-s`; bare `--dubbed` is rejected. `-y` stays
   optional beside `-s`.
7. `--dubbed` must search **both** dubbed catalogues, not just isaidub. Moviesda
   holds Indian-language dubs (malayalam, bollywood, ...); isaidub holds overseas
   dubs (hollywood, china, japan, ...). The old `list-dubbed` showed movies from
   both, so combined results restore what disappeared.
8. Combined results go into **one** picker, with `[Moviesda]` / `[Isaidub]` tags.
   Duplicate titles from both sources are kept so either can be chosen.
9. If one source fails to load, show the other source's results with a warning.
10. Keep the configured isaidub domain as-is; the remote GitHub config supplies
    current domains at startup. (The `isaidub.green` in the example was just an
    example.)
11. The shared scraping logic is fine — no per-site strategy is needed now. The
    owner considers the question resolved because the current implementation
    works.
12. VLC/yt-dlp/ffmpeg playback and downloads have been manually tested by the
    owner and work fine. Repository tests only use mocks; no live playback test
    was added here.
13. Docs stay in `docs/` and are linked from `README.md`.
14. More language flags follow the current `--tamil` model. `--english` is
    implemented for native English movies via isaidub's English catalogue, with
    the year used as a title filter. `--english --dubbed` for English dubbed
    movies, and further languages, are still planned and not implemented.
15. The built-in GitHub config URL stays authoritative; the remote file is the
    source of truth for domains and the local file/cache is the fallback. The
    unused `config_url` field was removed from `config/config.json`.
16. All catalogue paths were moved to the `endpoints` object in config, with
    defaults preserved and per-key fallback for older config files. This was
    done without breaking existing behavior; tests cover custom, missing and
    invalid endpoints.
17. `headers` is kept as-is. It is used by the HTTP client and the media layer,
    and the owner accepted the recommendation to leave it in place.
