# Election Strategy OS V3 — Full Production Specification

## 시스템 목적

선거 캠프 전략실장이 사용하는 **실시간 전략 운영체제**.
AI는 참모총장(Chief of Staff)으로 작동하며, 최종 결정권은 항상 인간에게 있다.

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│                    DASHBOARD (Layer 6)                    │
│  Campaign Status Bar │ Issue Score │ Attack │ Defense    │
│  Regional │ AI Urgent │ Internal Signal │ Override Board │
│  Execution Queue │ Command Box                           │
├─────────────────────────────────────────────────────────┤
│                HUMAN DECISION LAYER (Layer 5)            │
│  Approve / Edit / Reject / Assign                        │
├─────────────────────────────────────────────────────────┤
│              STRATEGY SYNTHESIS ENGINE (Layer 4)          │
│  Public + Internal + Memory → AI Recommendation          │
├──────────────────┬──────────────────────────────────────┤
│ STRATEGIC MEMORY │        INTERNAL INPUT ENGINE          │
│   (Layer 3)      │           (Layer 2)                   │
│ Candidate Memory │  Telegram /report /order /hypothesis  │
│ Campaign Memory  │  Dashboard Manual Input               │
│ Director Memory  │  Structured Signal Objects             │
│ Field Memory     │                                        │
│ Decision Memory  │                                        │
├──────────────────┴──────────────────────────────────────┤
│              PUBLIC INTELLIGENCE ENGINE (Layer 1)         │
│  News │ Community │ YouTube │ Trends │ Polling           │
│  ← 기존 V2 collectors + engines 유지                     │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1: Public Intelligence Engine (기존 V2 유지 + 확장)

기존 `collectors/` + `engines/` 그대로 유지.

**추가 출력:**
- `canonical_issue_scores` → Layer 4로 전달
- `sentiment_map` → Layer 4로 전달
- `anomaly_alerts` → Layer 4로 전달
- `opponent_risk_signals` → Layer 4로 전달

---

## Layer 2: Internal Input Engine

### 2.1 텔레그램 구조화 입력

#### 명령어 체계

```
/report   — 현장 보고 (팩트)
/order    — 직접 지시 (전략실장 명령)
/hypo     — 전략 가설
/block    — 금지어/프레임 차단
/narrative — 서사 우선순위 설정
/override — AI 판단 덮어쓰기
/status   — 현재 시스템 상태 조회
/approve  — AI 제안 승인
/reject   — AI 제안 거부
/edit     — AI 제안 수정 후 승인
```

#### /report 형식

```
/report
region: 김해
issue: 생활지원금
content: 현장반응 냉담, 물가이슈가 더 강함
confidence: high
expiry: 24h
```

#### /order 형식

```
/order
issue: 강남발언
instruction: 후보 직접 대응 금지, 대변인만
expiry: today 18:00
priority: urgent
```

#### /hypo 형식

```
/hypo
issue: 조선업
hypothesis: 양산보다 창원에서 더 효과적
test_by: 3일 내 여론 반응 확인
```

#### /block 형식

```
/block
term: 퍼주기
reason: 역프레이밍 위험
scope: all  (all | sns | spokesperson | candidate)
```

#### /narrative 형식

```
/narrative
priority: 1
frame: 이번 선거는 구조적 경제회복이지, 현금지원이 아니다
keywords: 조선,방산,경제회복
expiry: 7d
```

#### /override 형식

```
/override
issue: 김경수_강남발언
ai_stance: counter
my_stance: avoid
reason: 팩트 미확인
expiry: today 18:00
```

### 2.2 자연어 입력 지원

텔레그램에서 구조화 명령어 없이 자연어로 입력하면,
AI가 자동으로 분류하여 structured object로 변환.

```
예시 입력: "김해 생활지원금 반응 안좋아. 물가 이슈가 더 커"

→ 자동 분류:
{
  type: "field_report",
  region: "김해",
  issue: "생활지원금",
  content: "현장반응 부정적, 물가이슈 우세",
  confidence: "medium",
  source: "strategy_director"
}
```

### 2.3 Internal Signal Object Schema

모든 내부 입력은 다음 구조로 정규화:

