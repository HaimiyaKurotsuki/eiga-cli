# Task: Change to Provider-Based Architecture
- **Status:** DONE
- **Created:** 2026-11-27

## Objective
Move from a generic scraping architecture to an organized, provider-based architecture.
The main goal of this change is to extend the project beyond Tamil to support more sources and providers.

## Steps
1. Understand how the current `moviesda` and `isaidub` scrapers work.
2. Identify patterns in how both share common utilities, code, and logic.
3. Create the following directories for provider-specific code:
   - `src/providers/`
   - `src/providers/moviesda/`
   - `src/providers/isaidub/`
4. Design each provider to accept the required inputs and return only the resolved downloadable URL.
5. Analyze whether both providers require the same inputs or different ones, and build the provider interfaces accordingly.
6. Keep all downstream logic (everything after obtaining the final URL) unchanged.

## CLI Flags
The CLI flags need to be updated for the new architecture because they act as the primary controller for selecting the correct provider.

### Unchanged Common Flags
These common flags do not need to be modified:
```text
-s, --search
-y, --year
-p, --play
-d, --download
```

### New flags

```
--tamil: Target the moviesda provider.
--tamil --dubbed: Target the isaidub provider (combines the previous `list-dubbed` command—which hit a specific endpoint—into a single `--dubbed` flag instead of using separate commands).
--tamil --latest: Target the specific moviesda endpoint for latest releases.
--tamil --dubbed --latest: Not supported yet. Planned for a future release—create a separate task for this.
```
### Removed / Refactored Flags
list-latest and list-dubbed are removed and refactored into the new flag structure.

### Important Design Consideration 
Earlier, I noted that each provider should take an input and return only the final resolved URL. However, users rarely provide an exact query that yields a single movie. 
Instead:The user provides a general query.The tool finds a list of movies matching that query.The user selects a movie $\rightarrow$ selects a quality/server/intermediate option (depending on the page) $\rightarrow$ gets the final URL.

Plan the provider architecture to handle this multi-step interactive resolution flow.