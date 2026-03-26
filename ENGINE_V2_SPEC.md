# Election Engine V2 — 엔진 재설계 사양서

## 1. 재설계 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                         KEYWORD DISCOVERY                           │
│  keyword_engine.py (기존 유지)                                       │
│  Seed(46) → Expanded(뉴스추출) → Emerging(신규탐지)                   │
└──────────────────┬───────────────────────────────────────────────────┘
                   │ 300+ raw keywords
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  [NEW] A. CANONICAL ISSUE MAPPER                                    │
│  canonical_issue_mapper.py                                          │
│                                                                      │
│  ● 엔티티 정규화 (후보/상대/지역/정책 → 구조화 태그)                   │
│  ● 자카드 유사도 + 엔티티 오버랩 기반 클러스터링                        │
│  ● 300 keywords → ~60 canonical issues                              │
│  ● alias → canonical 매핑 테이블 유지                                 │
│                                                                      │
│  출력: CanonicalIssue(issue_id, canonical_name, aliases,             │
│        issue_type, target_side, entities)                            │
└──────────────────┬───────────────────────────────────────────────────┘
                   │ ~60 canonical issues
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION (기존 확장)                        │
│  unified_collector.py                                                │
│                                                                      │
│  ● Naver News (300건/키워드, 3-page)                                 │
│  ● Naver Blog + Cafe                                                 │
│  ● YouTube Data API                                                  │
│  ● Google Trends                                                     │
│  ● [NEW] I. 시간 윈도우 표준화 (6h / 24h / 7d)                       │
│                                                                      │
│  출력: UnifiedSignal + 원본 기사 리스트                                │
└────────────┬────────────────┬────────────────────────────────────────┘
             │                │
             ▼                ▼
┌────────────────────┐  ┌──────────────────────────────────────────────┐
│ [NEW] C. DEDUP     │  │ [NEW] D. ANOMALY DETECTOR                   │
│ news_deduplicator  │  │ anomaly_detector.py                          │
│                    │  │                                              │
│ ● 제목 n-gram 유사 │  │ ● 7일 롤링 baseline                          │
│ ● 82건→19스토리    │  │ ● z-score → surprise_score (0~100)           │
│ ● raw vs deduped   │  │ ● day-over-day 변화율                        │
│ ● 미디어티어 대표   │  │ ● is_anomaly / is_surge 판정                 │
│                    │  │                                              │
│ 출력: NewsStory[]  │  │ 출력: AnomalyResult                          │
└────────┬───────────┘  └──────────────────┬───────────────────────────┘
         │                                  │
         ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ISSUE SCORING (기존 확장)                          │
│  issue_scoring.py                                                    │
│                                                                      │
│  기존 공식 유지:                                                      │
│  base = velocity(0~25) + mention(0~25) + media(0~10)                │
│  bonus = candidate(+10) + trending(+8) + TV(+12) + proximity(+0~10) │
│                                                                      │
│  [NEW] mention_count에 deduped_story_count 반영 옵션                  │
│  [NEW] velocity에 surprise_score 가중 옵션                            │
│  [NEW] F. ScoreExplanation 객체 필수 생성                             │
│                                                                      │
│  출력: IssueScore + ScoreExplanation                                 │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
┌─────────────────────┐ ┌──────────────────────────────────────────────┐
│ [NEW] E. 2-STAGE    │ │ [NEW] G. READINESS SCORER                   │
│ SENTIMENT           │ │ response_readiness.py                        │
│                     │ │                                              │
│ Stage1: 기존 lexicon│ │ ● fact_readiness (0~100)                     │
│ (모든 이슈)         │ │ ● message_readiness (0~100)                  │
│                     │ │ ● legal_readiness (0~100)                    │
│ Stage2: Claude      │ │ ● total → A/B/C/D 등급                      │
│ (CRISIS 또는        │ │ ● stance override 생성                       │
│  candidate-linked   │ │                                              │
│  또는 score≥60)     │ │ 출력: ReadinessScore                         │
│                     │ │                                              │
│ 출력: polarity +    │ │ < 30 + high score → avoid                    │
│   target + impact   │ │ 30~60 → monitor/pivot                       │
└─────────┬───────────┘ │ > 60 → counter 가능                          │
          │             └──────────────────┬───────────────────────────┘
          ▼                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ISSUE RESPONSE (기존 확장)                         │
