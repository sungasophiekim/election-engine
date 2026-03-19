# Election Engine V2 — SaaS 설계서

## 1. Product Overview

### 제품명
**Election Engine** — AI 기반 선거 캠프 전략 플랫폼

### 타겟 사용자
- 광역/기초단체장 선거 캠프 (주력)
- 국회의원 선거 캠프
- 정당 중앙당 전략실
- 정치 컨설팅 회사

### 핵심 가치
> "데이터로 선거를 보는 눈, AI로 전략을 짜는 머리"

### 일일 의사결정 루프
```
06:00  자동 모닝 브리핑 (텔레그램/카카오)
09:00  선대위 회의 — 상황실 대시보드 공유
12:00  이슈 모니터링 — 실시간 키워드 추적
15:00  AI 전략 에이전트 분석 요청
18:00  저녁 유세 일정 확인
21:00  일일 리포트 자동 생성
```

### TOP 5 의사결정
1. 오늘 어떤 메시지를 밀 것인가
2. 어떤 이슈에 대응/회피할 것인가
3. 어디서 유세할 것인가
4. 상대 후보 공격에 어떻게 반응할 것인가
5. 여론조사 추이에 따라 전략을 바꿀 것인가

---

## 2. Tech Stack

### Frontend
```
Next.js 14 (App Router)
TypeScript
Tailwind CSS + shadcn/ui
Recharts (차트)
Zustand (상태관리)
Socket.io-client (실시간)
```

### Backend
```
FastAPI (Python 3.12)
Celery + Redis (비동기 수집/분석)
SQLAlchemy 2.0 (ORM)
Alembic (마이그레이션)
```

### Database
```
PostgreSQL 16 + TimescaleDB (시계열)
Redis 7 (캐시 + 세션 + Celery broker)
```

### AI Layer
```
Claude Sonnet 4 (전략 분석, 위기 대응)
Claude Haiku 4.5 (실시간 감성, 대량 처리)
```

### Infrastructure
```
Vercel (프론트엔드)
Railway / Fly.io (백엔드 + Celery)
Supabase (PostgreSQL)
Upstash (Redis)
```

---

## 3. Database Schema

### Core Tables

```sql
-- 테넌트 (캠프)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,                    -- "김경수 캠프"
    candidate_name TEXT NOT NULL,
    election_type TEXT NOT NULL,           -- "광역단체장"
    election_date DATE NOT NULL,
    region TEXT NOT NULL,
    slogan TEXT,
    core_message TEXT,
    opponents JSONB DEFAULT '[]',
    pledges JSONB DEFAULT '{}',
    config JSONB DEFAULT '{}',             -- 임계값, 금기어 등
    plan TEXT DEFAULT 'free',              -- "free" | "pro" | "enterprise"
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 사용자
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'member',            -- "owner" | "admin" | "member" | "viewer"
    hashed_password TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 세션
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL
);
```

### TimescaleDB Hypertables (시계열)

```sql
-- 이슈 스코어 (시계열)
CREATE TABLE issue_scores (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    keyword TEXT NOT NULL,
    score REAL NOT NULL,
    mention_count INTEGER,
    velocity REAL,
    media_tier INTEGER,
    candidate_linked BOOLEAN,
    tv_reported BOOLEAN,
    portal_trending BOOLEAN,
    -- 채널별
    news_count INTEGER DEFAULT 0,
    blog_count INTEGER DEFAULT 0,
    cafe_count INTEGER DEFAULT 0,
    youtube_count INTEGER DEFAULT 0,
    youtube_views INTEGER DEFAULT 0,
    trends_interest INTEGER DEFAULT 0
);
SELECT create_hypertable('issue_scores', 'time');

-- 여론조사
CREATE TABLE polls (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    poll_date DATE NOT NULL,
    pollster TEXT NOT NULL,
    sample_size INTEGER,
    margin_of_error REAL,
    our_support REAL NOT NULL,
    opponent_support JSONB,
    undecided REAL DEFAULT 0,
    source TEXT,                           -- "manual" | "auto"
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 상대 후보 시그널 (시계열)
CREATE TABLE opponent_signals (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    opponent_name TEXT NOT NULL,
    recent_mentions INTEGER,
    message_shift TEXT,
    attack_prob REAL,
    recommended_action TEXT
);
SELECT create_hypertable('opponent_signals', 'time');

-- 소셜 버즈 (시계열)
CREATE TABLE social_buzz (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    candidate_name TEXT NOT NULL,
    blog_count INTEGER DEFAULT 0,
    cafe_count INTEGER DEFAULT 0,
    youtube_count INTEGER DEFAULT 0,
    youtube_views INTEGER DEFAULT 0,
    sentiment REAL DEFAULT 0,
    trends_interest INTEGER DEFAULT 0
);
SELECT create_hypertable('social_buzz', 'time');

-- 커뮤니티 시그널 (시계열)
CREATE TABLE community_signals (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    community TEXT NOT NULL,              -- "dcinside" | "fmkorea" | ...
    keyword TEXT,
    result_count INTEGER,
    tone TEXT,
    negative_ratio REAL,
    sample_titles JSONB
);
SELECT create_hypertable('community_signals', 'time');
```