```python
@dataclass
class InternalSignal:
    id: str                    # UUID
    timestamp: datetime
    source: str                # strategy_director | field_agent | spokesperson
    signal_type: str           # field_report | order | hypothesis | block | narrative | override
    issue_id: str | None       # canonical_issue 연결
    region: str | None
    content: str
    confidence: str            # high | medium | low
    priority: str              # urgent | normal | low
    visibility: str            # director_only | strategy_team | all
    expiry: datetime | None
    metadata: dict             # 추가 필드 (instruction, hypothesis, blocked_term 등)
    status: str                # active | expired | superseded
    telegram_message_id: int | None
```

---

## Layer 3: Strategic Memory Engine

### 3.1 Memory Types

#### A) Candidate Memory
```python
candidate_memory = {
    "speaking_strengths": ["경제비전", "지역개발", "현장경험"],
    "weak_topics": ["강남발언", "과거논란"],
    "forbidden_expressions": ["퍼주기", "무상"],
    "emotional_risk_patterns": ["즉흥 반박 시 실언 위험", "피로 시 공격적 어조"],
    "best_format": "현장방문 + 짧은 메시지",
    "avoid_format": "기자회견 장시간 질의응답"
}
```

#### B) Campaign Memory
```python
campaign_memory = {
    "main_narratives": [
        {"frame": "구조적 경제회복", "priority": 1, "active": True},
        {"frame": "조선·방산 르네상스", "priority": 2, "active": True}
    ],
    "approved_frames": ["미래산업", "일자리", "지역균형"],
    "prohibited_themes": ["현금살포", "포퓰리즘 연상"],
    "crisis_playbooks": {
        "강남발언": {"stance": "avoid", "owner": "대변인", "message": "..."},
        "과거논란": {"stance": "pivot", "owner": "전략팀", "message": "..."}
    }
}
```

#### C) Strategy Director Memory
```python
director_memory = {
    "tactical_style": "선제공격보다 후속 프레이밍 선호",
    "attack_preference": "직접공격 회피, 우회적 비교",
    "silence_preference": "불리한 이슈는 24시간 침묵 후 판단",
    "override_habits": {
        "counter→avoid": 0.65,  # AI가 counter 추천 시 avoid로 변경하는 비율
        "push→monitor": 0.20
    },
    "language_preference": "격식체, 수치 포함, 감정적 표현 자제",
    "decision_speed": "신중형 (평균 2시간 숙고)"
}
```

#### D) Field Memory
```python
field_memory = {
    "regions": {
        "김해": {
            "sensitivity": ["생활지원금에 민감", "물가 최우선"],
            "reporters": [{"name": "김기자", "outlet": "경남일보", "bias": "neutral"}],
            "recurring_triggers": ["교통체증", "산업단지 이전"]
        },
        "창원": {
            "sensitivity": ["조선업 고용", "방산 클러스터"],
            "reporters": [],
            "recurring_triggers": ["STX 구조조정", "한화 투자"]
        }
    }
}
```

#### E) Decision Memory
```python
decision_memory = [
    {
        "timestamp": "2026-03-15T09:00",
        "ai_recommendation": {"issue": "강남발언", "stance": "counter"},
        "human_decision": {"stance": "avoid", "reason": "팩트 미확인"},
        "outcome": "positive",  # positive | negative | neutral | unknown
        "outcome_reason": "24시간 후 이슈 자연 소멸",
        "lesson": "강남발언 이슈는 대응보다 침묵이 효과적"
    }
]
```

### 3.2 Memory 학습 로직

```
Decision Memory 축적
    ↓
패턴 분석 (주기적)
    ↓
Director Memory 자동 업데이트
    ↓
Strategy Synthesis에 반영

예시:
  최근 10건 중 7건에서 counter→avoid 오버라이드
  → director_memory.override_habits["counter→avoid"] = 0.70
  → 향후 AI가 counter 추천 시 confidence를 낮추고
    "전략실장님은 이 유형에서 avoid를 선호하셨습니다" 부기
```

### 3.3 Memory Storage

- PostgreSQL `strategic_memory` 테이블 (type, key, value_json, updated_at)
- Redis 캐시 (hot memory: 현재 활성 narrative, 활성 override, 금지어)
- 주기적 consolidation (24h마다 decision_memory → director_memory 패턴 업데이트)