│  issue_response.py                                                   │
│                                                                      │
│  기존 5-stance 로직 유지:                                             │
│  push / counter / avoid / monitor / pivot                            │
│                                                                      │
│  [NEW] ReadinessScore에 의한 stance override 적용                     │
│  [NEW] 2-stage sentiment의 target/impact 반영                         │
│  [NEW] canonical issue 기반으로 중복 대응 방지                         │
│                                                                      │
│  출력: IssueResponse + ReadinessScore                                │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  [NEW] H. WEIGHTED STRATEGY MODE SELECTOR                           │
│  strategy_mode_v2.py                                                 │
│                                                                      │
│  4차원 압력 벡터:                                                     │
│  ● crisis_pressure     (위기 이슈 수 + 후보연결 + 점수)               │
│  ● polling_gap_pressure (격차 크기 + 방향)                            │
│  ● momentum_pressure   (추세 방향 + 변화 속도)                        │
│  ● opportunity_pressure (상대 약점 + 박빙 기회)                       │
│                                                                      │
│  → 가장 강한 압력이 모드 결정                                         │
│  → 모든 압력 수치와 이유 기록 (explainable)                           │
│  → D-14 보정 로직                                                    │
│                                                                      │
│  출력: ModeDecision(mode, pressures, reasoning, confidence)          │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    STRATEGY SYNTHESIZER (기존 확장)                   │
│  strategy_synthesizer.py                                             │
│                                                                      │
│  [CHANGE] _determine_campaign_mode → StrategyModeSelector.decide()  │
│  [NEW] ScoreExplanation 기반 이슈 전략 분류                           │
│  [NEW] canonical issue 기반 push/avoid/counter 분류                  │
│                                                                      │
│  출력: DailyStrategy + ModeDecision + explanations                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 모듈별 책임

| 파일 | 상태 | 책임 |
|------|------|------|
| `collectors/keyword_engine.py` | 유지 | 3계층 키워드 발굴 |
| `collectors/unified_collector.py` | 확장 | 4채널 수집 + 시간 윈도우 표준화 |
| `collectors/naver_news.py` | 유지 | 네이버 뉴스 API + 감성분석 |
| `collectors/keyword_analyzer.py` | 유지 | 심층 키워드 분석 + Claude |
| `engines/canonical_issue_mapper.py` | **신규** | 키워드 클러스터링 → canonical issue |
| `engines/news_deduplicator.py` | **신규** | 뉴스 중복 제거 (제목 유사도) |
| `engines/anomaly_detector.py` | **신규** | 기저선 기반 이상치 탐지 |
| `engines/response_readiness.py` | **신규** | 3차원 대응 준비도 채점 |
| `engines/score_explainer.py` | **신규** | 스코어 설명 객체 생성 |
| `engines/strategy_mode_v2.py` | **신규** | 4차원 압력 기반 모드 결정 |
| `engines/issue_scoring.py` | 확장 | 기존 공식 + dedup/anomaly 통합 |
| `engines/issue_response.py` | 확장 | readiness override 적용 |
| `engines/strategy_synthesizer.py` | 확장 | ModeSelector 교체 |
| `storage/schema_v2.sql` | **신규** | 11테이블 스키마 |
| `models/schemas.py` | 유지 | 기존 데이터 모델 (하위 호환) |

---

## 3. 개선된 스코어링 로직

### 기존 (유지)
```
base = velocity(0~25) + mention(0~25) + media(0~10) = 0~60
bonus = candidate(+10) + trending(+8) + TV(+12) + proximity(+0~10) = 0~40
score = clamp(base + bonus, 0, 100)
```

### 변경점

**3a. mention_score에 dedup 반영:**
```python
# 기존: mention_count = raw_articles (300건 중 24h 필터)
# V2: dedup_adjusted_count = deduped_story_count * story_weight + (raw - deduped) * copy_weight
#     story_weight = 1.0, copy_weight = 0.1
#     82건 19스토리 → 19 * 1.0 + 63 * 0.1 = 25.3 (기존 82 → 25.3)
```

**3b. velocity에 surprise_score 반영:**
```python
# 기존: velocity = 6h / 18h ratio (불안정)
# V2: effective_velocity = anomaly.velocity_6h  (기저선 대비)
#     if anomaly.is_surge: velocity_bonus += 5
```