### AI & Strategy Tables

```sql
-- AI 분석 이력
CREATE TABLE ai_analyses (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    type TEXT NOT NULL,                    -- "sentiment" | "strategy" | "crisis" | "qa"
    keyword TEXT,
    input_context JSONB,
    output JSONB,
    model TEXT,                           -- "claude-sonnet" | "claude-haiku"
    tokens_used INTEGER,
    requested_by TEXT,                    -- "dashboard" | "telegram" | "auto"
    cost_usd REAL DEFAULT 0
);

-- 일일 전략 브리핑
CREATE TABLE daily_briefs (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    date DATE NOT NULL,
    campaign_mode TEXT,                   -- "attack" | "defense" | "initiative" | "crisis"
    win_probability REAL,
    top_priority TEXT,
    key_messages JSONB,
    region_schedule JSONB,
    opponent_actions JSONB,
    risk_level TEXT,
    risk_factors JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 캠프 내부 인텔 (Phase 3)
CREATE TABLE camp_intel (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    category TEXT,                        -- "field_report" | "internal_poll" | "fund" | "memo"
    title TEXT,
    content TEXT,
    source TEXT,
    confidential BOOLEAN DEFAULT TRUE
);

-- 선거 일정
CREATE TABLE election_events (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    event_date DATE NOT NULL,
    event_type TEXT,                      -- "deadline" | "debate" | "voting" | "compliance"
    title TEXT NOT NULL,
    description TEXT,
    is_done BOOLEAN DEFAULT FALSE
);
```

---

## 4. API Architecture

### Auth
```
POST /api/auth/register          — 캠프 등록 (tenant + owner 생성)
POST /api/auth/login             — 로그인 → JWT
POST /api/auth/refresh           — 토큰 갱신
GET  /api/auth/me                — 현재 사용자 정보
```

### Dashboard
```
GET  /api/dashboard/warroom      — 상황실 종합 데이터
GET  /api/dashboard/executive    — KPI 9개
GET  /api/dashboard/alerts       — 긴급 알림
```

### Issues
```
GET  /api/issues/keywords        — 키워드 순위 리스트 (트렌딩 포함)
GET  /api/issues/keyword/{kw}    — 키워드 상세 (연관어+소스+감정)
GET  /api/issues/trend/{kw}      — 키워드 시계열 추이
POST /api/issues/refresh         — 수집 트리거 (Celery task)
```

### AI Agent
```
POST /api/ai/analyze             — AI 감성 분석 (하루 N회)
POST /api/ai/strategy            — AI 전략 브리핑 생성
POST /api/ai/crisis/{kw}         — AI 위기 대응 시나리오
POST /api/ai/ask                 — AI 자유 질의
GET  /api/ai/history             — 분석 이력
```

### Polling
```
GET  /api/polls                  — 여론조사 목록
POST /api/polls                  — 여론조사 입력
GET  /api/polls/analysis         — 승률 + 추세 + 스윙
DELETE /api/polls/{id}           — 삭제
```

### Social
```
GET  /api/social/buzz            — 후보별 소셜 버즈
GET  /api/social/community       — 커뮤니티 7곳 동향
GET  /api/social/channels        — 자체 채널 성과
```

### Strategy (어드민)
```
GET  /api/strategy/brief         — 오늘의 전략 브리핑
GET  /api/strategy/pledges       — 공약 비교
GET  /api/strategy/debate        — 토론 준비
GET  /api/strategy/schedule/{d}  — 유세 일정
GET  /api/strategy/attacks       — 공격 포인트
GET  /api/strategy/defense       — 방어 준비
```

### Tenant Admin
```
GET  /api/admin/tenant           — 캠프 설정 조회
PUT  /api/admin/tenant           — 캠프 설정 수정
GET  /api/admin/users            — 사용자 목록
POST /api/admin/users            — 사용자 초대
GET  /api/admin/usage            — API 사용량
```

### Webhook (외부 연동)
```
POST /api/webhook/telegram       — 텔레그램 봇 webhook
POST /api/webhook/kakao          — 카카오톡 알림
```

---

## 5. Screen Wireframe

