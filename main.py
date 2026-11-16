"""Habit Tracker — starter app for Week 6.

A tiny FastAPI service for habits and daily check-ins. You'll add features on
branches, open PRs, and compare your manual review with an AI reviewer.

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload
Test:
    pytest
"""

import logging
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "habits.db"

logger = logging.getLogger(__name__)

# Strict YYYY-MM-DD with ASCII digits only (\d would also match e.g. Arabic-Indic).
DAY_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

app = FastAPI(title="Habit Tracker")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_db()) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS habits (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS checkins (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                day      TEXT NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits (id)
            )"""
        )
        conn.commit()


init_db()


class HabitIn(BaseModel):
    name: str


class CheckinIn(BaseModel):
    day: str  # ISO date, e.g. "2026-09-22"


@app.post("/habits")
def create_habit(habit: HabitIn):
    with closing(get_db()) as conn:
        cur = conn.execute("INSERT INTO habits (name) VALUES (?)", (habit.name,))
        conn.commit()
        return {"id": cur.lastrowid, "name": habit.name}


@app.get("/habits")
def list_habits():
    with closing(get_db()) as conn:
        rows = conn.execute("SELECT id, name FROM habits ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/habits/{habit_id}/checkin")
def add_checkin(habit_id: int, checkin: CheckinIn):
    with closing(get_db()) as conn:
        habit = conn.execute(
            "SELECT id FROM habits WHERE id = ?", (habit_id,)
        ).fetchone()
        if habit is None:
            raise HTTPException(status_code=404, detail="unknown habit")
        conn.execute(
            "INSERT INTO checkins (habit_id, day) VALUES (?, ?)",
            (habit_id, checkin.day),
        )
        conn.commit()
    return {"habit_id": habit_id, "day": checkin.day}


@app.get("/habits/{habit_id}/checkins")
def list_checkins(habit_id: int):
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT day FROM checkins WHERE habit_id = ? ORDER BY day", (habit_id,)
        ).fetchall()
    return [r["day"] for r in rows]


def get_today() -> date:
    """Current date as a dependency, so tests can override it."""
    return date.today()


def _parse_day(raw: object) -> Optional[date]:
    """Parse a strict YYYY-MM-DD string, or return None.

    The regex runs first because date.fromisoformat accepts more than
    YYYY-MM-DD on Python 3.11+ ("20260314", "2026-W11-5"), so the result would
    depend on the Python version (local 3.9 rejects them, CI 3.12 accepts).
    """
    if not isinstance(raw, str) or not DAY_PATTERN.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:  # right shape, impossible date such as 2026-02-30
        return None


def compute_streak(days: Iterable[str], today: date) -> int:
    """Count consecutive checked-in days ending today (or yesterday).

    - Duplicate check-ins on the same day count once.
    - Future-dated check-ins are ignored.
    - Rows that are not strict ISO dates (YYYY-MM-DD) are skipped and logged,
      e.g. "2026-3-1", "20260314" or "2026-W11-5". Check-in input is not
      validated yet, so such rows can exist in the database.
    - If neither today nor yesterday has a check-in, the streak is 0.
    """
    checked: set[date] = set()
    for raw in days:
        d = _parse_day(raw)
        if d is None:
            logger.warning("streak: skipping check-in with invalid day %r", raw)
            continue
        if d <= today:
            checked.add(d)

    yesterday = today - timedelta(days=1)
    if today in checked:
        cursor = today
    elif yesterday in checked:
        cursor = yesterday
    else:
        return 0

    streak = 0
    while cursor in checked:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@app.get("/habits/{habit_id}/streak")
def get_streak(habit_id: int, today: date = Depends(get_today)):
    with closing(get_db()) as conn:
        habit = conn.execute(
            "SELECT id FROM habits WHERE id = ?", (habit_id,)
        ).fetchone()
        if habit is None:
            raise HTTPException(status_code=404, detail="unknown habit")
        rows = conn.execute(
            "SELECT day FROM checkins WHERE habit_id = ?", (habit_id,)
        ).fetchall()
    days = [r["day"] for r in rows]
    return {"habit_id": habit_id, "streak": compute_streak(days, today)}