**3c. ScoreExplanation 필수:**
```python
# 모든 score 산출 시 ScoreExplanation 동시 생성
# 대시보드 API가 explanation.to_dict() 반환
```

---

## 4. 개선된 대응 전략 로직

### Stance 결정 우선순위 (V2)

```
1. 위기 플레이북 매칭 → 즉시 반환 (기존 유지)

2. [NEW] Readiness Override 확인
   if readiness < 30 AND score ≥ 50:
     → "avoid" (대응 수단 부재)
   if readiness < 60 AND score ≥ 40:
     → "monitor" (counter 불가)

3. [NEW] 2-stage Sentiment 기반 Impact 확인
   if sentiment.impact == "hurts_us" AND score ≥ 60:
     → "counter"
   if sentiment.impact == "helps_us":
     → "push"

4. 기존 로직 유지
   - CRISIS + candidate danger → counter
   - opponent negative → push
   - high score neutral → pivot
   - low score → monitor
   - default → push
```

### Readiness → Stance 매핑

| Readiness | Issue Score | Stance |
|-----------|------------|--------|
| D (< 30)  | ≥ 50 | avoid — 대응 불가, 침묵 |
| C (30~50) | ≥ 40 | monitor — 준비 후 대응 |
| B (50~70) | any | pivot — 우리 영역으로 전환 |
| A (≥ 70)  | ≥ 50 | counter — 정면 대응 가능 |

---

## 5. 개선된 전략 모드 로직

### 기존 (제거)
```python
if crisis_linked:     CRISIS
elif gap < -2:        ATTACK
elif gap > +3:        DEFENSE
else:                 INITIATIVE
```

### V2: 4차원 압력 벡터

```python
pressures = {
  crisis:      f(crisis_count, candidate_linked, days_left),
  polling_gap: f(gap_magnitude, gap_direction),
  momentum:    f(trend_direction, trend_speed),
  opportunity: f(opponent_weakness, margin_closeness, momentum_direction),
}

scores = {
  CRISIS:     crisis_pressure,
  ATTACK:     max(0, polling_gap) + momentum * 0.5,
  DEFENSE:    abs(min(0, polling_gap)) + abs(min(0, momentum)) * 0.3,
  INITIATIVE: opportunity + (20 if 초박빙),
}

if scores["CRISIS"] >= 60: mode = CRISIS
else: mode = argmax(ATTACK, DEFENSE, INITIATIVE)
```

### Confidence 판정
```
gap = 1등 점수 - 2등 점수
≥ 20: high   (명확한 결정)
≥ 8:  medium (합리적 결정)
< 8:  low    (경계선 — 주의 필요)
```

---

## 6. 데이터 모델

### canonical_issues
| 컬럼 | 타입 | 설명 |
|------|------|------|
| issue_id | TEXT PK | "kimgyeongsu_gangnam" |
| canonical_name | TEXT | "김경수 강남 발언" |
| aliases_json | TEXT | 변형 키워드 리스트 |
| issue_type | TEXT | candidate_scandal / policy / ... |
| target_side | TEXT | ours / theirs / neutral |
| candidate_linked | BOOL | 후보 직접 연결 |
| entities_json | TEXT | 추출된 엔티티 |

### issue_metrics (6h 단위 시계열)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| issue_id | TEXT FK | canonical issue 참조 |
| ts_bucket | TIMESTAMP | 6h 단위 버킷 |
| raw_mentions | INT | 원본 기사 수 |
| deduped_story_count | INT | 고유 스토리 수 |
| surprise_score | REAL | 이상치 점수 0~100 |
| score_total | REAL | 종합 스코어 |
| score_components_json | TEXT | ScoreExplanation dict |
| readiness_score | REAL | 대응 준비도 |

### issue_responses
| 컬럼 | 타입 | 설명 |
|------|------|------|
| issue_id | TEXT FK | canonical issue 참조 |
| stance | TEXT | push/counter/avoid/monitor/pivot |
| readiness_score | REAL | 이 stance 결정의 근거 |
| readiness_detail_json | TEXT | 3차원 준비도 상세 |

---

## 7. 처리 플로우 (Discovery → Dashboard)

