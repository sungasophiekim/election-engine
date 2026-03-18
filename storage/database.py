"""
Election Engine — History Database
SQLite 기반 이력 저장소. 이슈 추이, 상대 동향, 유권자 분석 이력을 보관합니다.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Default DB location
# ---------------------------------------------------------------------------
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_DB_PATH = str(_DEFAULT_DB_DIR / "election_engine.db")

# ---------------------------------------------------------------------------
# SQL — table definitions
# ---------------------------------------------------------------------------
_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS issue_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    keyword         TEXT NOT NULL,
    score           REAL NOT NULL,
    crisis_level    TEXT NOT NULL,
    mention_count   INTEGER,
    negative_ratio  REAL,
    velocity        REAL,
    candidate_linked BOOLEAN,
    portal_trending BOOLEAN,
    tv_reported     BOOLEAN,
    halflife_hours  REAL
);

CREATE TABLE IF NOT EXISTS opponent_signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opponent_name       TEXT NOT NULL,
    recent_mentions     INTEGER,
    message_shift       TEXT,
    attack_prob         REAL,
    recommended_action  TEXT
);

CREATE TABLE IF NOT EXISTS voter_priorities (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    region            TEXT NOT NULL,
    voter_count       INTEGER,
    swing_index       REAL,
    priority_score    REAL,
    local_issue_heat  REAL
);

CREATE TABLE IF NOT EXISTS polls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    poll_date       TEXT NOT NULL,
    pollster        TEXT NOT NULL,
    sample_size     INTEGER,
    margin_of_error REAL,
    our_support     REAL NOT NULL,
    opponent_json   TEXT,
    undecided       REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_briefs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    crisis_level         TEXT,
    top_issues_json      TEXT,
    actions_json         TEXT,
    opponent_alerts_json TEXT
);
"""


