"""Request helpers shared by the route modules."""
from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import Depends, HTTPException

from . import db


def get_db():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_db)]


def student_row(conn: sqlite3.Connection, sid: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown student")
    return row
