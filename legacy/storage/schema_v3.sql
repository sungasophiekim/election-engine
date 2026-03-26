-- =====================================================================
-- Election Strategy OS V3 — Schema Extension
-- =====================================================================
-- V2 테이블 유지 + 6개 신규 테이블 추가
-- Layer 2: Internal Input Engine
-- Layer 3: Strategic Memory Engine
-- Layer 5: Human Decision Layer
-- =====================================================================

-- ─── 1. INTERNAL SIGNALS (내부 시그널) ──────────────────────────────
-- 텔레그램 /report, /order, /hypo, /block, /narrative, /override 입력
CREATE TABLE IF NOT EXISTS internal_signals (
    id                TEXT PRIMARY KEY,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source            TEXT NOT NULL DEFAULT 'strategy_director',
    signal_type       TEXT NOT NULL,          -- field_report | order | hypothesis | block | narrative | override
    issue_id          TEXT,                   -- canonical_issues 연결 (nullable)
    region            TEXT,
    content           TEXT NOT NULL,
    confidence        TEXT DEFAULT 'medium',  -- high | medium | low
    priority          TEXT DEFAULT 'normal',  -- urgent | normal | low
    visibility        TEXT DEFAULT 'director_only',
    expiry            TIMESTAMP,
    metadata_json     TEXT DEFAULT '{}',      -- signal_type별 추가 필드
    status            TEXT DEFAULT 'active',  -- active | expired | superseded
    telegram_message_id INTEGER,
    telegram_chat_id  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_signals_type_status ON internal_signals(signal_type, status);
CREATE INDEX IF NOT EXISTS idx_signals_issue ON internal_signals(issue_id);
CREATE INDEX IF NOT EXISTS idx_signals_created ON internal_signals(created_at DESC);

-- ─── 2. STRATEGIC MEMORY (전략 메모리) ─────────────────────────────
-- candidate, campaign, director, field, decision 5개 타입
CREATE TABLE IF NOT EXISTS strategic_memory (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_type       TEXT NOT NULL,          -- candidate | campaign | director | field | decision
    memory_key        TEXT NOT NULL,          -- e.g., "speaking_strengths", "override_habits"
    value_json        TEXT NOT NULL,
    source            TEXT DEFAULT 'system',  -- system | director_input | auto_learned
    confidence        REAL DEFAULT 0.5,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at        TIMESTAMP,
    UNIQUE(memory_type, memory_key)
);

CREATE INDEX IF NOT EXISTS idx_memory_type ON strategic_memory(memory_type);

-- ─── 3. STRATEGY PROPOSALS (전략 제안 = Execution Queue) ───────────
-- AI가 생성, 인간이 승인/수정/거부
CREATE TABLE IF NOT EXISTS strategy_proposals (
    id                TEXT PRIMARY KEY,       -- P-0001 format
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issue_id          TEXT,
    proposal_type     TEXT NOT NULL,          -- stance | message | schedule | crisis_response | attack

    -- AI 제안
    ai_recommendation TEXT NOT NULL,
    ai_reasoning      TEXT,
    ai_confidence     REAL DEFAULT 0.5,
    ai_data_sources   TEXT DEFAULT '[]',      -- JSON array

    -- 인간 결정
    status            TEXT DEFAULT 'pending', -- pending | approved | edited | rejected | expired
    decided_by        TEXT,
    decided_at        TIMESTAMP,
    human_version     TEXT,
    rejection_reason  TEXT,
    assigned_owner    TEXT,                   -- 대변인 | 전략팀 | 후보 | 여론분석팀 | 일정팀

    -- 결과 추적
    outcome           TEXT,                  -- positive | negative | neutral | unknown
    outcome_reason    TEXT,

    -- 메타
    urgency           TEXT DEFAULT 'today',  -- immediate | today | 48h | monitoring
    expiry            TIMESTAMP,
    tags_json         TEXT DEFAULT '[]',

    -- 충돌 기록
    conflict_with_override INTEGER DEFAULT 0,
    override_id       TEXT
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON strategy_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON strategy_proposals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_urgency ON strategy_proposals(urgency, status);

-- ─── 4. DECISION LOG (결정 이력) ───────────────────────────────────
-- 모든 인간 결정의 감사 추적
CREATE TABLE IF NOT EXISTS decision_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id       TEXT,
    timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action            TEXT NOT NULL,          -- approve | edit | reject | assign | override
    actor             TEXT NOT NULL,          -- strategy_director | system
    before_state_json TEXT,
    after_state_json  TEXT,
    reason            TEXT,
    metadata_json     TEXT DEFAULT '{}',
    FOREIGN KEY (proposal_id) REFERENCES strategy_proposals(id)
);

CREATE INDEX IF NOT EXISTS idx_decision_log_proposal ON decision_log(proposal_id);
CREATE INDEX IF NOT EXISTS idx_decision_log_time ON decision_log(timestamp DESC);

-- ─── 5. ACTIVE NARRATIVES (활성 서사) ──────────────────────────────
-- 전략실장이 설정하는 캠페인 서사 우선순위
CREATE TABLE IF NOT EXISTS active_narratives (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    priority          INTEGER NOT NULL,
    frame             TEXT NOT NULL,
    keywords_json     TEXT DEFAULT '[]',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry            TIMESTAMP,
    status            TEXT DEFAULT 'active',  -- active | expired | superseded
    created_by        TEXT DEFAULT 'strategy_director'
);

CREATE INDEX IF NOT EXISTS idx_narratives_status ON active_narratives(status, priority);

-- ─── 6. BLOCKED TERMS (차단어) ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS blocked_terms (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    term              TEXT NOT NULL,
    reason            TEXT,
    scope             TEXT DEFAULT 'all',     -- all | sns | spokesperson | candidate
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry            TIMESTAMP,
    status            TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_blocked_status ON blocked_terms(status);
