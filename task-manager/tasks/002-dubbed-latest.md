# Task: Support Dubbed Latest Releases
- **Status:** TODO
- **Created:** 2026-11-27

## Objective
Support the `--tamil --dubbed --latest` flag combination in a future release.

## Steps / Checklist
- [ ] Find the isaidub endpoint that lists latest dubbed releases.
- [ ] Add a `latest` branch to the isaidub provider's `list_movies` method.
- [ ] Allow the combination in `src/argparser.py` and update its validation.
- [ ] Add provider and CLI tests for the new combination.
- [ ] Update `README.md` flag documentation.