---

## Layer 4: Strategy Synthesis Engine

### 4.1 입력 통합

```
public_intelligence (Layer 1)
    ├─ canonical_issue_scores
    ├─ sentiment_map
    ├─ anomaly_alerts
    ├─ opponent_risk_signals
    └─ polling_data

internal_signals (Layer 2)
    ├─ active field_reports
    ├─ active orders
    ├─ active hypotheses
    ├─ active blocks
    └─ active narratives

strategic_memory (Layer 3)
    ├─ candidate_memory
    ├─ campaign_memory
    ├─ director_memory
    ├─ field_memory
    └─ decision_memory
```

### 4.2 Synthesis Logic

```python
def synthesize(public, internal, memory) -> StrategyPackage:

    # 1. Issue Priority (공개 데이터 + 내부 시그널 보정)
    for issue in public.issues:
        # 내부 보고로 점수 조정
        field_reports = internal.get_reports(issue.id)
        if field_reports:
            issue.score = adjust_score(issue.score, field_reports)

        # 활성 override 확인
        override = internal.get_active_override(issue.id)
        if override:
            issue.stance = override.my_stance
            issue.stance_source = "director_override"

        # 금지어 필터
        blocks = internal.get_active_blocks()
        issue.talking_points = filter_blocked_terms(issue.talking_points, blocks)

    # 2. Narrative Alignment
    narratives = internal.get_active_narratives()
    # 모든 메시지가 현재 서사와 일치하는지 확인

    # 3. Director Style Adaptation
    style = memory.director_memory
    # counter 추천 시 director가 avoid 선호하면 confidence 조정

    # 4. AI Synthesis (Claude 호출)
    prompt = build_synthesis_prompt(
        issues=ranked_issues,
        narratives=narratives,
        memory=memory,
        internal=internal,
        mode=campaign_mode
    )

    # 5. 출력: StrategyPackage
    return StrategyPackage(
        issue_priorities=[...],
        stance_recommendations=[...],
        message_recommendations=[...],
        region_priorities=[...],
        risk_alerts=[...],
        timing_recommendations=[...],
        conflict_resolutions=[...]   # AI vs Director 충돌 해결 기록
    )
```

### 4.3 충돌 해결 규칙

| 상황 | 규칙 |
|------|------|
| AI=counter, Director override=avoid | **Director 우선** (override 활성 시) |
| AI=push, 금지어 포함 | **금지어 제거** 후 push 유지 |
| AI=urgent, Director order=대기 | **Director order 우선** |
| Public=위기, Internal 보고 없음 | **AI 경고 + Director 확인 요청** |
| Public=안정, Internal=위기보고 | **Internal 우선, 점수 상향 조정** |

---

## Layer 5: Human Decision Layer

### 5.1 Approval Flow

```
AI 제안 생성
    ↓
Execution Queue에 등록 (status: pending)
    ↓
Dashboard 표시 + Telegram 알림
    ↓
Human 검토
    ├─ Approve → status: approved, execute
    ├─ Edit → status: edited, human 수정본으로 대체
    └─ Reject → status: rejected, reason 기록
    ↓
Decision Memory에 저장
    ↓
Director Memory 패턴 업데이트 (주기적)
```

### 5.2 Proposal Object

```python
@dataclass
class StrategyProposal:
    id: str                        # UUID
    created_at: datetime
    issue_id: str | None
    proposal_type: str             # stance | message | schedule | crisis_response

    # AI 제안
    ai_recommendation: str
    ai_reasoning: str
    ai_confidence: float           # 0.0~1.0
    ai_data_sources: list[str]     # 근거 데이터

    # 인간 결정
    status: str                    # pending | approved | edited | rejected | expired
    decided_by: str | None
    decided_at: datetime | None
    human_version: str | None      # 수정된 경우
    rejection_reason: str | None
    assigned_owner: str | None     # 대변인 | 전략팀 | 후보 | 여론분석팀

    # 메타
    urgency: str                   # immediate | today | 48h | monitoring
    expiry: datetime | None
    tags: list[str]
```

### 5.3 텔레그램 승인 흐름

