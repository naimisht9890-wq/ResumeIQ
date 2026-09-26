import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from app.models.schemas import Citation
from app.services.sqlite_database import database_path


KNOWLEDGE_FILE = (
    Path(__file__).resolve().parents[2]
    / "knowledge"
    / "resume_best_practices.json"
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
MAX_QUERY_TOKENS = 64
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def load_knowledge() -> list[dict[str, Any]]:
    """Load and validate the curated rule chunks."""
    if not KNOWLEDGE_FILE.exists():
        raise RuntimeError(
            f"Knowledge file was not found: {KNOWLEDGE_FILE}"
        )

    try:
        with KNOWLEDGE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The resume best-practices knowledge file contains invalid JSON."
        ) from error

    if not isinstance(data, list):
        raise RuntimeError(
            "The resume best-practices knowledge file must contain a list."
        )

    seen_rule_ids: set[str] = set()
    for index, rule in enumerate(data):
        if not isinstance(rule, dict):
            raise RuntimeError(
                f"Knowledge chunk at index {index} must be an object."
            )
        for field in ("rule_id", "category", "text", "source"):
            value = rule.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(
                    f"Knowledge chunk at index {index} has an invalid "
                    f"'{field}' field."
                )
        rule_id = rule["rule_id"]
        if rule_id in seen_rule_ids:
            raise RuntimeError(
                f"Duplicate knowledge rule ID: {rule_id}"
            )
        seen_rule_ids.add(rule_id)

    return data


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")

    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                rule_id UNINDEXED,
                category UNINDEXED,
                source UNINDEXED,
                text,
                tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.commit()
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _sync_index(
    connection: sqlite3.Connection,
    rules: list[dict[str, Any]],
) -> None:
    source_hash = hashlib.sha256(
        KNOWLEDGE_FILE.read_bytes()
    ).hexdigest()
    row = connection.execute(
        """
        SELECT value FROM knowledge_metadata
        WHERE key = 'resume_best_practices_sha256'
        """
    ).fetchone()

    if row is not None and row["value"] == source_hash:
        return

    connection.execute("BEGIN IMMEDIATE")
    connection.execute("DELETE FROM knowledge_fts")
    connection.executemany(
        """
        INSERT INTO knowledge_fts (rule_id, category, source, text)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                rule["rule_id"],
                rule["category"],
                rule["source"],
                rule["text"],
            )
            for rule in rules
        ],
    )
    connection.execute(
        """
        INSERT INTO knowledge_metadata (key, value)
        VALUES ('resume_best_practices_sha256', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (source_hash,),
    )


def _match_expression(query: str) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in TOKEN_PATTERN.findall(query.lower()):
        if token in STOP_WORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) == MAX_QUERY_TOKENS:
            break
    return " OR ".join(f'"{token}"' for token in tokens)


def retrieve_context(
    query: str,
    categories: list[str],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve category-filtered rule chunks using SQLite FTS5 BM25."""
    if top_k < 1:
        raise ValueError("top_k must be at least one.")
    normalized_categories = list(dict.fromkeys(
        category.strip() for category in categories if category.strip()
    ))
    if not normalized_categories:
        return []

    rules = load_knowledge()
    match = _match_expression(query)
    placeholders = ", ".join("?" for _ in normalized_categories)

    with _connection() as connection:
        _sync_index(connection, rules)

        if match:
            rows = connection.execute(
                f"""
                SELECT rule_id, category, source, text, bm25(knowledge_fts) AS rank
                FROM knowledge_fts
                WHERE knowledge_fts MATCH ?
                  AND category IN ({placeholders})
                ORDER BY rank ASC, rule_id ASC
                LIMIT ?
                """,
                (match, *normalized_categories, top_k),
            ).fetchall()
        else:
            rows = []

        if not rows:
            rows = connection.execute(
                f"""
                SELECT rule_id, category, source, text, 0.0 AS rank
                FROM knowledge_fts
                WHERE category IN ({placeholders})
                ORDER BY rule_id ASC
                LIMIT ?
                """,
                (*normalized_categories, top_k),
            ).fetchall()

    return [
        {
            "rule_id": row["rule_id"],
            "category": row["category"],
            "source": row["source"],
            "text": row["text"],
            "retrieval_method": "sqlite_fts5_bm25",
            "rank": float(row["rank"]),
        }
        for row in rows
    ]


def citations_for_context(
    rules: list[dict[str, Any]],
    note_prefix: str = "",
) -> list[Citation]:
    return [
        Citation(
            rule_id=rule["rule_id"],
            source=rule["source"],
            note=(
                f"{note_prefix}"
                f"Retrieved for {rule['category']} context using "
                "SQLite FTS5 BM25."
            ),
        )
        for rule in rules
    ]


def retrieve_rule(category: str) -> dict[str, Any]:
    """Return the highest-ranked curated rule for a category."""
    rules = retrieve_context("", [category], top_k=1)
    if not rules:
        raise ValueError(
            f"No best-practice rule exists for category: {category}"
        )
    return rules[0]