### 5.1 상황실 (기본 화면)
```
┌─────────────────────────────────────────────────────┐
│ [로고] 김경수 캠프  D-76  승률 46.9%  [전략갱신] [설정]│
├────┬────────────────────────────────────┬────────────┤
│    │ ┌──────────────┬──────────────┐    │            │
│ N  │ │ 여론조사 추이  │  승률 게이지   │    │ 긴급알림    │
│ A  │ │ (SVG 차트)   │  46.9%       │    │ ● 위기 3건  │
│ V  │ │              │  격차 -0.2%p  │    │ ● 경고 4건  │
│    │ ├──────────────┼──────────────┤    │            │
│    │ │ 소셜 통계     │  이슈 현황    │    │ 선거일정    │
│    │ │ 김경수 209K   │  🔴3 🟠4 🟢4  │    │ D-76      │
│    │ │ 박완수 31K    │  TOP 5 이슈   │    │ ○ 후보등록  │
│    │ ├──────────────┴──────────────┤    │ ○ 사전투표  │
│    │ │ 💬 오늘의 핵심 메시지 3개      │    │ ○ 투표일   │
│    │ └─────────────────────────────┘    │            │
└────┴────────────────────────────────────┴────────────┘
```

### 5.2 이슈 탭
```
┌─────────────────────────────────────────────────────┐
│ 🤖 AI 전략 에이전트  [분석 요청]  남은 3/5회          │
│ (최근 분석 결과 또는 이력)                             │
├─────────────────────────────────────────────────────┤
│  # │ 키워드          │ 스코어 │ 트렌드 │ 24h    │     │
│  1 │ 🔵김경수 경남    │ ████ 83│  📈    │ +12%   │     │
│  2 │ 🔴박완수 경남    │ ████ 91│  🔥    │ +28%   │     │
│  3 │ ⚪경남 우주항공  │ ███  75│  📉    │ -5%    │     │
│  4 │ ⚪경남 청년 정책 │ ███  68│  →     │ 0%     │     │
├─────────────────────────────────────────────────────┤
│ (클릭 시) 연관 키워드 TOP 10 + 데이터 소스 + 감정 톤   │
└─────────────────────────────────────────────────────┘
```

### 5.3 전략 탭 (어드민)
```
┌─────────────────────────────────────────────────────┐
│ 모드: [선점]  최우선: 의제 선점하라                     │
├──────────────────────┬──────────────────────────────┤
│ 핵심 메시지 3개       │ 이슈 스코어 바                 │
│ 1. [선점] 프레임 정의  │ ████████ 김경수 83           │
│ 2. [공약] 5극3특      │ ██████ 부울경 75             │
│ 3. [비전] 다시 경남    │ ████ 청년 68                 │
├──────────────────────┼──────────────────────────────┤
│ 지역 우선순위          │ 상대 후보                     │
│ 1. 창원 (열기 0.83)   │ 박완수 공격확률 72% [선제반박]  │
│ 2. 김해 (열기 0.15)   │ 전희영 [무시]                 │
├──────────────────────┴──────────────────────────────┤
│ 공격 포인트 / 방어 준비 / 지역 토킹포인트               │
├─────────────────────────────────────────────────────┤
│ 🤖 AI 긴급 리포트 (최근 3건)                          │
└─────────────────────────────────────────────────────┘
```

---

## 6. MVP Roadmap

### Phase 1 — Foundation (2주)
```
목표: V1 엔진을 V2 인프라에 올리기

Week 1:
  □ Next.js 프로젝트 초기화 + Tailwind + shadcn
  □ PostgreSQL 스키마 생성 (Supabase)
  □ FastAPI 구조 정리 (라우터 분리)
  □ JWT 인증 구현
  □ V1 엔진 코드 임포트 (패키지화)

Week 2:
  □ 상황실 페이지 (Next.js)
  □ 이슈 페이지 (키워드 순위 + 상세)
  □ Celery 워커 (수집 백그라운드)
  □ Railway 배포
  □ 도메인 연결

산출물: 배포된 대시보드 + 1개 캠프 사용 가능
```

### Phase 2 — Core Features (4주)
```
목표: V1 기능 전체 이관 + 개선

Week 3-4:
  □ 전략 탭 (어드민)
  □ 공약 비교
  □ 여론조사 입력/분석
  □ 소셜 분석 (버즈 + 커뮤니티)
  □ AI 전략 에이전트 (Claude)

Week 5-6:
  □ 텔레그램 봇 (webhook 방식)
  □ 카카오톡 알림
  □ 모닝 브리핑 자동 생성 (Celery Beat)
  □ 유세 일정 최적화
  □ 토론 준비

산출물: V1 기능 100% + 자동화 + 알림
```

