import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

PARQUET_PATH = Path("data/audio_analysis/audio_analysis.parquet")


def _ensure_dataset_dir() -> None:
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)


def save_analysis_result(
    analysis_type: str,
    source_path: str,
    result: Any,
    title: Optional[str] = None,
    context_summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    is_partial: bool = True,
) -> Dict[str, Any]:
    """Persist an analysis result into a parquet dataset."""

    if analysis_type not in {"transcription", "background_sound"}:
        raise ValueError("analysis_type must be either 'transcription' or 'background_sound'")

    _ensure_dataset_dir()

    entry_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    record = {
        "id": entry_id,
        "analysis_type": analysis_type,
        "source_path": source_path,
        "title": title,
        "result_json": json.dumps(result, ensure_ascii=False),
        "context_summary": context_summary,
        "tags_json": json.dumps(tags or [], ensure_ascii=False),
        "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
        "is_partial": bool(is_partial),
        "created_at": created_at,
    }

    df = pd.DataFrame([record])
    target_path = str(PARQUET_PATH.resolve())
    conn = duckdb.connect()
    conn.register("analysis_row", df)
    conn.execute(
        "COPY analysis_row TO ? (FORMAT PARQUET, APPEND TRUE)",
        [target_path],
    )
    conn.unregister("analysis_row")

    return {
        "status": "stored",
        "analysis_type": analysis_type,
        "id": entry_id,
        "dataset": str(PARQUET_PATH),
    }


def fetch_analysis_results(
    analysis_type: Optional[str] = None,
    source_path_contains: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Retrieve entries from the parquet dataset with optional filters."""

    if limit <= 0:
        raise ValueError("limit must be positive")

    if not PARQUET_PATH.exists():
        return {"count": 0, "dataset": str(PARQUET_PATH), "entries": []}

    clauses = []
    params: List[Any] = []

    if analysis_type:
        if analysis_type not in {"transcription", "background_sound"}:
            raise ValueError("analysis_type must be either 'transcription' or 'background_sound'")
        clauses.append("analysis_type = ?")
        params.append(analysis_type)

    if source_path_contains:
        clauses.append("source_path ILIKE ?")
        params.append(f"%{source_path_contains}%")

    where_clause = ""
    if clauses:
        where_clause = "WHERE " + " AND ".join(clauses)

    sql = f"""
        SELECT
            id,
            analysis_type,
            source_path,
            title,
            result_json,
            context_summary,
            tags_json,
            metadata_json,
            is_partial,
            created_at
        FROM read_parquet('{PARQUET_PATH.as_posix()}')
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """

    params.append(limit)

    conn = duckdb.connect()
    rows = conn.execute(sql, params).fetchall()

    def _parse_json(value: Optional[str], default: Any) -> Any:
        if value in (None, ""):
            return default
        return json.loads(value)

    entries = []
    for row in rows:
        (
            row_id,
            row_type,
            row_path,
            row_title,
            result_json,
            context_summary,
            tags_json,
            metadata_json,
            is_partial,
            created_at,
        ) = row

        entries.append(
            {
                "id": row_id,
                "analysis_type": row_type,
                "source_path": row_path,
                "title": row_title,
                "result": _parse_json(result_json, {}),
                "context_summary": context_summary,
                "tags": _parse_json(tags_json, []),
                "metadata": _parse_json(metadata_json, {}),
                "is_partial": is_partial,
                "created_at": created_at,
            }
        )

    return {
        "count": len(entries),
        "dataset": str(PARQUET_PATH),
        "entries": entries,
    }
