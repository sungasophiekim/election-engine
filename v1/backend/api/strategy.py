"""전략 실행 레이어 API — AI 기반 데일리/위클리 전략 브리핑"""
import json
import os
from datetime import datetime, timedelta
from fastapi import APIRouter
from v1config.settings import ENRICHMENT_PATH, LEGACY_DATA

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

_cache: dict = {"daily": {"date": "", "data": None}, "weekly": {"date": "", "data": None}}


def _parse_json(text: str) -> dict:
    """AI 응답에서 JSON 추출 — 코드블록, 잘림 등 처리"""
    import re
    # 코드블록 제거
    if "```" in text:
        blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
        if blocks:
            text = blocks[0]
    # 앞뒤 공백
    text = text.strip()
    # JSON 시작/끝 찾기
    start = text.find("{")
    if start == -1:
        return {}
    text = text[start:]
    # 잘린 JSON 복구 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 괄호 밸런스로 닫기 시도
        depth_brace = 0
        depth_bracket = 0
        for ch in text:
            if ch == "{": depth_brace += 1
            elif ch == "}": depth_brace -= 1
            elif ch == "[": depth_bracket += 1
            elif ch == "]": depth_bracket -= 1
        fix = text.rstrip().rstrip(",")
        fix += "]" * max(0, depth_bracket)
        fix += "}" * max(0, depth_brace)
        try:
            return json.loads(fix)
        except Exception:
            # 마지막 시도: 잘린 문자열/값 닫기
            fix2 = fix
            if fix2.count('"') % 2 != 0:
                fix2 += '"'
            fix2 = re.sub(r',\s*([}\]])', r'\1', fix2)
            try:
                return json.loads(fix2)
            except Exception:
                return {"error": "JSON 파싱 실패", "raw": text[:500]}


def _load_snap() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _load_polls() -> list:
    try:
        with open(LEGACY_DATA / "polls.json") as f:
            return json.load(f).get("polls", [])
    except Exception:
        return []


def _load_history() -> list:
    try:
        with open(LEGACY_DATA / "indices_history.json") as f:
            return json.load(f)
    except Exception:
        return []


def _ensure_env():
    from pathlib import Path
    # 프로젝트 루트의 .env (로컬 개발용, Render에서는 환경변수로 설정)
    for candidate in [
        Path(__file__).resolve().parent.parent.parent.parent / ".env",  # election_engine/.env
        Path.cwd() / ".env",
    ]:
        if candidate.exists():
            for line in open(candidate):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break


def _build_daily_context(snap: dict) -> str:
    clusters = snap.get("news_clusters", [])
    buzz = snap.get("candidate_buzz", {})
    corr = snap.get("turnout", {}).get("correction", {})
    pandse = corr.get("pandse_index", 50)
    d_day = corr.get("d_day", "?")
    factors = corr.get("factors", [])
    polls = _load_polls()
    latest_poll = polls[-1] if polls else {}
    history = _load_history()[-7:]

    kim_m = sum(v.get("mention_count", 0) for k, v in buzz.items() if "김경수" in k)
    park_m = sum(v.get("mention_count", 0) for k, v in buzz.items() if "박완수" in k)
    kim_sents = [v.get("ai_sentiment", {}) for k, v in buzz.items() if "김경수" in k]
    park_sents = [v.get("ai_sentiment", {}) for k, v in buzz.items() if "박완수" in k]

    cluster_text = "\n".join(
        f"{i+1}. {c.get('name','')} | {c.get('side','중립')} | {c.get('count',0)}건 | tip: {c.get('tip','')}"
        for i, c in enumerate(clusters[:10])
    ) or "없음"

    factors_text = "\n".join(
        f"  - {f.get('name','')}: {f.get('value',0):+.1f} ({f.get('reason','')})"
        for f in factors
    ) or "없음"

    buzz_detail = ""
    for kw, v in list(buzz.items())[:15]:
        ai = v.get("ai_sentiment", {})
        buzz_detail += f"  - {kw}: 언급 {v.get('mention_count',0)}건, 감성 {ai.get('net_sentiment',0):.2f}, 톤: {ai.get('dominant_tone','?')}\n"

    trend_text = "\n".join(
        f"  {h.get('date','')}: 이슈(김{h.get('issue_kim',0)}/박{h.get('issue_park',0)}) 반응(김{h.get('reaction_kim',0)}/박{h.get('reaction_park',0)}) 판세{h.get('pandse',50):.1f}"
        for h in history
    ) or "없음"

    return f"""## 경남도지사 선거 전략 브리핑 데이터 ({datetime.now().strftime('%Y-%m-%d %H:%M')}, D-{d_day})

### 여론조사
- 최신: 김경수 {latest_poll.get('kim',0)}% vs 박완수 {latest_poll.get('park',0)}% ({latest_poll.get('label','')}, {latest_poll.get('date','')})
- 전체 조사 {len(polls)}건 추적 중

### 판세지수: {pandse:.1f}pt (50=중립)
9 Factors 상세:
{factors_text}

### 뉴스 노출 (24시간)
- 김경수: {kim_m}건 | 박완수: {park_m}건

### 후보별 버즈 상세 (AI 감성분석)
{buzz_detail}

### 뉴스 클러스터 TOP 10
{cluster_text}

### 최근 7회 지표 추이
{trend_text}

### 구조적 배경
- 경남 보수 텃밭. 7대(2018) 투표율 65.8%
- 연령구조: 2030세대 37.7%(감소), 60+ 39.5%(증가) → 인구만으로 13~14만표 열세
- 투표율 반영 시 여론조사 격차가 뒤집힐 수 있음 (60대 투표율 72.5% vs 20대 52%)
- 40대 지지율 64.1%로 최고 → 핵심 결집 대상
- 20대 부동층 44.9% → 설득 아닌 동원 필요 (무관심이 본질)
- 현직(박완수)은 예산·행정력·미디어 접근성에서 구조적 우위"""