```
[매 6시간 실행]

1. keyword_engine.discover()
   → 300+ raw keywords

2. CanonicalIssueMapper.cluster_keywords(keywords)
   → ~60 canonical issues + alias mapping

3. for each canonical_issue:
     a. unified_collector.collect(issue.aliases)
        → UnifiedSignal + raw articles

     b. NewsDeduplicator.deduplicate(articles)
        → raw_mentions, deduped_story_count, NewsStory[]

     c. AnomalyDetector.analyze(keyword, current_24h, history_7d)
        → surprise_score, z_score, is_anomaly

     d. issue_scoring.calculate(signal, config)
        → IssueScore + breakdown

     e. [Stage1] lexicon sentiment
        → polarity, target, impact

     f. [Stage2, 조건부] if CRISIS or candidate_linked or score≥60:
          Claude sentiment refinement
        → refined polarity, target, impact

     g. ResponseReadinessScorer.score(keyword, score, type, side)
        → ReadinessScore (fact/message/legal)

     h. ScoreExplanation 조립 (d+b+c+e/f+g 통합)

     i. IssueResponseEngine.analyze(score, signal, readiness)
        → IssueResponse (stance, message, talking_points)

4. StrategyModeSelector.decide(scores, gap, momentum, opponents, days)
   → ModeDecision (mode, pressures, reasoning)

5. StrategySynthesizer.synthesize(scores, opponents, voters, polling)
   → DailyStrategy

6. DB 저장
   → canonical_issues 갱신
   → issue_metrics 6h bucket 삽입
   → issue_responses 삽입
   → strategy_decisions 삽입
   → news_stories 삽입

7. Dashboard API
   → ScoreExplanation.to_dict() 반환
   → canonical issue 기반 정렬/필터
   → 시계열 차트용 issue_metrics 쿼리
```

---

## 8. 구현 우선순위

| 순위 | 모듈 | 영향도 | 난이도 | 이유 |
|------|------|--------|--------|------|
| **1** | canonical_issue_mapper | 극대 | 중 | 모든 후속 모듈의 기반. 없으면 대시보드에 중복 이슈 범람 |
| **2** | score_explainer | 극대 | 하 | 대시보드 설명력의 핵심. 기존 breakdown 확장만으로 구현 |
| **3** | news_deduplicator | 고 | 중 | mention_count 신뢰도 직결. 통신사 전재 82건→19건 |
| **4** | anomaly_detector | 고 | 중 | velocity 노이즈 제거. 진짜 급등 vs 잡음 구분 |
| **5** | response_readiness | 고 | 하 | stance 결정의 근거 구조화. avoid의 이유 설명 |
| **6** | strategy_mode_v2 | 중 | 중 | 전략 결정의 설명력 강화. 기존 로직 교체 |
| **7** | schema_v2 + 저장 | 중 | 하 | 시계열 저장 기반. 대시보드 차트 데이터 |
| **8** | 2-stage sentiment | 중 | 고 | Claude 의존. Stage1만으로도 작동 가능 |
| **9** | 시간 윈도우 표준화 | 중 | 중 | unified_collector 수정. 6h/24h/7d 일관성 |
| **10** | unified_collector 통합 | 중 | 고 | 모든 신규 모듈을 파이프라인에 연결 |

---

## 9. 규칙 기반 vs AI 구분

### 규칙 기반 유지 (AI 불필요)
- 이슈 스코어링 (수학적 공식)
- 키워드 클러스터링 (자카드 유사도)
- 뉴스 중복 제거 (n-gram 유사도)
- 이상치 탐지 (z-score 통계)
- 대응 준비도 채점 (config 기반)
- 전략 모드 결정 (압력 벡터)
- 생명주기 분류 (시계열 패턴)

### AI 사용 (선택적)
- **2단계 감성 분석**: CRISIS / candidate-linked / score≥60일 때만 Claude Haiku
- **전략 메시지 제안**: AI 에이전트가 키워드별 전략 분석 (1일 3회 제한 유지)
- **프레임 해석**: keyword_analyzer.py의 narrative detection에 Claude 보조

### AI 절대 불필요
- 스코어 계산
- 위기 등급 분류
- stance 결정
- 캠페인 모드 결정
- 뉴스 중복 제거
- 이상치 탐지
