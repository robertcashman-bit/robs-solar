"""Unit tests for concurrency-safe schema init helpers."""

from __future__ import annotations

from app.db.session import _is_retryable_schema_error


def test_retryable_schema_errors_detected() -> None:
    assert _is_retryable_schema_error(
        Exception("asyncpg.exceptions.DeadlockDetectedError: deadlock detected")
    )
    assert _is_retryable_schema_error(
        Exception(
            'UniqueViolationError: duplicate key value violates unique constraint '
            '"pg_type_typname_nsp_index"'
        )
    )
    assert _is_retryable_schema_error(Exception("relation already exists"))
    assert not _is_retryable_schema_error(Exception("password authentication failed"))