```
AI → Telegram 알림:
━━━━━━━━━━━━━━━━━━
🔔 전략 제안 #P-0042
이슈: 김경수 강남발언
AI 판단: counter (신뢰도 0.78)
근거: 점수 82(+14), 부정 감성 급등
권장: 대변인 즉시 반박
━━━━━━━━━━━━━━━━━━

/approve P-0042
/reject P-0042 팩트 미확인
/edit P-0042 stance=avoid, owner=전략팀
```

---

## Layer 6: Dashboard

### 6.1 상단 바 (Campaign Status Bar)

```
┌──────────────────────────────────────────────────────────┐
│ 🔴 CRISIS │ 48.2% │ -2.1%p │ ⚠️ ALERT │ D-28 │ 09:42  │
│   mode    │ win%  │  gap   │  crisis  │ dday │  time   │
└──────────────────────────────────────────────────────────┘

색상 로직:
- CRISIS  → 빨강 (#EF4444)
- ALERT   → 주황 (#F97316)
- WATCH   → 노랑 (#EAB308)
- NORMAL  → 초록 (#22C55E)
```

### 6.2 메인 레이아웃 (4개 수평 레이어)

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: Campaign Situation Summary                  │
│ [Mode] [Polling Trend] [Top Issue] [Immediate Risk]  │
├─────────────────────────────────────────────────────┤
│ Layer 2: Strategic Action Panels (2×2 grid)          │
│ ┌──────────────┐ ┌──────────────┐                    │
│ │ Issue Score   │ │ Attack Point │                    │
│ │ Panel         │ │ Panel        │                    │
│ ├──────────────┤ ├──────────────┤                    │
│ │ Defense       │ │ Regional     │                    │
│ │ Readiness     │ │ Talking Pts  │                    │
│ └──────────────┘ └──────────────┘                    │
├─────────────────────────────────────────────────────┤
│ Layer 3: AI Strategic Intelligence                    │
│ [AI Urgent Report] [Internal Signal Feed]            │
│ [Strategic Override Board]                            │
├─────────────────────────────────────────────────────┤
│ Layer 4: Command Layer                               │
│ [Execution Queue] [Command Box: Top 3 Actions]       │
└─────────────────────────────────────────────────────┘
```

### 6.3 Issue Score Panel

```
┌─────────────────────────────────────────────────────┐
│ 📊 ISSUE SCORE                              [전체보기] │
├─────────────────────────────────────────────────────┤
│ # │ Issue              │ Score │ Δ   │ Sent │ Urg  │
│───┼────────────────────┼───────┼─────┼──────┼──────│
│ 1 │ 김경수 강남발언     │  82   │ +14 │ 🔴   │ 긴급 │
│ 2 │ 생활지원금 논란     │  71   │ +8  │ 🟠   │ 당일 │
│ 3 │ 조선업 르네상스     │  65   │ +3  │ 🟢   │ 모니 │
│ 4 │ 박완수 부동산       │  58   │ -2  │ 🔴   │ 48h  │
│ 5 │ 부울경 메가시티     │  45   │ 0   │ 🟢   │ 모니 │
└─────────────────────────────────────────────────────┘

클릭 시 드릴다운:
- 점수 분해 (velocity, mention, media, bonus)
- 소스 클러스터 (뉴스 30건 → 7개 스토리)
- 타임라인 (6h 버킷 추이)
- 여론조사 오버레이
```

### 6.4 Polling Overlay (이슈-여론조사 복합 차트)

```
┌─────────────────────────────────────────────────────┐
│     Issue Score ━━━  /  Polling % ─ ─ ─             │
│  100│                                                │
│   80│    ━━━╲                                        │
│   60│         ╲━━━━━━━                               │
│   40│  ─ ─ ─ ─╲─ ─ ─ ─ ─ ─                         │
│   20│           ─ ─ ─                                │
│    0│────────────────────────                        │
│      3/1  3/5  3/10  3/15  3/19                      │
└─────────────────────────────────────────────────────┘
```

### 6.5 Attack Point Panel

```
┌─────────────────────────────────────────────────────┐
│ ⚔️ ATTACK POINTS                                     │
├─────────────────────────────────────────────────────┤
│ 박완수 부동산 논란  │ 78 │ ⏰ 골든타임 4h │ push    │
│ [대변인멘트] [SNS] [후보발언]                        │
│─────────────────────────────────────────────────────│
│ 전희영 공약 모순   │ 62 │ ⏰ 12h          │ counter │
│ [대변인멘트] [SNS] [후보발언]                        │
└─────────────────────────────────────────────────────┘

