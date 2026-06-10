"""
PostgreSQL-compatible audit store backed by SQLite.

Stores every fraud-detection decision with full evidence and audit trail
for regulatory compliance, replay, and analytics.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from src.models.decision import DecisionResult, RiskLevel

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT    NOT NULL UNIQUE,
    decision        TEXT    NOT NULL,
    confidence      REAL    NOT NULL,
    risk_level      TEXT    NOT NULL,
    composite_score REAL    NOT NULL DEFAULT 0.0,
    reason          TEXT    NOT NULL DEFAULT '',
    reasons         TEXT    NOT NULL DEFAULT '[]',
    evidence        TEXT    NOT NULL DEFAULT '[]',
    processing_time_ms REAL NOT NULL DEFAULT 0.0,
    fast_path       INTEGER NOT NULL DEFAULT 0,
    audit_trail     TEXT    NOT NULL DEFAULT '{}',
    created_at      TEXT    NOT NULL
);
"""

_CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_decisions_decision   ON decisions(decision);",
    "CREATE INDEX IF NOT EXISTS idx_decisions_risk_level  ON decisions(risk_level);",
    "CREATE INDEX IF NOT EXISTS idx_decisions_created_at  ON decisions(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_decisions_txn_id      ON decisions(transaction_id);",
]


class SQLiteAuditStore:
    """Async audit store using SQLite (mirrors PostgreSQL interface)."""

    def __init__(self, db_path: str = "audit.db") -> None:
        """Initialise the store.

        Args:
            db_path: Path to the SQLite database file. Use ``:memory:``
                for a purely in-memory store (tests).
        """
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Open the database and create schema if needed."""
        # Ensure parent directory exists for file-based DBs
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.execute("PRAGMA synchronous=NORMAL;")
        await self._db.execute(_CREATE_TABLE_SQL)
        for idx_sql in _CREATE_INDEX_SQL:
            await self._db.execute(idx_sql)
        await self._db.commit()
        logger.info("AuditStore started (db=%s)", self._db_path)

    async def stop(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
        logger.info("AuditStore stopped.")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def store_decision(self, result: DecisionResult) -> None:
        """Persist a ``DecisionResult`` to the audit store.

        Args:
            result: The final decision result to persist.
        """
        assert self._db is not None, "AuditStore not started"

        audit_trail_json = "{}"
        if result.audit_trail is not None:
            audit_trail_json = result.audit_trail.model_dump_json()

        await self._db.execute(
            """
            INSERT OR REPLACE INTO decisions
                (transaction_id, decision, confidence, risk_level, composite_score,
                 reason, reasons, evidence, processing_time_ms, fast_path,
                 audit_trail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.transaction_id,
                result.decision.value,
                result.confidence,
                result.risk_level.value,
                result.composite_score,
                result.reason,
                json.dumps(result.reasons),
                json.dumps([e for e in result.evidence], default=str),
                result.processing_time_ms,
                1 if result.fast_path else 0,
                audit_trail_json,
                result.timestamp.isoformat(),
            ),
        )
        await self._db.commit()
        logger.debug("Stored decision for txn %s", result.transaction_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_decision(self, transaction_id: str) -> dict[str, Any] | None:
        """Retrieve a single decision by transaction ID.

        Returns:
            A dict representation of the decision row, or ``None``.
        """
        assert self._db is not None, "AuditStore not started"

        cursor = await self._db.execute(
            "SELECT * FROM decisions WHERE transaction_id = ?",
            (transaction_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(cursor.description, row)

    async def query_decisions(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        decision_type: str | None = None,
        risk_level: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query decisions with optional filters.

        Args:
            start_time: Lower bound on ``created_at`` (inclusive).
            end_time: Upper bound on ``created_at`` (inclusive).
            decision_type: Filter by decision value (APPROVE/DECLINE/ESCALATE).
            risk_level: Filter by risk level (LOW/MEDIUM/HIGH/CRITICAL).
            limit: Max rows to return.
            offset: Row offset for pagination.

        Returns:
            List of decision dicts.
        """
        assert self._db is not None, "AuditStore not started"

        clauses: list[str] = []
        params: list[Any] = []

        if start_time is not None:
            clauses.append("created_at >= ?")
            params.append(start_time.isoformat())
        if end_time is not None:
            clauses.append("created_at <= ?")
            params.append(end_time.isoformat())
        if decision_type is not None:
            clauses.append("decision = ?")
            params.append(decision_type.upper())
        if risk_level is not None:
            clauses.append("risk_level = ?")
            params.append(risk_level.upper())

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = (
            f"SELECT * FROM decisions {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        cursor = await self._db.execute(sql, params)
        rows = await cursor.fetchall()
        return [self._row_to_dict(cursor.description, r) for r in rows]

    async def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics from the audit store.

        Returns:
            Dict with counts by decision, risk level, averages, etc.
        """
        assert self._db is not None, "AuditStore not started"

        stats: dict[str, Any] = {}

        # Total count
        cursor = await self._db.execute("SELECT COUNT(*) FROM decisions")
        row = await cursor.fetchone()
        stats["total_decisions"] = row[0] if row else 0

        # Counts by decision
        cursor = await self._db.execute(
            "SELECT decision, COUNT(*) FROM decisions GROUP BY decision"
        )
        stats["by_decision"] = {r[0]: r[1] for r in await cursor.fetchall()}

        # Counts by risk level
        cursor = await self._db.execute(
            "SELECT risk_level, COUNT(*) FROM decisions GROUP BY risk_level"
        )
        stats["by_risk_level"] = {r[0]: r[1] for r in await cursor.fetchall()}

        # Average processing time
        cursor = await self._db.execute(
            "SELECT AVG(processing_time_ms) FROM decisions"
        )
        row = await cursor.fetchone()
        stats["avg_processing_time_ms"] = round(row[0], 2) if row and row[0] else 0.0

        # Fast path rate
        cursor = await self._db.execute(
            "SELECT AVG(fast_path) FROM decisions"
        )
        row = await cursor.fetchone()
        stats["fast_path_rate"] = round(row[0], 4) if row and row[0] else 0.0

        # Average confidence
        cursor = await self._db.execute(
            "SELECT AVG(confidence) FROM decisions"
        )
        row = await cursor.fetchone()
        stats["avg_confidence"] = round(row[0], 4) if row and row[0] else 0.0

        return stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(
        description: Any, row: tuple[Any, ...]
    ) -> dict[str, Any]:
        """Convert a DB row + cursor description into a dict."""
        columns = [col[0] for col in description]
        result: dict[str, Any] = dict(zip(columns, row))
        # Parse JSON fields back
        for json_field in ("reasons", "evidence", "audit_trail"):
            if json_field in result and isinstance(result[json_field], str):
                try:
                    result[json_field] = json.loads(result[json_field])
                except json.JSONDecodeError:
                    pass
        # Convert fast_path int → bool
        if "fast_path" in result:
            result["fast_path"] = bool(result["fast_path"])
        return result
