---
name: save-audio-analysis
description: Persist transcription or background sound analysis payloads into DuckDB for later retrieval.
---

# Save Audio Analysis

## Instructions
1. After completing either the **transcription** or **background sound description** tools, gather:
   - `analysis_type`: `"transcription"` or `"background_sound"`.
   - `source_path`: absolute or repo-relative path to the analyzed file.
   - `title`: concise, human-readable label summarizing the recording (e.g., "Gilles Hamon – entretien 1958" or "Chantier naval – meuleuse A1").
   - `result`: the data returned by the analysis tool (JSON object for transcriptions, string/object for background descriptions).
   - Optional context notes (`context_summary`, `tags`, `metadata`) and whether this is only a partial/sample upload (`is_partial`).
2. Call the `save_analysis_result` tool with those fields to store the payload into the DuckDB database located in `data/audio_analysis.duckdb`.
   - Each entry records the `analysis_type`, file path, JSON payload, metadata, and `is_partial` flag.
3. Include tags like `["fr", "sample"]` to flag early partial uploads while the full archive is still pending.
4. Return the tool result so the user can confirm the DuckDB row ID and file path.

## Examples

**Example 1 – Transcription**
```
[Call save_analysis_result with
 analysis_type="transcription",
 source_path="data/eng/int/Gilles.Hamon-Dessinateur.WAV",
 title="Interview Gilles Hamon – dessinateur",
 result={...chunks...},
 context_summary="Interview with Gilles Hamon (dessinateur) – partial sample",
 tags=["fr", "interview", "sample"],
 is_partial=true]
```

**Example 2 – Background Sound Description**
```
[Call save_analysis_result with
 analysis_type="background_sound",
 source_path="data/eng/meule/AV-1-S-OUT-201-1-A.wav",
 title="Meuleuse industrielle – AV-1-S-OUT-201-1-A",
 result="Bruit de meule industrielle...",
 context_summary="Archive d'ambiance chantier naval",
 tags=["ambiance", "chantier_naval"],
 is_partial=false]
```
