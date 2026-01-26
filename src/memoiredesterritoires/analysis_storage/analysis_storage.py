import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

DB_PATH = Path(os.getenv("DUCKDB_PATH", "data/audio_analysis.duckdb"))
TABLE_NAME = "audio_analysis"
SEQUENCE_NAME = f"{TABLE_NAME}_id_seq"

_connection: Optional[duckdb.DuckDBPyConnection] = None


def _get_connection() -> duckdb.DuckDBPyConnection:
    """Return a cached DuckDB connection, creating the schema if needed."""
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = duckdb.connect(str(DB_PATH))
        _initialize_schema(_connection)
    return _connection


def _initialize_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {SEQUENCE_NAME};")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id BIGINT PRIMARY KEY,
            analysis_type TEXT NOT NULL,
            source_path TEXT NOT NULL,
            result_json JSON NOT NULL,
            context_summary TEXT,
            tags_json JSON,
            metadata_json JSON,
            is_partial BOOLEAN,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def save_analysis_result(
    analysis_type: str,
    source_path: str,
    result: Any,
    context_summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    is_partial: bool = True,
) -> Dict[str, Any]:
    """
    Persist an analysis result (transcription or background sound description) into DuckDB.
    """
    if analysis_type not in {"transcription", "background_sound"}:
        raise ValueError("analysis_type must be either 'transcription' or 'background_sound'")

    conn = _get_connection()
    created_at = datetime.now(timezone.utc)

    result_json = json.dumps(result, ensure_ascii=False)
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    row = conn.execute(
        f"""
        INSERT INTO {TABLE_NAME} (
            id,
            analysis_type,
            source_path,
            result_json,
            context_summary,
            tags_json,
            metadata_json,
            is_partial,
            created_at
        )
        VALUES (
            nextval('{SEQUENCE_NAME}'),
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        RETURNING id
        """,
        (
            analysis_type,
            source_path,
            result_json,
            context_summary,
            tags_json,
            metadata_json,
            bool(is_partial),
            created_at,
        ),
    )

    inserted_id = row.fetchone()[0]
    return {
        "status": "stored",
        "analysis_type": analysis_type,
        "id": inserted_id,
        "db_path": str(DB_PATH),
        "table": TABLE_NAME,
    }


def fetch_analysis_results(
    analysis_type: Optional[str] = None,
    source_path_contains: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Retrieve stored analysis rows with optional filters."""
    if limit <= 0:
        raise ValueError("limit must be positive")

    conn = _get_connection()
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

    where_clause = " AND ".join(clauses)
    if where_clause:
        where_clause = "WHERE " + where_clause

    query = f"""
        SELECT
            id,
            analysis_type,
            source_path,
            result_json,
            context_summary,
            tags_json,
            metadata_json,
            is_partial,
            created_at
        FROM {TABLE_NAME}
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """

    params.append(limit)
    rows = conn.execute(query, params).fetchall()

    def parse_json(value: Optional[str], default: Any) -> Any:
        if value in (None, ""):
            return default
        return json.loads(value)

    entries = []
    for row in rows:
        (
            row_id,
            row_type,
            row_path,
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
                "result": parse_json(result_json, {}),
                "context_summary": context_summary,
                "tags": parse_json(tags_json, []),
                "metadata": parse_json(metadata_json, {}),
                "is_partial": is_partial,
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            }
        )

    return {
        "count": len(entries),
        "db_path": str(DB_PATH),
        "entries": entries,
    }