@router.get("/daily-briefing")
def daily_briefing(force: bool = False):
    today = datetime.now().strftime("%Y-%m-%d")
    if not force and _cache["daily"]["date"] == today and _cache["daily"]["data"]:
        return _cache["daily"]["data"]

    snap = _load_snap()
    context = _build_daily_context(snap)
    _ensure_env()

    try:
        import anthropic
        client = anthropic.Anthropic()

        prompt = f"""{context}

당신은 김경수 경남도지사 캠프의 전략 총 책임자입니다.
매일 오전 후보에게 전달하는 전략대응 리포트를 작성하세요.

아래 JSON 형식으로만 답변 (코드블록 없이 순수 JSON):
{{
  "summary": "종합요약 — 3줄 이내. 판세 진단 + 핵심 위기/기회 + 오늘 반드시 해야 할 것",

  "issue_review": {{
    "issue_top5": [
      {{"rank": 1, "name": "이슈명", "count": 기사수, "side": "우리유리|상대유리|중립", "impact": "이슈·반응·판세지수에 미친 영향 1줄", "diagnosis": "AI 진단 — 투표율·지지율 영향 + 세그먼트별(2030/4050/60+) + 지역별(창원/김해/서부권) 분석 2줄"}}
    ],
    "reaction_top5": [
      {{"rank": 1, "keyword": "키워드", "sentiment": "긍정|부정|혼합", "volume": "높음|보통|낮음", "insight": "시민 반응 핵심 — 어떤 세그먼트가 어떻게 반응하는지 1줄"}}
    ],
    "our_diagnosis": "우리 후보 종합 진단 — 강점·약점·기회·위협 + 투표율/지지율 영향 (세그먼트별) 3줄",
    "opp_diagnosis": "상대 후보 종합 진단 — 강점·약점 + 우리가 공략할 틈 3줄"
  }},

  "strategy": {{
    "short_term": [
      {{
        "title": "단기 전략 제목",
        "issue_context": "어떤 이슈에 대응하는 전략인지",
        "action": "구체적 실행 방안 2줄",
        "expected_impact": "이 전략 실행 시 투표율·지지율 예상 영향 (세그먼트별 수치 포함)",
        "risk": "리스크 — 기존 지지층 이해관계·후보 공약과 충돌 가능성",
        "timeline": "이번 주|다음 주"
      }}
    ],
    "mid_long_term": [
      {{
        "title": "중장기 전략 제목",
        "rationale": "후보 이미지·공약·정치커리어를 고려한 근거",
        "action": "실행 방향 2줄",
        "target_segment": "공략 대상 (스윙/보수 이탈/무당층 등)",
        "synergy": "단기 전략과의 연계점"
      }}
    ]
  }},

  "messages": [
    {{
      "priority": 1,
      "target": "대상 (전체|2030|4050|60+|김해|서부권 등)",
      "message": "핵심 메시지 (후보 발언용, 20자 이내)",
      "sub_message": "보조 메시지/근거",
      "channel": "채널 (SNS|언론브리핑|현장|카드뉴스 등)",
      "caution": "주의사항 — 이 메시지가 다른 세그먼트에 미칠 역효과"
    }}
  ],

  "execution": [
    {{
      "when": "시간 (오늘 즉시|오늘 오전|오늘 오후|내일|이번 주 중)",
      "what": "할 일",
      "who": "담당 (대변인실|홍보팀|정책팀|후보|현장팀)",
      "kpi": "측정 기준 — 위클리 리포트에서 확인할 지표"
    }}
  ]
}}

작성 원칙:
1. 간결하되 핵심 포함 — 캠프는 바쁘다. 한 문장이 하나의 판단을 담아야 함
2. 데이터 근거 필수 — 기사수, 투표율, 지지율, 연령 세그먼트 수치를 반드시 인용
3. 단기 대응 시 중장기 충돌 검토 — "이 메시지가 40-50대 공략에 효과적이나, 20대 부동층과는 거리감 발생 가능" 식의 다각화 분석
4. 상대 현직 성과 직접 부정 금지 → "더 잘할 수 있다" 확장 프레임
5. 중앙당 이슈 편승 금지 → "경남만 보고 간다" 원칙
6. 실행 후 측정 가능해야 함 — KPI를 반드시 명시
7. youth_strategy 보고서 스타일 참고: 구분표(X민심 vs 여론조사), 단기/중기 과제 분리, 메시지 전환표
8. **중요: 이슈지수, 반응지수, 판세지수 등 자체 지수 수치를 리포트 본문에 절대 언급하지 마라.** 지수는 아직 안정화 중이므로 리포트 글에 포함시키면 안 됨. 대신 기사수, 여론조사 수치, 투표율, 지지율 등 원천 데이터만 인용할 것. 지수 데이터는 내부 분석 참고용으로만 활용하고 텍스트에는 쓰지 않는다."""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        data = _parse_json(text)
        data["generated_at"] = datetime.now().isoformat()
        data["d_day"] = snap.get("turnout", {}).get("correction", {}).get("d_day", "?")
        data["date"] = today

        _cache["daily"]["date"] = today
        _cache["daily"]["data"] = data
        return data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "generated_at": datetime.now().isoformat()}