버튼 클릭 → 메시지 초안 생성 (AI) → 승인 큐로 이동
```

### 6.6 Defense Readiness Panel

```
┌─────────────────────────────────────────────────────┐
│ 🛡️ DEFENSE READINESS                                │
├─────────────────────────────────────────────────────┤
│ Issue           │ Fact │ Msg │ Legal │ Grade │ Stance│
│─────────────────┼──────┼─────┼───────┼───────┼──────│
│ 강남발언        │  40  │  30 │  80   │  C    │ avoid │
│ 생활지원금      │  70  │  60 │  90   │  B    │ pivot │
│ 과거 논란       │  90  │  85 │  70   │  A    │counter│
└─────────────────────────────────────────────────────┘
```

### 6.7 Regional Panel (히트맵)

```
┌─────────────────────────────────────────────────────┐
│ 🗺️ REGIONAL SITUATION                                │
├─────────────────────────────────────────────────────┤
│                                                      │
│   [창원 🟠]    [김해 🔴]    [양산 🟡]               │
│     조선업        물가         교통                   │
│                                                      │
│   [진주 🟢]    [거제 🟡]    [통영 🟢]               │
│     안정         조선업        관광                   │
│                                                      │
│ 클릭 → 지역별 이슈 압력, 감성, 권장 토킹포인트       │
└─────────────────────────────────────────────────────┘
```

### 6.8 AI Urgent Report

```
┌─────────────────────────────────────────────────────┐
│ 🚨 AI URGENT REPORT                                 │
├─────────────────────────────────────────────────────┤
│ 09:15 │ 강남발언 급등 │ Score 82 │ 부정감성 80%      │
│ 영향: 창원·김해 핵심지역                              │
│ AI 권장: avoid (대변인 침묵, 조선업 프레임 전환)       │
│ 즉시 행동: 조선업 현장방문 스케줄 앞당기기             │
│ [승인] [수정] [거부]                                  │
├─────────────────────────────────────────────────────┤
│ 08:40 │ 박완수 부동산 뉴스 폭발 │ Score 78           │
│ 영향: 상대 약점 노출                                  │
│ AI 권장: push (골든타임 4시간)                         │
│ 즉시 행동: 대변인 논평 발표                            │
│ [승인] [수정] [거부]                                  │
└─────────────────────────────────────────────────────┘
```

### 6.9 Internal Signal Feed

```
┌─────────────────────────────────────────────────────┐
│ 📡 INTERNAL SIGNALS                                  │
├─────────────────────────────────────────────────────┤
│ 09:20 │ 전략실장 │ field_report │ 김해 │ 생활지원금  │
│        confidence: high │ expiry: 24h                │
│        "현장반응 냉담, 물가이슈가 더 강함"            │
│─────────────────────────────────────────────────────│
│ 08:50 │ 전략실장 │ order │ 강남발언                  │
│        "후보 직접 대응 금지, 대변인만" │ ~18:00       │
│─────────────────────────────────────────────────────│
│ 08:30 │ 전략실장 │ block │ 전체                      │
│        term: "퍼주기" │ reason: 역프레이밍 위험       │
└─────────────────────────────────────────────────────┘
```

### 6.10 Strategic Override Board

```
┌─────────────────────────────────────────────────────┐
│ ⚡ ACTIVE OVERRIDES                                  │
├─────────────────────────────────────────────────────┤
│ 강남발언 │ AI: counter → 실장: avoid │ ~18:00 활성  │
│ 생활지원금 │ AI: push → 실장: monitor │ ~24h 활성   │
│                                                      │
│ 만료된 override: 2건 (접기)                          │
└─────────────────────────────────────────────────────┘
```

### 6.11 Execution Queue

```
┌─────────────────────────────────────────────────────┐
│ 📋 EXECUTION QUEUE (대기 3건)                        │
├─────────────────────────────────────────────────────┤
│ P-0042 │ 강남발언 stance=avoid │ ⏳ pending │ 긴급   │
│ [승인] [수정] [거부] [담당지정]                       │
│─────────────────────────────────────────────────────│
│ P-0041 │ 조선업 대변인 메시지 │ ⏳ pending │ 당일    │
│ [승인] [수정] [거부] [담당지정]                       │
│─────────────────────────────────────────────────────│
│ P-0040 │ 창원 현장방문 앞당기기 │ ⏳ pending │ 48h   │
│ [승인] [수정] [거부] [담당지정]                       │
└─────────────────────────────────────────────────────┘
```

### 6.12 Command Box

```
┌─────────────────────────────────────────────────────┐
│ 🎯 TODAY'S COMMANDS (승인된 실행 지시)                │
├─────────────────────────────────────────────────────┤
│ 1. 조선업 프레임 밀어붙이기 — 담당: 대변인           │
│ 2. 강남발언 직접 대응 금지 — 담당: 전체               │
│ 3. 후보 창원 현장방문 — 담당: 일정팀                  │
└─────────────────────────────────────────────────────┘
```

### 6.13 Dashboard Modes

| Mode | 설명 | 강조 패널 |
|------|------|-----------|
| **Monitoring** | 공개 정보 중심 | Issue Score, Polling, Regional |
| **Strategy** | AI 합성 중심 | AI Urgent, Override Board, Internal Signal |
| **Command** | 실행 중심 | Execution Queue, Command Box, Defense Readiness |

---

## DB Schema (V3 추가)

### internal_signals
```sql
CREATE TABLE internal_signals (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL,                    -- strategy_director | field_agent | spokesperson
    signal_type TEXT NOT NULL,               -- field_report | order | hypothesis | block | narrative | override
    issue_id TEXT REFERENCES canonical_issues(issue_id),
    region TEXT,
    content TEXT NOT NULL,
    confidence TEXT DEFAULT 'medium',        -- high | medium | low
    priority TEXT DEFAULT 'normal',          -- urgent | normal | low
    visibility TEXT DEFAULT 'director_only', -- director_only | strategy_team | all
    expiry TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    status TEXT DEFAULT 'active',            -- active | expired | superseded
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT
);

