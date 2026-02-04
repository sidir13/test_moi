---
name: list-audio-analyses
description: Retrieve stored transcription or background-sound entries from DuckDB to review prior results.
---

# List Audio Analyses

## Instructions
1. When the user wants to review previously saved analyses, collect any filter details:
   - `analysis_type`: `"transcription"` or `"background_sound"`.
   - `source_path_contains`: substring to match paths (e.g., `hamon` or `background_sounds`).
   - `limit`: number of rows to return (default 10, keep it small for readability).
2. Call the `list_analysis_results` tool with the filters.
3. Summarize the returned rows, including `id`, `analysis_type`, `title`, `source_path`, whether it is partial, and notable metadata/tags.
4. If no results match, clearly state that and suggest refining the filters.

## Example
```
[Call list_analysis_results with analysis_type="transcription", source_path_contains="Gilles", limit=3]
```
Then describe each entry’s id, created_at, and a short context summary so the user can choose which one to inspect next.