@router.get("/weekly-briefing")
def weekly_briefing(force: bool = False):
    today = datetime.now().strftime("%Y-%m-%d")
    week_key = datetime.now().strftime("%Y-W%W")
    if not force and _cache["weekly"]["date"] == week_key and _cache["weekly"]["data"]:
        return _cache["weekly"]["data"]

    snap = _load_snap()
    history = _load_history()
    polls = _load_polls()
    corr = snap.get("turnout", {}).get("correction", {})
    _ensure_env()

    # 주간 데이터 추출
    week_data = history[-48:]  # 최근 48건 (약 1주일)
    first = week_data[0] if week_data else {}
    last = week_data[-1] if week_data else {}

    trend_text = "\n".join(
        f"  {h.get('date','')}: 이슈(김{h.get('issue_kim',0)}/박{h.get('issue_park',0)}) 반응(김{h.get('reaction_kim',0)}/박{h.get('reaction_park',0)}) 판세{h.get('pandse',50):.1f}"
        for h in week_data[::6]  # 6건 간격 샘플링
    ) or "없음"

    polls_text = "\n".join(
        f"  - {p.get('label','')}: 김{p.get('kim',0)}% 박{p.get('park',0)}% ({p.get('date','')})"
        for p in polls[-5:]
    ) or "없음"

    context = f"""## 주간 성과 측정 데이터 ({today}, D-{corr.get('d_day','?')})

### 주간 지표 변동
- 판세지수: {first.get('pandse',50):.1f} → {last.get('pandse',50):.1f} ({last.get('pandse',50)-first.get('pandse',50):+.1f}pt)
- 이슈 김경수: {first.get('issue_kim',0)} → {last.get('issue_kim',0)}
- 이슈 박완수: {first.get('issue_park',0)} → {last.get('issue_park',0)}
- 반응 김경수: {first.get('reaction_kim',0)} → {last.get('reaction_kim',0)}
- 반응 박완수: {first.get('reaction_park',0)} → {last.get('reaction_park',0)}

### 주간 추이 (샘플)
{trend_text}

### 여론조사 추이
{polls_text}

### 현재 판세지수 팩터
{chr(10).join(f"  - {f.get('name','')}: {f.get('value',0):+.1f}" for f in corr.get('factors', []))}"""

    try:
        import anthropic
        client = anthropic.Anthropic()

        prompt = f"""{context}

당신은 김경수 캠프 전략 총 책임자입니다. 한 주간 성과를 측정하는 위클리 리포트를 작성하세요.

아래 JSON 형식으로만 답변:
{{
  "week_summary": "주간 종합 판단 3줄 — 지표 변동 해석 + 전략 성과 + 다음 주 핵심 과제",
  "kpi_review": [
    {{
      "metric": "지표명",
      "start": "주초 값",
      "end": "주말 값",
      "change": "변동",
      "grade": "달성|미달|보류",
      "analysis": "해석 1줄"
    }}
  ],
  "strategy_review": [
    {{
      "strategy": "이번 주 실행한 전략",
      "executed": "실행 여부/내용",
      "result": "결과 — 지표 변동으로 확인된 효과",
      "lesson": "교훈 — 다음에 반복할 것 / 수정할 것"
    }}
  ],
  "segment_analysis": [
    {{
      "segment": "세그먼트 (2030/4050/60+/김해/서부권 등)",
      "trend": "이번 주 변화",
      "action_needed": "다음 주 필요 조치"
    }}
  ],
  "next_week": {{
    "priority_1": "최우선 과제 + 근거",
    "priority_2": "차우선 과제 + 근거",
    "priority_3": "보조 과제",
    "risk_watch": "주의 감시 이슈"
  }}
}}"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        data = _parse_json(text)
        data["generated_at"] = datetime.now().isoformat()
        data["week"] = week_key

        _cache["weekly"]["date"] = week_key
        _cache["weekly"]["data"] = data
        return data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "generated_at": datetime.now().isoformat()}