CREATE INDEX idx_signals_type_status ON internal_signals(signal_type, status);
CREATE INDEX idx_signals_issue ON internal_signals(issue_id);
CREATE INDEX idx_signals_created ON internal_signals(created_at DESC);
```

### strategic_memory
```sql
CREATE TABLE strategic_memory (
    id SERIAL PRIMARY KEY,
    memory_type TEXT NOT NULL,               -- candidate | campaign | director | field | decision
    memory_key TEXT NOT NULL,                -- e.g., "speaking_strengths", "override_habits"
    value_json JSONB NOT NULL,
    source TEXT DEFAULT 'system',            -- system | director_input | auto_learned
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,                    -- NULL = permanent
    UNIQUE(memory_type, memory_key)
);

CREATE INDEX idx_memory_type ON strategic_memory(memory_type);
```

### strategy_proposals
```sql
CREATE TABLE strategy_proposals (
    id TEXT PRIMARY KEY,                     -- P-0001 format
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    issue_id TEXT REFERENCES canonical_issues(issue_id),
    proposal_type TEXT NOT NULL,             -- stance | message | schedule | crisis_response | attack

    -- AI 제안
    ai_recommendation TEXT NOT NULL,
    ai_reasoning TEXT,
    ai_confidence FLOAT,
    ai_data_sources JSONB DEFAULT '[]',

    -- 인간 결정
    status TEXT DEFAULT 'pending',           -- pending | approved | edited | rejected | expired
    decided_by TEXT,
    decided_at TIMESTAMP,
    human_version TEXT,
    rejection_reason TEXT,
    assigned_owner TEXT,                      -- 대변인 | 전략팀 | 후보 | 여론분석팀 | 일정팀

    -- 결과 추적
    outcome TEXT,                            -- positive | negative | neutral | unknown
    outcome_reason TEXT,

    -- 메타
    urgency TEXT DEFAULT 'today',            -- immediate | today | 48h | monitoring
    expiry TIMESTAMP,
    tags JSONB DEFAULT '[]',

    -- 충돌 기록
    conflict_with_override BOOLEAN DEFAULT FALSE,
    override_id TEXT REFERENCES internal_signals(id)
);

