import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

DB_PATH = Path("aurum.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # Access columns by name
    return conn


def init_db() -> None:
    """Create required tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mood_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            mood TEXT NOT NULL,
            energy TEXT NOT NULL,
            focus TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            success INTEGER NOT NULL
        );
        """
    )

    conn.commit()
    conn.close()


def insert_mood(mood: str, energy: str, focus: str) -> Dict[str, Any]:
    """Store a mood check-in and return it as a dict."""
    conn = get_connection()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT INTO mood_logs (timestamp, mood, energy, focus)
        VALUES (?, ?, ?, ?);
        """,
        (ts, mood, energy, focus),
    )

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "mood": mood,
        "energy": energy,
        "focus": focus,
    }


def insert_action(action: str, success: bool) -> Dict[str, Any]:
    """Store an action log and return it as a dict."""
    conn = get_connection()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()

    cur.execute(
        """
        INSERT INTO action_logs (timestamp, action, success)
        VALUES (?, ?, ?);
        """,
        (ts, action, int(success)),
    )

    conn.commit()
    conn.close()

    return {
        "timestamp": ts,
        "action": action,
        "success": success,
    }


def get_summary() -> Dict[str, Any]:
    """Return simple counts of stored moods and actions."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM mood_logs;")
    mood_entries = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM action_logs;")
    action_entries = cur.fetchone()["c"]

    conn.close()

    return {
        "mood_entries": mood_entries,
        "action_entries": action_entries,
    }

def get_mood_history(limit: int = 20) -> List[Dict[str, Any]]:
    # Return the most recent mood entries, newest first.
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """ 
        SELECT timestamp, mood, energy, focus
        FROM mood_logs
        ORDER By timestamp DESC
        LIMIT ?;
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()

    # Convert sqlite3.Row objects to plain dicts
    history = []
    for row in rows:
        history.append(
            {
                "timestamp": row["timestamp"],
                "mood": row["mood"],
                "energy": row["energy"],
                "focus": row["focus"],
            }
        )
    
    return history

def get_action_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent action entries, newest first."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT timestamp, action, success
        FROM action_logs
        ORDER BY timestamp DESC
        LIMIT ?;
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append(
            {
                "timestamp": row["timestamp"],
                "action": row["action"],
                "success": bool(row["success"]),
            }
        )

    return history

def get_action_streak() -> Dict[str, Any]:
    """
    Calculate the current streak of days with at least one successful action.
    Streak is counted backwards from today (UTC) as consecutive days.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Get all successful actions ordered from newest to oldest
    cur.execute(
        """
        SELECT timestamp
        FROM action_logs
        WHERE success = 1
        ORDER BY timestamp DESC;
        """
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "streak_days": 0,
            "last_action_date": None,
        }

    # Collect unique dates (in UTC) where successful actions happened
    unique_dates = []
    seen = set()

    for row in rows:
        ts_str = row["timestamp"]
        try:
            dt = datetime.fromisoformat(ts_str)
        except ValueError:
            # If parsing fails for some reason, skip this row
            continue

        d = dt.date()
        if d not in seen:
            seen.add(d)
            unique_dates.append(d)

    if not unique_dates:
        return {
            "streak_days": 0,
            "last_action_date": None,
        }

    # Sort dates from newest to oldest (should already be, but just in case)
    unique_dates.sort(reverse=True)

    today = date.today()
    streak = 0
    expected = today

    for d in unique_dates:
        if d == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif d > expected:
            # Action logged in "future" relative to today (rare) - skip those
            continue
        else:
            # There's a gap; streak ends
            break

    last_action_date = unique_dates[0].isoformat()

    return {
        "streak_days": streak,
        "last_action_date": last_action_date,
    }



def get_latest_mood() -> Dict[str, Any] | None:
    """Return the most recent mood entry or None if no data."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT timestamp, mood, energy, focus
        FROM mood_logs
        ORDER BY timestamp DESC
        LIMIT 1;
        """
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "timestamp": row["timestamp"],
        "mood": row["mood"],
        "energy": row["energy"],
        "focus": row["focus"],
    }


def get_counts() -> Dict[str, int]:
    """Return counts for mood and action logs (same idea as get_summary, but typed)."""
    summary = get_summary()
    return {
        "mood_entries": int(summary["mood_entries"]),
        "action_entries": int(summary["action_entries"]),
    }
