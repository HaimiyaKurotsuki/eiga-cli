# Task: Add English Movie Support
- **Status:** DONE
- **Created:** 2026-11-27

## Objective
Add support for English movies via the new `--english` CLI flag.

## Steps
1. Understand the project by reading `docs/` and the related source code.
2. Add the new `--english` flag (requires `--search` / `-s`).
3. Configure `--english` to target the `isaidub` provider using the endpoint `https://isaidub.green/movie/hollywood-movies-in-english/`.
4. Reuse the existing `isaidub` pagination and scraping logic.
5. Add the `/movie/hollywood-movies-in-english/` path to `config/config.json` instead of hardcoding it.
6. Handle the `--year` (`-y`) flag appropriately: since this endpoint does not follow a year-based URL pattern like `"isaidub_by_year_dubbed": "/tamil-{year}-dubbed-movies/"`, either use the provided year strictly for filtering/verifying search results or ignore it.
7. Do not support `--dubbed` with `--english` for now—only implement `--english`.
8. Do not create a new provider, since `isaidub` already hosts English movies at this endpoint; reuse the existing scrapers, crawlers, and resolution logic to get the final URL.