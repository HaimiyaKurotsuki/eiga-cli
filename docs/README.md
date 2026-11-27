# Documentation index

These notes describe **the code that is in this repository**, not planned behavior.
Every factual statement is traceable to a checked-in file; the relevant file is
named in each document. Owner-confirmed intent is labeled as such. Confirmed
decisions and the project owner's answers are collected in
[open-questions.md](open-questions.md).

Scope: this tree has the provider-based CLI described in
`task-manager/tasks/001-change-arci.md` (marked DONE) plus the `--english`
support from `task-manager/tasks/003-add-english-movies.md` (marked DONE).
`pyproject.toml` declares version `0.6.4`.

| Document | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | Entry point, module map, end-to-end request flow, provider boundary |
| [cli.md](cli.md) | Flags, validation rules, exit codes, examples |
| [providers.md](providers.md) | Provider contract, all three providers, resolution steps, implemented and planned language flags |
| [configuration.md](configuration.md) | Config sources, endpoint templates, refresh/load order, cache paths |
| [verification.md](verification.md) | Test layout, commands, build/release workflow |
| [open-questions.md](open-questions.md) | Owner-confirmed decisions (no unresolved items) |

User-facing install/usage instructions remain in `README.md`, and contributor
workflow in `CONTRIBUTING.md`. This directory holds internal design notes.

Convention used here: when code changes, update the matching note in the same
change; do not record intentions as if they were implemented behavior.
