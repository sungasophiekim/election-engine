-- =====================================================================
-- Election Engine V2 — Dashboard-Grade Storage Schema
-- =====================================================================
-- 기존 6테이블 → 11테이블 확장
-- 핵심 변경: canonical issue 기반 정규화, 시계열 표준화, 설명 객체 저장
-- =====================================================================

-- ─── 1. CANONICAL ISSUES (정규화된 이슈 마스터) ─────────────────────
-- keyword 폭발을 정규화한 canonical issue 단위
CREATE TABLE IF NOT EXISTS canonical_issues (
    issue_id          TEXT PRIMARY KEY,
    canonical_name    TEXT NOT NULL,
    aliases_json      TEXT,              -- ["김경수 강남", "김경수 강남 발언", ...]
    issue_type        TEXT,              -- candidate_scandal | policy | opponent_attack | regional | general
    target_side       TEXT,              -- ours | theirs | neutral | both
    candidate_linked  BOOLEAN DEFAULT 0,
    region            TEXT,
    entities_json     TEXT,              -- ["김경수", "강남"]
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 2. ISSUE METRICS (시계열 이슈 메트릭) ─────────────────────────
-- 6h 단위 time-series bucket으로 표준화
CREATE TABLE IF NOT EXISTS issue_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id              TEXT NOT NULL,
    ts_bucket             TIMESTAMP NOT NULL,     -- 6시간 단위 bucket (00:00, 06:00, 12:00, 18:00)

    -- 뉴스
    raw_mentions          INTEGER DEFAULT 0,       -- 원본 기사 수
    deduped_story_count   INTEGER DEFAULT 0,       -- 중복 제거 스토리 수

    -- 속도/이상치
    velocity_6h           REAL DEFAULT 0,
    velocity_24h          REAL DEFAULT 0,
    surprise_score        REAL DEFAULT 0,          -- 0~100
    z_score               REAL DEFAULT 0,
    is_anomaly            BOOLEAN DEFAULT 0,

    -- 검색/소셜
    search_interest       INTEGER DEFAULT 0,       -- Google Trends 0~100
    youtube_video_count   INTEGER DEFAULT 0,
    youtube_views         INTEGER DEFAULT 0,
    blog_mentions         INTEGER DEFAULT 0,
    cafe_mentions         INTEGER DEFAULT 0,

    -- 감성 (2단계 결과)
    sentiment_positive    REAL DEFAULT 0,
    sentiment_negative    REAL DEFAULT 0,
    sentiment_target      TEXT,                    -- ours | theirs | neutral
    sentiment_impact      TEXT,                    -- helps_us | hurts_us | neutral
    sentiment_source      TEXT DEFAULT 'lexicon',  -- lexicon | claude | hybrid

    -- 스코어
    score_total           REAL DEFAULT 0,
    score_components_json TEXT,                    -- ScoreExplanation.to_dict()
    crisis_level          TEXT DEFAULT 'NORMAL',

    -- 대응 준비도
    readiness_score       REAL DEFAULT 0,
    readiness_grade       TEXT,

    FOREIGN KEY (issue_id) REFERENCES canonical_issues(issue_id)
);

CREATE INDEX IF NOT EXISTS idx_issue_metrics_ts ON issue_metrics(issue_id, ts_bucket);
CREATE INDEX IF NOT EXISTS idx_issue_metrics_score ON issue_metrics(score_total DESC);

-- ─── 3. ISSUE RESPONSES (이슈 대응 전략) ───────────────────────────
CREATE TABLE IF NOT EXISTS issue_responses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id            TEXT NOT NULL,
    recorded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    stance              TEXT NOT NULL,              -- push | counter | avoid | monitor | pivot
    stance_reason       TEXT,
    owner               TEXT,                       -- 대변인 | 전략팀 | 후보직접 | 여론분석팀
    urgency             TEXT,                       -- 즉시 | 당일 | 48시간 | 모니터링
    golden_time_hours   REAL,

    response_message    TEXT,
    talking_points_json TEXT,                       -- ["포인트1", "포인트2", ...]
    do_not_say_json     TEXT,                       -- ["금기1", "금기2", ...]
    recommended_action  TEXT,

    readiness_score     REAL,
    readiness_detail_json TEXT,                     -- ReadinessScore 상세

    FOREIGN KEY (issue_id) REFERENCES canonical_issues(issue_id)
);

-- ─── 4. STRATEGY DECISIONS (전략 결정 이력) ────────────────────────
CREATE TABLE IF NOT EXISTS strategy_decisions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    campaign_mode           TEXT NOT NULL,           -- CRISIS | ATTACK | DEFENSE | INITIATIVE
    mode_reasoning          TEXT,
    confidence              TEXT,                    -- high | medium | low

    pressure_crisis         REAL DEFAULT 0,
    pressure_polling        REAL DEFAULT 0,
    pressure_momentum       REAL DEFAULT 0,
    pressure_opportunity    REAL DEFAULT 0,
    pressure_breakdown_json TEXT,                    -- {CRISIS: 75, ATTACK: 30, ...}

    top_priority            TEXT,
    key_messages_json       TEXT,
    region_schedule_json    TEXT,
    opponent_actions_json   TEXT,

    risk_level              TEXT,
    risk_factors_json       TEXT,

    win_probability         REAL,
    days_left               INTEGER
);

-- ─── 5. NEWS STORIES (중복 제거된 뉴스 스토리) ─────────────────────
CREATE TABLE IF NOT EXISTS news_stories (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id            TEXT,
    story_cluster_id    INTEGER,
    representative_title TEXT,
    representative_source TEXT,
    media_tier          INTEGER DEFAULT 3,
    article_count       INTEGER DEFAULT 1,          -- 이 스토리에 속한 기사 수
    sources_json        TEXT,                        -- ["연합뉴스", "조선일보", ...]
    first_seen          TIMESTAMP,
    last_seen           TIMESTAMP,

    FOREIGN KEY (issue_id) REFERENCES canonical_issues(issue_id)
);

-- ─── 기존 테이블 유지 (하위 호환) ──────────────────────────────────

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