### Phase 3 — SaaS (4주)
```
목표: 멀티테넌트 + 과금 + 온보딩

Week 7-8:
  □ 멀티테넌트 데이터 격리
  □ 캠프 등록 → 설정 위자드
  □ 사용자 역할 (owner/admin/member/viewer)
  □ Stripe/Toss 결제 연동

Week 9-10:
  □ 어드민 대시보드 (사용량, 과금)
  □ 캠프 내부 인텔 입력 기능
  □ AI 컨텍스트 학습 (캠프별 커스텀)
  □ 랜딩 페이지 + 마케팅

산출물: 누구나 가입하여 사용할 수 있는 SaaS
```

---

## 7. Estimated Cost

### 개발 비용 (인건비 제외)
| 항목 | Phase 1 | Phase 2 | Phase 3 | 월 운영 |
|------|---------|---------|---------|--------|
| Vercel | $0 | $0 | $20 | $20 |
| Railway | $0 | $10 | $20 | $20 |
| Supabase | $0 | $0 | $25 | $25 |
| Redis (Upstash) | $0 | $0 | $10 | $10 |
| Claude API | $5 | $20 | $50 | $50+ |
| 도메인 | $15 | - | - | $15/년 |
| **합계** | **$20** | **$30** | **$125** | **$125+** |

### SaaS 과금 모델
| 플랜 | 가격 | AI 분석 | 사용자 | 수집 주기 |
|------|------|---------|-------|---------|
| Free | 무료 | 3회/일 | 2명 | 수동 |
| Pro | $99/월 | 20회/일 | 10명 | 1시간 |
| Enterprise | $299/월 | 무제한 | 무제한 | 실시간 |

---

## 8. Engineering Difficulty

| 작업 | 난이도 | 예상 기간 | 의존성 |
|------|--------|---------|--------|
| Next.js 대시보드 | ★★★ | 2주 | 디자인 확정 필요 |
| FastAPI 구조화 | ★★ | 3일 | 없음 |
| PostgreSQL 마이그레이션 | ★★ | 2일 | 스키마 확정 |
| JWT 인증 | ★★ | 1일 | 없음 |
| Celery 워커 | ★★ | 2일 | Redis |
| 멀티테넌트 | ★★★★ | 1주 | DB 스키마 |
| 결제 연동 | ★★★ | 3일 | Stripe 계정 |
| 실시간 WebSocket | ★★★ | 3일 | 없음 |
| 카카오톡 연동 | ★★ | 2일 | 카카오 앱 등록 |
| AI 컨텍스트 학습 | ★★★★ | 1주 | 캠프 데이터 |

---

## 9. Korean Election Compliance

### 선거법 준수 자동 체크
```
1. 여론조사 공표 금지 (선거일 6일 전)
   → 시스템 자동 감지 → 외부 공유 차단 모드
   → 내부 분석은 계속, 공유 버튼 비활성화

2. AI 생성 콘텐츠 표시 의무
   → 모든 AI 생성 메시지에 "AI 생성" 워터마크
   → 후보 발언 제안에 "검토 필요" 플래그

3. 비방/허위사실 금지
   → AI가 생성한 공격 포인트에 법적 검토 필터
   → forbidden_words 자동 체크

4. 선거비용 보고
   → AI API 비용을 선거비용에 포함해야 하는지 법률 자문 필요
```

### 한국 미디어 특화
```
1. 네이버 뉴스 댓글 수집 (V2 추가)
2. 네이버 실검 대체 → DataLab API 연동
3. 유튜브 정치 채널 별도 추적 리스트
4. 카카오톡 오픈채팅 모니터링 (수동 입력)
5. 지역 언론 (경남일보, 경남도민일보 등) 별도 가중치
```

---

## 10. V1 코드 재사용 계획

### 그대로 사용 (85%)
```
engines/
  issue_scoring.py        → v2/engines/issue_scoring.py
  voter_and_opponent.py   → v2/engines/voter_analyzer.py
  polling_tracker.py      → v2/engines/polling.py
  pledge_comparator.py    → v2/engines/pledges.py
  strategy_synthesizer.py → v2/engines/strategy.py
  debate_engine.py        → v2/engines/debate.py
  schedule_optimizer.py   → v2/engines/schedule.py
  issue_response.py       → v2/engines/issue_response.py

collectors/
  naver_news.py           → v2/collectors/naver.py
  social_collector.py     → v2/collectors/social.py
  youtube_collector.py    → v2/collectors/youtube.py
  trends_collector.py     → v2/collectors/trends.py
  community_collector.py  → v2/collectors/community.py
  keyword_engine.py       → v2/collectors/keywords.py
  keyword_analyzer.py     → v2/collectors/analyzer.py
```

### 새로 만들기 (15%)
```
v2/
  frontend/               → Next.js (완전 새로)
  api/                    → FastAPI 라우터 재구성
  workers/                → Celery 태스크 (새로)
  auth/                   → JWT + 세션 (새로)
  billing/                → 결제 (새로)
  migrations/             → Alembic (새로)
```
