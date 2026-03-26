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
    undecided       REAL DEFAULT 0,
    source          TEXT DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS nesdc_known (
    ntt_id          TEXT PRIMARY KEY,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type            TEXT NOT NULL,
    keyword         TEXT,
    input_context   TEXT,
    output          TEXT,
    requested_by    TEXT DEFAULT 'dashboard'
);

CREATE TABLE IF NOT EXISTS daily_briefs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    crisis_level         TEXT,
    top_issues_json      TEXT,
    actions_json         TEXT,
    opponent_alerts_json TEXT
);

CREATE TABLE IF NOT EXISTS v5_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_id     TEXT NOT NULL UNIQUE,
    tenant_id       TEXT,
    decision_type   TEXT NOT NULL,
    keyword         TEXT,
    region          TEXT,
    recommended_value TEXT,
    confidence      TEXT,
    reasoning       TEXT,
    context_snapshot TEXT,
    override_value  TEXT,
    override_reason TEXT,
    overridden_by   TEXT,
    was_executed    BOOLEAN DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS v5_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decision_id     TEXT NOT NULL,
    decision_type   TEXT NOT NULL,
    keyword         TEXT,
    region          TEXT,
    recommended_value TEXT,
    actual_outcome  TEXT,
    outcome_grade   TEXT,
    predicted_metric REAL,
    actual_metric   REAL,
    metric_delta    REAL,
    evaluator_note  TEXT,
    FOREIGN KEY (decision_id) REFERENCES v5_decisions(decision_id)
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
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
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
                  opponent_support: dict, undecided: float = 0.0,
                  source: str = "manual"):
        """Save a new poll result."""
        self._conn.execute(
            """
            INSERT INTO polls (poll_date, pollster, sample_size, margin_of_error,
                               our_support, opponent_json, undecided, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (poll_date, pollster, sample_size, margin_of_error,
             our_support, json.dumps(opponent_support, ensure_ascii=False),
             undecided, source),
        )
        self._conn.commit()

    def get_nesdc_known_ids(self) -> set[str]:
        """이미 수집한 nesdc nttId 목록 반환"""
        try:
            rows = self._conn.execute("SELECT ntt_id FROM nesdc_known").fetchall()
            return {r[0] for r in rows}
        except Exception:
            return set()

    def save_nesdc_id(self, ntt_id: str):
        """수집 완료한 nesdc nttId 기록"""
        self._conn.execute(
            "INSERT OR IGNORE INTO nesdc_known (ntt_id) VALUES (?)",
            (ntt_id,),
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

    # ------------------------------------------------------------------
    # AI Analysis methods
    # ------------------------------------------------------------------

    def save_ai_analysis(self, analysis_type: str, keyword: str,
                         input_context: str, output: str,
                         requested_by: str = "dashboard"):
        self._conn.execute(
            "INSERT INTO ai_analyses (type, keyword, input_context, output, requested_by) VALUES (?,?,?,?,?)",
            (analysis_type, keyword, input_context, output, requested_by),
        )
        self._conn.commit()

    def count_ai_today(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM ai_analyses WHERE date(created_at)=date('now')"
        ).fetchone()
        return row["cnt"] if row else 0

    def get_ai_analyses(self, keyword: str = None, limit: int = 10) -> list:
        if keyword:
            rows = self._conn.execute(
                "SELECT * FROM ai_analyses WHERE keyword=? ORDER BY created_at DESC LIMIT ?",
                (keyword, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ai_analyses ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Decision Log methods (v5 learning loop)
    # ------------------------------------------------------------------

    def save_decisions(self, records: list):
        """DecisionRecord 목록을 저장."""
        rows = []
        for r in records:
            d = r.to_dict() if hasattr(r, 'to_dict') else r
            rows.append((
                d.get("decision_id", ""),
                d.get("tenant_id", ""),
                d.get("decision_type", ""),
                d.get("keyword", ""),
                d.get("region", ""),
                d.get("recommended_value", ""),
                d.get("confidence", ""),
                d.get("reasoning", ""),
                json.dumps(d.get("context_snapshot", {}), ensure_ascii=False),
            ))
        self._conn.executemany(
            """INSERT OR IGNORE INTO v5_decisions
               (decision_id, tenant_id, decision_type, keyword, region,
                recommended_value, confidence, reasoning, context_snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    def save_override(self, override):
        """OverrideRecord를 v5_decisions에 반영."""
        d = override.to_dict() if hasattr(override, 'to_dict') else override
        self._conn.execute(
            """UPDATE v5_decisions
               SET override_value=?, override_reason=?, overridden_by=?
               WHERE decision_id=?""",
            (d.get("overridden_value", ""),
             d.get("override_reason", ""),
             d.get("overridden_by", ""),
             d.get("decision_id", "")),
        )
        self._conn.commit()

    def save_execution(self, execution):
        """ExecutionRecord를 v5_decisions에 반영."""
        d = execution.to_dict() if hasattr(execution, 'to_dict') else execution
        self._conn.execute(
            "UPDATE v5_decisions SET was_executed=? WHERE decision_id=?",
            (d.get("was_executed", False), d.get("decision_id", "")),
        )
        self._conn.commit()

    def save_outcomes(self, outcomes: list):
        """OutcomeRecord 목록을 저장."""
        rows = []
        for o in outcomes:
            d = o if isinstance(o, dict) else (o.to_dict() if hasattr(o, 'to_dict') else o.__dict__)
            rows.append((
                d.get("decision_id", ""),
                d.get("decision_type", ""),
                d.get("keyword", ""),
                d.get("region", ""),
                d.get("recommended_value", ""),
                d.get("actual_outcome", ""),
                d.get("outcome_grade", ""),
                d.get("predicted_metric", 0),
                d.get("actual_metric", 0),
                d.get("metric_delta", 0),
                d.get("evaluator_note", ""),
            ))
        self._conn.executemany(
            """INSERT INTO v5_outcomes
               (decision_id, decision_type, keyword, region,
                recommended_value, actual_outcome, outcome_grade,
                predicted_metric, actual_metric, metric_delta, evaluator_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()

    def get_pending_decisions(self, hours_ago: int = 48, tenant_id: str = None) -> list[dict]:
        """평가 대기 중인 결정 목록 조회 (v5_outcomes에 아직 없는 것)."""
        query = """
            SELECT d.* FROM v5_decisions d
            LEFT JOIN v5_outcomes o ON d.decision_id = o.decision_id
            WHERE o.decision_id IS NULL
              AND d.created_at <= datetime('now', ?)
        """
        params = [f"-{hours_ago} hours"]
        if tenant_id:
            query += " AND d.tenant_id = ?"
            params.append(tenant_id)
        query += " ORDER BY d.created_at ASC"
        rows = self._conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("context_snapshot"):
                d["context_snapshot"] = json.loads(d["context_snapshot"])
            result.append(d)
        return result

    def get_accuracy_summary(self, tenant_id: str = None, days: int = 7) -> list[dict]:
        """결정 유형별 정확도 요약."""
        since = f"-{days} days"
        query = """
            SELECT decision_type,
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome_grade='correct' THEN 1 ELSE 0 END) as correct,
                   SUM(CASE WHEN outcome_grade='partially_correct' THEN 1 ELSE 0 END) as partial,
                   SUM(CASE WHEN outcome_grade='wrong' THEN 1 ELSE 0 END) as wrong,
                   SUM(CASE WHEN outcome_grade='inconclusive' THEN 1 ELSE 0 END) as inconclusive
            FROM v5_outcomes
            WHERE evaluated_at >= datetime('now', ?)
        """
        params = [since]
        if tenant_id:
            query += """
                AND decision_id IN (
                    SELECT decision_id FROM v5_decisions WHERE tenant_id = ?
                )
            """
            params.append(tenant_id)
        query += " GROUP BY decision_type"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_override_stats(self, tenant_id: str = None, days: int = 7) -> dict:
        """Override 빈도 통계 — 어떤 유형의 추천을 사람이 가장 많이 바꾸는가."""
        since = f"-{days} days"
        query = """
            SELECT decision_type,
                   COUNT(*) as total,
                   SUM(CASE WHEN override_value IS NOT NULL THEN 1 ELSE 0 END) as overridden
            FROM v5_decisions
            WHERE created_at >= datetime('now', ?)
        """
        params = [since]
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        query += " GROUP BY decision_type"
        rows = self._conn.execute(query, params).fetchall()
        return {r["decision_type"]: {"total": r["total"], "overridden": r["overridden"]} for r in rows}