CREATE INDEX idx_proposals_status ON strategy_proposals(status);
CREATE INDEX idx_proposals_created ON strategy_proposals(created_at DESC);
```

### decision_log
```sql
CREATE TABLE decision_log (
    id SERIAL PRIMARY KEY,
    proposal_id TEXT REFERENCES strategy_proposals(id),
    timestamp TIMESTAMP DEFAULT NOW(),
    action TEXT NOT NULL,                    -- approve | edit | reject | assign | override
    actor TEXT NOT NULL,                     -- strategy_director | system
    before_state JSONB,
    after_state JSONB,
    reason TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_decision_log_proposal ON decision_log(proposal_id);
CREATE INDEX idx_decision_log_time ON decision_log(timestamp DESC);
```

### active_narratives
```sql
CREATE TABLE active_narratives (
    id SERIAL PRIMARY KEY,
    priority INTEGER NOT NULL,
    frame TEXT NOT NULL,
    keywords JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    expiry TIMESTAMP,
    status TEXT DEFAULT 'active',            -- active | expired | superseded
    created_by TEXT DEFAULT 'strategy_director'
);
```

### blocked_terms
```sql
CREATE TABLE blocked_terms (
    id SERIAL PRIMARY KEY,
    term TEXT NOT NULL,
    reason TEXT,
    scope TEXT DEFAULT 'all',                -- all | sns | spokesperson | candidate
    created_at TIMESTAMP DEFAULT NOW(),
    expiry TIMESTAMP,
    status TEXT DEFAULT 'active'
);
```

---

## Telegram Bot V3 Architecture

### 구조

```
telegram_bot/
├── bot_v3.py              # 메인 봇 (polling)
├── command_parser.py      # 구조화 명령어 파서
├── natural_language.py    # 자연어 → 구조화 변환 (Claude)
├── approval_handler.py    # /approve, /reject, /edit 처리
└── notification.py        # AI → 전략실장 알림 발송
```

### 명령어 파싱 로직

```python
class CommandParser:
    """텔레그램 구조화 명령어 → InternalSignal 변환"""

    COMMANDS = {
        "/report": "field_report",
        "/order": "order",
        "/hypo": "hypothesis",
        "/block": "block",
        "/narrative": "narrative",
        "/override": "override",
    }

    def parse(self, text: str) -> InternalSignal:
        """
        /report
        region: 김해
        issue: 생활지원금
        content: 현장반응 냉담
        confidence: high

        → InternalSignal(...)
        """
        lines = text.strip().split("\n")
        command = lines[0].strip().split()[0]
        fields = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()

        return self._build_signal(command, fields)
```

### 자연어 입력 처리

```python
class NaturalLanguageParser:
    """자연어 텔레그램 메시지 → InternalSignal 변환"""

    async def parse(self, text: str) -> InternalSignal:
        prompt = f"""
        다음 메시지를 캠페인 내부 시그널로 분류하세요.

        메시지: {text}

        JSON으로 응답:
        {{
            "signal_type": "field_report|order|hypothesis|block|narrative",
            "issue": "연결된 이슈 (없으면 null)",
            "region": "지역 (없으면 null)",
            "content": "핵심 내용",
            "confidence": "high|medium|low",
            "priority": "urgent|normal|low"
        }}
        """
        # Claude Haiku 호출 (빠른 분류)
        result = await ai_client.classify(prompt)
        return InternalSignal(**result)
```

---

## OpenClaw AI Agent 운영 방식

### 역할

OpenClaw에서 호스팅되는 AI 에이전트는 **전략 참모총장**으로 작동:

1. **수신**: 텔레그램 입력 + 공개 데이터 + 메모리
2. **합성**: 전략 패키지 생성
3. **제안**: StrategyProposal 생성 → 대기 큐 등록
4. **대기**: 인간 승인까지 실행하지 않음
5. **학습**: 결정 결과 → 메모리 업데이트

### 안전 장치

```
1. NO AUTONOMOUS EXECUTION
   - AI는 제안만 생성
   - status=pending으로만 생성 가능
   - status=approved로 변경은 인간만 가능

2. OVERRIDE PRIORITY
   - 활성 override가 있으면 AI 판단 무시
   - AI는 override 존재를 명시하고 대안 제시

3. BLOCKED TERM FILTER
   - 모든 AI 출력에서 blocked_terms 자동 필터링
   - 위반 시 경고 + 대체 표현 제안

4. NARRATIVE ALIGNMENT CHECK
   - 모든 AI 메시지가 active_narratives와 일치하는지 검증
   - 불일치 시 자동 수정 또는 경고

5. AUDIT TRAIL
   - 모든 AI 제안, 인간 결정, 변경 사항 기록
   - decision_log 테이블에 전체 이력 보존

6. CONFIDENCE CALIBRATION
   - Director가 자주 거부하는 유형 → confidence 자동 하향
   - Director가 자주 승인하는 유형 → confidence 유지/상향

7. EXPIRY ENFORCEMENT
   - 만료된 override/order 자동 비활성화
   - 만료 전 알림 발송
```

---

## 구현 순서

### Phase 1: Foundation (1주)
1. DB 스키마 V3 마이그레이션
2. InternalSignal 모델 + CRUD
3. StrategyProposal 모델 + CRUD
4. StrategicMemory 모델 + CRUD

### Phase 2: Telegram V3 (1주)
5. CommandParser 구현
6. NaturalLanguageParser 구현 (Claude Haiku)
7. ApprovalHandler (/approve, /reject, /edit)
8. NotificationService (AI → 전략실장 알림)

### Phase 3: Strategy Synthesis (1주)
9. Internal Signal → Score 조정 로직
10. Override Resolution 로직
11. Narrative Alignment 검증
12. Claude Synthesis Prompt 설계
13. StrategyProposal 자동 생성

### Phase 4: Memory Engine (1주)
14. Decision Memory 축적
15. Director Pattern 분석 (override_habits)
16. Confidence Calibration
17. Memory Consolidation (24h 주기)

### Phase 5: Dashboard V3 (1~2주)
18. Campaign Status Bar
19. Internal Signal Feed 패널
20. Strategic Override Board
21. Execution Queue + 승인 버튼
22. Command Box
23. Polling Overlay 차트
24. Dashboard Mode 전환 (Monitoring/Strategy/Command)

### Phase 6: Integration & Polish (1주)
25. End-to-end 테스트 (텔레그램 → 제안 → 승인 → 실행)
26. Memory 학습 검증
27. 부하 테스트 + 최적화
28. 배포

---

## 핵심 API Endpoints (V3 추가)

```
# Internal Signals
POST /api/v3/signals              — 내부 시그널 생성
GET  /api/v3/signals              — 활성 시그널 목록
GET  /api/v3/signals/:id          — 시그널 상세

# Proposals (Execution Queue)
GET  /api/v3/proposals            — 대기 중 제안 목록
POST /api/v3/proposals/:id/approve — 승인
POST /api/v3/proposals/:id/reject  — 거부
POST /api/v3/proposals/:id/edit    — 수정 후 승인

# Overrides
GET  /api/v3/overrides            — 활성 override 목록
POST /api/v3/overrides            — override 생성

# Memory
GET  /api/v3/memory/:type         — 메모리 타입별 조회
PUT  /api/v3/memory/:type/:key    — 메모리 수동 업데이트

# Narratives
GET  /api/v3/narratives           — 활성 서사 목록
POST /api/v3/narratives           — 서사 추가

# Blocked Terms
GET  /api/v3/blocked-terms        — 차단어 목록
POST /api/v3/blocked-terms        — 차단어 추가

# Dashboard
GET  /api/v3/dashboard/status-bar — 상단 바 데이터
GET  /api/v3/dashboard/command-box — 오늘의 지시 Top 3
GET  /api/v3/dashboard/mode       — 현재 대시보드 모드

# Decision Log
GET  /api/v3/decisions            — 결정 이력
GET  /api/v3/decisions/patterns   — Director 패턴 분석
```
