"""Evaluation department transactions use the caller's connection and local RLS scope."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

import psycopg

from medops.domain.identity import UserContext
from medops.infrastructure.db.deadline import DeadlineConnection

Row = TypeVar("Row")


def checked_row(row: Row | None) -> Row:
    if row is None:
        raise ValueError("required evaluation query returned no row")
    return row


@contextmanager
def department_transaction(conn: psycopg.Connection, department: str) -> Iterator[psycopg.Connection]:
    with conn.transaction():
        conn.execute("select set_config('medops.dept', %s, true)", (department,))
        yield conn


@contextmanager
def dept_connection(conn: psycopg.Connection, user: UserContext) -> Iterator[DeadlineConnection]:
    with department_transaction(conn, user.dept.value):
        yield DeadlineConnection(conn)