class ElectionDB:
    """SQLite 기반 선거 엔진 이력 저장소."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        """Initialize DB and create tables if not exist."""
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript(_CREATE_TABLES)
        self._conn.commit()

    # context-manager support
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_issue_scores(self, scores: list, signals: list = None):
        """Save issue scores (and optionally the raw signals).

        *scores* — list of ``IssueScore`` dataclass instances.
        *signals* — optional list of ``IssueSignal`` instances. When
        provided, matching signal fields (mention_count, velocity, etc.)
        are merged into the stored row by keyword.
        """
        signal_map: dict = {}
        if signals:
            for sig in signals:
                signal_map[sig.keyword] = sig

        rows = []
        for sc in scores:
            sig = signal_map.get(sc.keyword)
            rows.append((
                sc.keyword,
                sc.score,
                sc.level.name if hasattr(sc.level, "name") else str(sc.level),
                sig.mention_count if sig else None,
                sig.negative_ratio if sig else None,
                sig.velocity if sig else None,
                sig.candidate_linked if sig else None,
                sig.portal_trending if sig else None,
                sig.tv_reported if sig else None,
                sc.estimated_halflife_hours,
            ))

        self._conn.executemany(
            """
            INSERT INTO issue_scores
                (keyword, score, crisis_level, mention_count, negative_ratio,
                 velocity, candidate_linked, portal_trending, tv_reported,
                 halflife_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def save_opponent_signals(self, signals: list):
        """Save opponent analysis results.

        *signals* — list of ``OpponentSignal`` dataclass instances.
        """
        rows = [
            (
                s.opponent_name,
                s.recent_mentions,
                s.message_shift,
                s.attack_prob_72h,
                s.recommended_action,
            )
            for s in signals
        ]
        self._conn.executemany(
            """
            INSERT INTO opponent_signals
                (opponent_name, recent_mentions, message_shift,
                 attack_prob, recommended_action)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def save_voter_priorities(self, segments: list):
        """Save voter priority snapshots.

        *segments* — list of ``VoterSegment`` dataclass instances.
        """
        rows = [
            (
                seg.region,
                seg.voter_count,
                seg.swing_index,
                seg.priority_score,
                seg.local_issue_heat,
            )
            for seg in segments
        ]
        self._conn.executemany(
            """
            INSERT INTO voter_priorities
                (region, voter_count, swing_index, priority_score,
                 local_issue_heat)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()

    def save_daily_brief(self, brief):
        """Save a strategic brief summary.

        *brief* — a ``StrategicBrief`` dataclass instance.
        """
        top_issues = [
            {"keyword": iss.keyword, "score": iss.score, "level": iss.level.name}
            for iss in brief.top_issues
        ]

        self._conn.execute(
            """
            INSERT INTO daily_briefs
                (crisis_level, top_issues_json, actions_json,
                 opponent_alerts_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                brief.crisis_level.name if hasattr(brief.crisis_level, "name") else str(brief.crisis_level),
                json.dumps(top_issues, ensure_ascii=False),
                json.dumps(brief.response_actions, ensure_ascii=False),
                json.dumps(brief.opponent_alerts, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_issue_trend(self, keyword: str, days: int = 7) -> list[dict]:
        """Get score history for a keyword over *days* days."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT recorded_at, score, crisis_level, mention_count,
                   negative_ratio, velocity, halflife_hours
            FROM issue_scores
            WHERE keyword = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            """,
            (keyword, since),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_opponent_trend(self, opponent_name: str, days: int = 7) -> list[dict]:
        """Get attack probability trend for an opponent over *days* days."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT recorded_at, recent_mentions, message_shift,
                   attack_prob, recommended_action
            FROM opponent_signals
            WHERE opponent_name = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            """,
            (opponent_name, since),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_scores(self) -> list[dict]:
        """Get most recent issue scores (latest record per keyword)."""
        rows = self._conn.execute(
            """
            SELECT s.keyword, s.score, s.crisis_level, s.mention_count,
                   s.negative_ratio, s.velocity, s.halflife_hours,
                   s.recorded_at
            FROM issue_scores s
            INNER JOIN (
                SELECT keyword, MAX(recorded_at) AS max_at
                FROM issue_scores
                GROUP BY keyword
            ) latest ON s.keyword = latest.keyword
                     AND s.recorded_at = latest.max_at
            ORDER BY s.score DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_score_comparison(self, keyword: str) -> dict:
        """Compare today's score vs yesterday vs 7 days ago.

        Returns::

            {
                "current":   <float | None>,
                "yesterday": <float | None>,
                "week_ago":  <float | None>,
                "trend":     "up" | "down" | "stable",
            }
        """
        now = datetime.now()

        def _latest_score_near(target_dt: datetime, window_hours: int = 12) -> Optional[float]:
            lo = (target_dt - timedelta(hours=window_hours)).isoformat()
            hi = (target_dt + timedelta(hours=window_hours)).isoformat()
            row = self._conn.execute(
                """
                SELECT score FROM issue_scores
                WHERE keyword = ? AND recorded_at BETWEEN ? AND ?
                ORDER BY recorded_at DESC LIMIT 1
                """,
                (keyword, lo, hi),
            ).fetchone()
            return row["score"] if row else None

        current = _latest_score_near(now)
        yesterday = _latest_score_near(now - timedelta(days=1))
        week_ago = _latest_score_near(now - timedelta(days=7))

        # Determine trend
        if current is not None and yesterday is not None:
            diff = current - yesterday
            if diff > 2:
                trend = "up"
            elif diff < -2:
                trend = "down"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "current": current,
            "yesterday": yesterday,
            "week_ago": week_ago,
            "trend": trend,
        }

    # ------------------------------------------------------------------
    # Poll methods
    # ------------------------------------------------------------------

    def save_poll(self, poll_date: str, pollster: str, sample_size: int,
                  margin_of_error: float, our_support: float,
                  opponent_support: dict, undecided: float = 0.0):
        """Save a new poll result."""
        self._conn.execute(
            """
            INSERT INTO polls (poll_date, pollster, sample_size, margin_of_error,
                               our_support, opponent_json, undecided)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (poll_date, pollster, sample_size, margin_of_error,
             our_support, json.dumps(opponent_support, ensure_ascii=False), undecided),
        )
        self._conn.commit()

    def get_all_polls(self) -> list[dict]:
        """Get all saved polls ordered by date."""
        rows = self._conn.execute(
            "SELECT * FROM polls ORDER BY poll_date ASC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["opponent_support"] = json.loads(d.pop("opponent_json", "{}"))
            result.append(d)
        return result

    def delete_poll(self, poll_id: int):
        """Delete a poll by ID."""
        self._conn.execute("DELETE FROM polls WHERE id = ?", (poll_id,))
        self._conn.commit()

    def get_region_trend(self, region: str, days: int = 7) -> list[dict]:
        """Get priority score trend for a region over *days* days."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT recorded_at, voter_count, swing_index,
                   priority_score, local_issue_heat
            FROM voter_priorities
            WHERE region = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            """,
            (region, since),
        ).fetchall()
        return [dict(r) for r in rows]
