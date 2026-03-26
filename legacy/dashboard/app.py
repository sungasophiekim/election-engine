# Run: uvicorn dashboard.app:app --reload --host 0.0.0.0 --port 8000
# Then open: http://localhost:8000
"""
Election Engine — Web Dashboard (Production)
실시간 선거 전략 대시보드 — 인증, 비동기, 레이트리밋 적용
"""

import hashlib
import json
import os
import secrets
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, FastAPI, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="Election Engine Dashboard")

# ── 자동 스냅샷 스케줄러 ──
import threading

def _auto_snapshot_loop():
    """매일 09:00, 15:00, 21:00에 자동 스냅샷 저장."""
    import time as _t
    from datetime import datetime as _dt, date as _date

    _last_run_date = None

    while True:
        try:
            now = _dt.now()
            hour = now.hour
            today = _date.today().isoformat()

            # 하루 3번 (09, 15, 21시) + 같은 날 같은 시간 중복 방지
            run_key = f"{today}_{hour}"
            if hour in (9, 15, 21) and run_key != _last_run_date:
                _last_run_date = run_key
                print(f"[AutoSnapshot] 자동 스냅샷 시작: {now.strftime('%Y-%m-%d %H:%M')}")

                try:
                    from dotenv import load_dotenv
                    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

                    # 간이 데이터 수집
                    from collectors.naver_news import search_news, analyze_sentiment
                    from collectors.national_poll_collector import get_latest_national_poll
                    from collectors.economic_collector import get_latest_economic
                    from engines.index_tracker import DailySnapshot, save_daily_snapshot

                    # 뉴스 수집
                    kim_arts = search_news("김경수 경남", display=30, pages=1)
                    _t.sleep(0.5)
                    park_arts = search_news("박완수 경남", display=30, pages=1)
                    kim_sent = analyze_sentiment(kim_arts, "김경수", ["박완수"])
                    park_sent = analyze_sentiment(park_arts, "박완수", ["김경수"])

                    # 뉴스 기반 간이 인덱스 계산
                    kim_score = len(kim_arts) * 1.5
                    park_score = len(park_arts) * 1.5
                    kim_sentiment = kim_sent.get("net_sentiment", 0)

                    # Leading Index 간이 추정
                    np_data = get_latest_national_poll()
                    econ = get_latest_economic()
                    honeymoon = np_data.honeymoon_score if np_data else 0
                    economy = econ.incumbent_effect if econ else 0
                    li = 50 + kim_sentiment * 15 * 0.15 + honeymoon * 0.08 + economy * 0.05

                    snap = DailySnapshot(
                        date=today,
                        leading_index=round(max(35, min(65, li)), 1),
                        leading_direction="gaining" if li >= 53 else "losing" if li <= 47 else "stable",
                        issue_index_avg=round(kim_score, 1),
                        reaction_index_avg=round(kim_score * 0.7, 1),
                        opp_issue_avg=round(park_score, 1),
                        opp_reaction_avg=round(park_score * 0.7, 1),
                        poll_actual_kim=36.0,
                        poll_actual_park=34.0,
                        poll_source="KNN 서던포스트 2026-03-06",
                        turnout_predicted_gap=-14.8,
                        data_quality="auto",
                    )
                    save_daily_snapshot(snap)
                    _mark_run("auto_snapshot")
                    print(f"[AutoSnapshot] 저장 완료: LI={snap.leading_index}, Issue={snap.issue_index_avg}")

                    # 여론조사 자동 수집 (09시에만)
                    if hour == 9:
                        try:
                            from collectors.poll_auto_collector import auto_collect_polls
                            new_polls = auto_collect_polls()
                            if new_polls:
                                _v2_enrichment_cache = _v2_enrichment_cache or {}
                                _v2_enrichment_cache["auto_polls"] = [p.to_dict() for p in new_polls]
                                _mark_run("poll_auto")
                                print(f"[PollAuto] {len(new_polls)}건 여론조사 자동 감지")
                                for p in new_polls:
                                    print(f"  {p.source}: {p.org} 김경수 {p.kim}% 박완수 {p.park}% ({p.confidence:.0%})")
                        except Exception as e:
                            print(f"[PollAuto] Warning: {e}")

                except Exception as e:
                    print(f"[AutoSnapshot] 실패: {e}")

        except Exception:
            pass

        _t.sleep(300)  # 5분마다 체크


# 백그라운드 스레드로 시작
_auto_thread = threading.Thread(target=_auto_snapshot_loop, daemon=True)
_auto_thread.start()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# ---------------------------------------------------------------------------
# V3 Strategy OS Integration
# ---------------------------------------------------------------------------
try:
    from v3.api.routes import router as v3_router, init_storage as v3_init_storage
    from v3.storage import V3Storage
    from v3.engines.memory_engine import MemoryEngine

    _v3_db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "election_engine.db",
    )
    _v3_storage = V3Storage(_v3_db_path)
    v3_init_storage(_v3_storage)

    # Seed default memory
    _mem_engine = MemoryEngine(_v3_storage)
    _mem_engine.seed_defaults()

    app.include_router(v3_router)
    print("[V3] Strategy OS routes mounted at /api/v3/*")
except Exception as e:
    print(f"[V3] Warning: Could not load V3 routes: {e}")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

DASHBOARD_PW_HASH = hashlib.sha256(
    os.getenv("DASHBOARD_PASSWORD", "election2026").encode()
).hexdigest()
SESSION_SECRET = secrets.token_hex(32)
SESSIONS = {}  # {token: expiry_timestamp}
SESSION_TTL = 24 * 60 * 60  # 24 hours


def check_auth(session_token: Optional[str]) -> bool:
    if not session_token or session_token not in SESSIONS:
        return False
    if SESSIONS[session_token] < time.time():
        del SESSIONS[session_token]
        return False
    return True


def require_auth(session_token: Optional[str]):
    """Return RedirectResponse if not authenticated, else None."""
    if not check_auth(session_token):
        return RedirectResponse("/login", status_code=302)
    return None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_last_run_time: float = 0.0
_strategy_running: bool = False
RATE_LIMIT_SECONDS = 30  # 30초로 단축


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    from storage.database import ElectionDB
    db = ElectionDB()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Auth pages
# ---------------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if pw_hash != DASHBOARD_PW_HASH:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "비밀번호가 올바르지 않습니다."}
        )
    token = secrets.token_hex(32)
    SESSIONS[token] = time.time() + SESSION_TTL
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        key="session_token",
        value=token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
    )
    return resp


@app.get("/logout")
async def logout(session_token: str = Cookie(default=None)):
    if session_token and session_token in SESSIONS:
        del SESSIONS[session_token]
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session_token")
    return resp


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session_token: str = Cookie(default=None)):
    redir = require_auth(session_token)
    if redir:
        return redir
    response = templates.TemplateResponse("index.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# JSON APIs — cached DB data
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def api_status(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    crisis_issues = []
    try:
        with get_db() as db:
            rows = db.get_latest_scores()
            for r in rows:
                level = (r.get("crisis_level") or r.get("level") or "").upper()
                if level == "CRISIS":
                    crisis_issues.append(r.get("keyword", ""))
    except Exception:
        pass
    return {
        "ok": True,
        "crisis": crisis_issues,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/scores")
async def api_scores(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        rows = db.get_latest_scores()
        return rows


@app.get("/api/opponents")
async def api_opponents(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        rows = db._conn.execute(
            """
            SELECT o.opponent_name, o.recent_mentions, o.message_shift,
                   o.attack_prob, o.recommended_action, o.recorded_at
            FROM opponent_signals o
            INNER JOIN (
                SELECT opponent_name, MAX(recorded_at) AS max_at
                FROM opponent_signals
                GROUP BY opponent_name
            ) latest ON o.opponent_name = latest.opponent_name
                     AND o.recorded_at = latest.max_at
            ORDER BY o.attack_prob DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/regions")
async def api_regions(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        rows = db._conn.execute(
            """
            SELECT v.region, v.voter_count, v.swing_index,
                   v.priority_score, v.local_issue_heat, v.recorded_at
            FROM voter_priorities v
            INNER JOIN (
                SELECT region, MAX(recorded_at) AS max_at
                FROM voter_priorities
                GROUP BY region
            ) latest ON v.region = latest.region
                     AND v.recorded_at = latest.max_at
            ORDER BY v.priority_score DESC
            """
        ).fetchall()
        # config에서 추가 필드 merge
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config_regions = SAMPLE_GYEONGNAM_CONFIG.regions
        result = []
        for r in rows:
            d = dict(r)
            cfg = config_regions.get(d["region"], {})
            d["population"] = cfg.get("population", 0)
            d["type"] = cfg.get("type", "")
            d["key_issue"] = cfg.get("key_issue", "")
            d["권역"] = cfg.get("권역", "")
            d["2018_kim_pct"] = cfg.get("2018_kim_pct", 0)
            d["2018_opp_pct"] = cfg.get("2018_opp_pct", 0)
            d["2022_yang_pct"] = cfg.get("2022_yang_pct", 0)
            d["2022_park_pct"] = cfg.get("2022_park_pct", 0)
            d["swing_7to8"] = cfg.get("swing_7to8", 0)
            d["battlegrounds"] = cfg.get("battlegrounds", [])
            d["population_surge"] = cfg.get("population_surge", "")
            result.append(d)
        return result


@app.get("/api/trend/{keyword}")
async def api_trend(keyword: str, days: int = 7, session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        return db.get_issue_trend(keyword, days)


# ---------------------------------------------------------------------------
# Debate prep
# ---------------------------------------------------------------------------

@app.get("/api/debate-prep")
async def api_debate_prep(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.debate_engine import DebateEngine
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        engine = DebateEngine(SAMPLE_GYEONGNAM_CONFIG)
        prep = engine.prepare(SAMPLE_GYEONGNAM_CONFIG.opponents[0] if SAMPLE_GYEONGNAM_CONFIG.opponents else "박완수")
        return {
            "opening": prep.opening_statement,
            "closing": prep.closing_statement,
            "questions": [
                {
                    "topic": q.topic, "question": q.question,
                    "difficulty": q.difficulty, "source": q.source,
                    "response": q.recommended_response,
                    "pivot": q.pivot_to, "trap": q.trap_warning,
                }
                for q in prep.expected_questions
            ],
            "attacks": [
                {
                    "topic": a.topic, "opening": a.opening_line,
                    "argument": a.main_argument, "killer_q": a.killer_question,
                    "follow_up": a.follow_up,
                }
                for a in prep.attack_scripts
            ],
            "defenses": prep.defense_scripts,
            "pivots": prep.pivot_messages,
            "red_lines": prep.red_lines,
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

@app.get("/api/schedule/{date}")
async def api_schedule(date: str, session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.schedule_optimizer import ScheduleOptimizer
        from engines.voter_and_opponent import calculate_voter_priorities
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opt = ScheduleOptimizer(config)
        segs = calculate_voter_priorities(config)
        schedule = opt.generate_daily_schedule(date, voter_segments=segs)
        return {
            "date": schedule.date,
            "theme": schedule.day_theme,
            "total_regions": schedule.total_regions,
            "total_travel": schedule.total_travel_min,
            "key_message": schedule.key_message,
            "events": [
                {
                    "time": e.time_slot, "region": e.region,
                    "type": e.event_type, "location": e.location_hint,
                    "talking_points": e.talking_points, "priority": e.priority,
                    "notes": e.notes,
                }
                for e in schedule.events
            ],
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Polling history
# ---------------------------------------------------------------------------

@app.get("/api/polling-history")
async def api_polling_history(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.polling_tracker import PollingTracker
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        tracker = PollingTracker(SAMPLE_GYEONGNAM_CONFIG)
        return {
            "polls": [
                {
                    "date": p.poll_date, "pollster": p.pollster,
                    "our": p.our_support, "opponent": p.opponent_support,
                    "moe": p.margin_of_error,
                }
                for p in tracker.polls
            ],
            "win_prob": tracker.calculate_win_probability(),
            "trend": tracker.calculate_trend(),
            "swing": tracker.analyze_swing_voters(),
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Poll CRUD — 여론조사 입력/삭제
# ---------------------------------------------------------------------------

@app.post("/api/polls")
async def api_add_poll(request: Request, session_token: str = Cookie(default=None)):
    """새 여론조사 입력"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        body = await request.json()
        poll_date = body.get("poll_date", "")
        pollster = body.get("pollster", "")
        our_support = float(body.get("our_support", 0))
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        default_opp = SAMPLE_GYEONGNAM_CONFIG.opponents[0] if SAMPLE_GYEONGNAM_CONFIG.opponents else "상대"
        opponent_name = body.get("opponent_name", default_opp)
        opponent_support = float(body.get("opponent_support", 0))
        sample_size = int(body.get("sample_size", 1000))
        margin_of_error = float(body.get("margin_of_error", 3.0))
        undecided = float(body.get("undecided", 0))

        if not poll_date or not pollster or our_support <= 0:
            return JSONResponse({"error": "필수 필드 누락 (poll_date, pollster, our_support)"}, status_code=400)

        with get_db() as db:
            db.save_poll(
                poll_date=poll_date,
                pollster=pollster,
                sample_size=sample_size,
                margin_of_error=margin_of_error,
                our_support=our_support,
                opponent_support={opponent_name: opponent_support},
                undecided=undecided,
            )

        return {"ok": True, "message": f"{poll_date} {pollster} 여론조사 저장 완료"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/polls/{poll_id}")
async def api_delete_poll(poll_id: int, session_token: str = Cookie(default=None)):
    """여론조사 삭제"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        with get_db() as db:
            db.delete_poll(poll_id)
        return {"ok": True, "message": f"Poll {poll_id} 삭제 완료"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/polls/nesdc-sync")
async def api_nesdc_sync(session_token: str = Cookie(default=None)):
    """중앙선거여론조사심의위원회 자동 수집"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.nesdc_scraper import NesdcScraper
        scraper = NesdcScraper()
        polls = scraper.collect_new_and_save()
        return {
            "total_found": len(polls),
            "parsed": sum(1 for p in polls if p.pdf_parsed),
            "polls": [
                {
                    "ntt_id": p.ntt_id,
                    "org": p.org,
                    "survey_date": p.survey_date,
                    "pub_date": p.pub_date,
                    "sample_size": p.sample_size,
                    "our_support": p.our_support,
                    "opponent_support": p.opponent_support,
                    "pdf_parsed": p.pdf_parsed,
                }
                for p in polls
            ],
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/polls")
async def api_list_polls(session_token: str = Cookie(default=None)):
    """저장된 여론조사 전체 목록"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        return db.get_all_polls()


# ---------------------------------------------------------------------------
# Keyword Engine — 실시간 키워드 관리
# ---------------------------------------------------------------------------

@app.get("/api/keywords")
async def api_keywords(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
    from collectors.keyword_engine import KeywordEngine
    engine = KeywordEngine(SAMPLE_GYEONGNAM_CONFIG)
    return {
        "keywords": [
            {"keyword": k.keyword, "source": k.source, "category": k.category,
             "priority": k.priority, "reason": k.reason, "active": k.active}
            for k in engine.keywords
        ],
        "total": len(engine.keywords),
        "active": sum(1 for k in engine.keywords if k.active),
    }


@app.post("/api/keywords/discover")
async def api_discover_keywords(session_token: str = Cookie(default=None)):
    """키워드 자동 발굴 실행"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from collectors.keyword_engine import KeywordEngine
        engine = KeywordEngine(SAMPLE_GYEONGNAM_CONFIG)
        discovered = engine.discover()
        return {
            "keywords": [
                {"keyword": k.keyword, "source": k.source, "category": k.category,
                 "priority": k.priority, "reason": k.reason, "active": k.active}
                for k in engine.keywords
            ],
            "total": len(engine.keywords),
            "active": len(discovered),
            "seed_count": sum(1 for k in engine.keywords if k.source == "seed"),
            "extracted_count": sum(1 for k in engine.keywords if k.source in ("news_extract", "social_extract", "emerging")),
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/keywords/add")
async def api_add_keyword(request: Request, session_token: str = Cookie(default=None)):
    """수동 키워드 추가"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    body = await request.json()
    keyword = body.get("keyword", "").strip()
    reason = body.get("reason", "수동 추가")
    if not keyword:
        return JSONResponse({"error": "키워드 필수"}, status_code=400)
    # DB에 저장하는 대신, 응답으로만 확인 (stateless)
    return {"ok": True, "keyword": keyword, "reason": reason,
            "message": f"'{keyword}' 키워드가 다음 분석에 포함됩니다"}


# ---------------------------------------------------------------------------
# AI Strategy Agent — 하루 3회 정밀 분석
# ---------------------------------------------------------------------------

AI_DAILY_LIMIT = 3

@app.post("/api/ai-agent/analyze")
async def api_ai_analyze(request: Request, session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    body = await request.json()
    keyword = body.get("keyword", "")
    if not keyword:
        return JSONResponse({"error": "키워드 필수"}, status_code=400)

    def _run():
        from storage.database import ElectionDB
        db = ElectionDB()

        # 하루 3회 제한 체크
        today_count = db.count_ai_today()
        if today_count >= AI_DAILY_LIMIT:
            db.close()
            return {"error": f"오늘 분석 {AI_DAILY_LIMIT}회 한도 초과 (사용: {today_count}회)", "remaining": 0}

        # 컨텍스트 수집
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from collectors.naver_news import search_news
        config = SAMPLE_GYEONGNAM_CONFIG

        articles = search_news(keyword, display=100, pages=2)
        titles = [a["title"] for a in articles[:20]]

        # 전략 컨텍스트 구성
        context = {
            "candidate": config.candidate_name,
            "slogan": config.slogan,
            "opponents": config.opponents,
            "pledges": list(config.pledges.keys()),
            "keyword": keyword,
            "article_count": len(articles),
            "titles": titles,
        }

        # Claude 호출
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key or "xxxxx" in api_key:
            db.close()
            return {"error": "Anthropic API 키 미설정", "remaining": AI_DAILY_LIMIT - today_count}

        import anthropic, json as jmod
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""당신은 '{config.candidate_name}' 후보 ({config.region} {config.election_type}) 캠프의 수석 전략 참모입니다.
슬로건: {config.slogan}
상대: {', '.join(config.opponents)}
공약: {', '.join(config.pledges.keys())}

아래는 "{keyword}" 키워드의 최근 뉴스 제목입니다:
{chr(10).join(f'{i+1}. {t}' for i,t in enumerate(titles[:15]))}

캠프 전략가 관점에서 분석하세요.
중요: 반드시 한 줄 JSON으로만 응답하세요. 줄바꿈 없이 한 줄로. 각 값은 50자 이내로 간결하게:
{{
  "sentiment": "긍정/부정/중립/혼재",
  "score": -1.0~1.0,
  "summary": "현재 상황 2~3문장 요약",
  "risk": "캠프 관점 위험 요소 (구체적으로)",
  "opportunity": "활용 가능한 기회 (구체적으로)",
  "recommended_action": "지금 해야 할 행동 1가지",
  "message_suggestion": "이 이슈에 대해 후보가 할 수 있는 발언 1문장",
  "avoid": "절대 하면 안 되는 것"
}}"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            # JSON 파싱 — 여러 방법 시도
            import re as re_mod
            raw = re_mod.sub(r'[\n\r\t]+', ' ', raw)
            result = None
            # 시도 1: 직접 파싱
            try:
                result = jmod.loads(raw)
            except jmod.JSONDecodeError:
                pass
            # 시도 2: { } 추출
            if not result:
                m = re_mod.search(r'\{.*\}', raw, re_mod.DOTALL)
                if m:
                    try:
                        result = jmod.loads(re_mod.sub(r'[\n\r\t]+', ' ', m.group()))
                    except jmod.JSONDecodeError:
                        pass
            # 시도 3: fallback
            if not result:
                result = {"sentiment": "분석완료", "score": 0, "summary": raw[:300]}

            # DB 저장
            db.save_ai_analysis(
                analysis_type="sentiment",
                keyword=keyword,
                input_context=jmod.dumps(context, ensure_ascii=False),
                output=jmod.dumps(result, ensure_ascii=False),
            )
            remaining = AI_DAILY_LIMIT - today_count - 1
            db.close()

            return {
                "analysis": result,
                "keyword": keyword,
                "remaining": remaining,
                "source": "claude-sonnet",
            }
        except Exception as e:
            db.close()
            return {"error": str(e)[:100], "remaining": AI_DAILY_LIMIT - today_count}

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/ai-agent/history")
async def api_ai_history(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        analyses = db.get_ai_analyses(limit=20)
        today_count = db.count_ai_today()
    return {
        "analyses": analyses,
        "today_count": today_count,
        "daily_limit": AI_DAILY_LIMIT,
        "remaining": max(0, AI_DAILY_LIMIT - today_count),
    }


@app.get("/api/daily-briefing")
async def api_daily_briefing(session_token: str = Cookie(default=None)):
    """최신 데일리 브리핑 리포트 반환"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        rows = db.get_ai_analyses(keyword="TOP10_DAILY", limit=1)
    if not rows:
        return {"report": None, "created_at": None}
    r = rows[0]
    return {
        "report": r.get("output", ""),
        "created_at": r.get("created_at", ""),
        "input_context": r.get("input_context", ""),
    }


# ---------------------------------------------------------------------------
# Community Monitoring — 한국 주요 커뮤니티 모니터링
# ---------------------------------------------------------------------------

@app.get("/api/community")
async def api_community(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.community_collector import scan_all_communities, COMMUNITIES
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        report = scan_all_communities(f"{config.candidate_name}")
        return {
            "keyword": report.keyword,
            "total": report.total_mentions,
            "hottest": report.hottest_community,
            "overall_tone": report.overall_tone,
            "communities": [
                {
                    "id": s.community_id,
                    "name": s.name,
                    "icon": s.icon,
                    "count": s.result_count,
                    "tone": s.tone,
                    "negative": s.negative_ratio,
                    "positive": s.positive_ratio,
                    "titles": s.recent_titles[:5],
                    "info": COMMUNITIES.get(s.community_id, {}),
                }
                for s in report.signals
            ],
            "timestamp": report.timestamp,
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Owned Channels — 자체 SNS 채널 모니터링
# ---------------------------------------------------------------------------

@app.get("/api/owned-channels")
async def api_owned_channels(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.owned_channels import monitor_all_channels, channels_from_config
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        chan_config = channels_from_config(SAMPLE_GYEONGNAM_CONFIG)
        metrics = monitor_all_channels(chan_config)
        return {
            "candidate": chan_config.candidate_name,
            "channels": [
                {
                    "channel": m.channel,
                    "url": m.url,
                    "status": m.status,
                    "followers": m.followers,
                    "recent_posts": m.recent_posts,
                    "engagement": m.recent_engagement,
                    "top_content": m.top_content[:5],
                    "note": m.note,
                    "last_updated": m.last_updated,
                }
                for m in metrics
            ],
            "config": {
                "facebook": chan_config.facebook_id or "미설정",
                "youtube": chan_config.youtube_channel or "미설정",
                "instagram": chan_config.instagram_id or "미확인",
            },
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# SNS Battle — 우리+상대 후보 SNS 채널 비교
# ---------------------------------------------------------------------------

@app.get("/api/sns-battle")
async def api_sns_battle(session_token: str = Cookie(default=None)):
    """우리 후보 vs 상대 후보 SNS 채널 비교 데이터."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.owned_channels import monitor_all_candidates
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        all_metrics = monitor_all_candidates(config)

        candidates = {}
        for name, metrics in all_metrics.items():
            total_posts = sum(m.recent_posts for m in metrics)
            total_engagement = sum(m.recent_engagement for m in metrics)
            total_followers = sum(m.followers for m in metrics)
            candidates[name] = {
                "channels": [
                    {
                        "channel": m.channel,
                        "url": m.url,
                        "status": m.status,
                        "followers": m.followers,
                        "recent_posts": m.recent_posts,
                        "engagement": m.recent_engagement,
                        "top_content": m.top_content[:3],
                        "note": m.note,
                        "themes": m.message_themes,
                    }
                    for m in metrics
                ],
                "total_posts": total_posts,
                "total_engagement": total_engagement,
                "total_followers": total_followers,
            }

        # 비교 요약
        our = candidates.get(config.candidate_name, {})
        opp_name = config.opponents[0] if config.opponents else ""
        opp = candidates.get(opp_name, {})
        summary = {
            "our_posts": our.get("total_posts", 0),
            "opp_posts": opp.get("total_posts", 0),
            "our_engagement": our.get("total_engagement", 0),
            "opp_engagement": opp.get("total_engagement", 0),
            "our_followers": our.get("total_followers", 0),
            "opp_followers": opp.get("total_followers", 0),
            "post_ratio": round(our.get("total_posts", 0) / max(opp.get("total_posts", 0), 1), 2),
            "engagement_ratio": round(our.get("total_engagement", 0) / max(opp.get("total_engagement", 0), 1), 2),
        }

        return {
            "candidate": config.candidate_name,
            "opponent": opp_name,
            "candidates": candidates,
            "summary": summary,
            "sns_config": {
                "candidate_sns": config.candidate_sns,
                "opponent_profiles": config.opponent_profiles,
            },
            "timestamp": datetime.now().isoformat(),
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Keyword Deep Analysis — 키워드 클릭 시 상세 분석
# ---------------------------------------------------------------------------

@app.get("/api/keyword-analysis/{keyword}")
async def api_keyword_analysis(keyword: str, session_token: str = Cookie(default=None)):
    """키워드 하나에 대한 심층 분석: 연관 단어, 감정 톤, 프레임"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.keyword_analyzer import analyze_keyword
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        result = analyze_keyword(
            keyword,
            candidate_name=config.candidate_name,
            opponents=config.opponents,
        )
        return {
            "keyword": result.keyword,
            "total_analyzed": result.total_analyzed,
            "co_words": result.co_words[:15],
            "bigrams": result.bigrams[:8],
            "tone": {
                "dominant": result.dominant_tone,
                "score": result.tone_score,
                "distribution": result.tone_distribution,
            },
            "frames": result.frames,
            "narratives": result.key_narratives[:5],
            "who_talks": result.who_talks,
            "about_whom": result.about_whom,
            "samples": {
                "news": result.news_samples[:5],
                "blog": result.blog_samples[:5],
                "cafe": result.cafe_samples[:5],
            },
            "data_freshness": result.data_freshness,
            "ai_analysis": {
                "sentiment": result.ai_sentiment,
                "score": result.ai_score,
                "summary": result.ai_summary,
                "risk": result.ai_risk,
                "opportunity": result.ai_opportunity,
                "source": result.ai_source,
            },
            "google_trends": {
                "interest": result.trend_interest,
                "change_7d": result.trend_change_7d,
                "direction": result.trend_direction,
                "related": result.trend_related,
            },
            "youtube": {
                "count": result.yt_count,
                "views": result.yt_views,
                "top": result.yt_top,
            },
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Issue Response — 이슈별 대응 전략 (키워드 엔진 연동)
# ---------------------------------------------------------------------------

def _build_guide():
    return {
        "stances": {
            "push": {"label": "밀기", "color": "#4caf50", "icon": "🟢", "desc": "우리에게 유리 → 적극 확산"},
            "counter": {"label": "반박", "color": "#f44336", "icon": "🔴", "desc": "불리하지만 대응 필요 → 반박 후 전환"},
            "avoid": {"label": "회피", "color": "#616161", "icon": "⚫", "desc": "대응할수록 손해 → 침묵"},
            "monitor": {"label": "모니터링", "color": "#ffeb3b", "icon": "🟡", "desc": "아직 작음 → 확산 감시"},
            "pivot": {"label": "전환", "color": "#2196f3", "icon": "🔵", "desc": "중립 이슈 → 우리 프레임으로 전환"},
        },
        "lifecycle": {
            "emerging": "태동 — 선점 기회",
            "growing": "성장 — 지금 대응하면 프레임 장악",
            "peak": "정점 — 최대 효과/위험",
            "declining": "하락 — 재점화 주의",
            "dormant": "소멸 — 모니터링만",
        },
        "urgency": {"즉시": "1-2시간 내", "당일": "6시간 내", "48시간": "2일 내", "모니터링": "추적만"},
        "how_it_works": "1.키워드수집 → 2.스코어링 → 3.감성분석 → 4.입장결정 → 5.대응메시지 → 6.담당배정",
    }


def _build_issue_response_result(responses, unified, config):
    return {
        "responses": [
            {
                "keyword": r.keyword, "score": r.score, "level": r.level.name,
                "stance": r.stance, "stance_reason": r.stance_reason,
                "owner": r.owner, "urgency": r.urgency, "golden_time": r.golden_time_hours,
                "response_message": r.response_message, "talking_points": r.talking_points,
                "do_not_say": r.do_not_say, "related_pledges": r.related_pledges,
                "pivot_to": r.pivot_to, "lifecycle": r.lifecycle,
                "trend": r.trend_direction, "duration": r.estimated_duration,
                "scenario_best": r.scenario_best, "scenario_worst": r.scenario_worst,
                "channels": {
                    "news": u.news_mentions if u else 0,
                    "blog": u.blog_recent if u else 0,
                    "cafe": u.cafe_recent if u else 0,
                    "video": u.video_recent if u else 0,
                    "total": u.total_mentions if u else 0,
                    "prev_total": u.prev_total if u else 0,
                    "change": u.change_count if u else 0,
                    "change_pct": u.change_pct if u else 0,
                    "youtube": u.yt_recent_7d if u else 0,
                    "yt_views": u.yt_total_views if u else 0,
                } if (u := next((x for x in unified if x.keyword == r.keyword), None)) or True else {},
                "top_blogs": [b.get("title", "")[:50] for b in (u.top_blogs if u else [])],
                "top_cafe": [c.get("title", "")[:50] for c in (u.top_cafe_posts if u else [])],
                "top_youtube": [v.get("title", "")[:50] for v in (u.yt_top_videos[:3] if u else [])],
                "trend_data": {
                    "interest": u.trend_interest if u else 0,
                    "change_7d": u.trend_change_7d if u else 0,
                    "direction": u.trend_direction if u else "",
                    "related": u.trend_related if u else [],
                } if u else {},
            }
            for r in responses
        ],
        "guide": _build_guide(),
        "timestamp": datetime.now().isoformat(),
    }


# 이슈 대응 결과 서버 캐시 (전략 갱신 시 업데이트)
_issue_response_cache = {"data": None, "timestamp": ""}

# V2 엔진 enrichment 캐시 (전략 갱신 시 업데이트)
_v2_enrichment_cache = None

_ENRICHMENT_SNAPSHOT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "enrichment_snapshot.json"
)


def _save_enrichment_snapshot():
    """_v2_enrichment_cache를 JSON 파일로 저장."""
    global _v2_enrichment_cache
    if not _v2_enrichment_cache:
        return
    try:
        os.makedirs(os.path.dirname(_ENRICHMENT_SNAPSHOT_PATH), exist_ok=True)
        with open(_ENRICHMENT_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(_v2_enrichment_cache, f, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[EnrichmentSnapshot] Save failed: {e}")


def _load_enrichment_snapshot():
    """JSON 파일에서 _v2_enrichment_cache를 복원."""
    global _v2_enrichment_cache
    if not os.path.exists(_ENRICHMENT_SNAPSHOT_PATH):
        return
    try:
        with open(_ENRICHMENT_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            _v2_enrichment_cache = json.load(f)
        print(f"[EnrichmentSnapshot] Restored from {_ENRICHMENT_SNAPSHOT_PATH}")
    except Exception as e:
        print(f"[EnrichmentSnapshot] Load failed: {e}")


_load_enrichment_snapshot()


# ---------------------------------------------------------------------------
# News Clustering — 전략 갱신 시 자동 실행
# ---------------------------------------------------------------------------

_CLUSTER_RULES = [
    ("정청래 봉하 방문 + 검찰청 폐지", ["정청래", "봉하", "검찰청 폐지", "노무현"], "우리 측"),
    ("경남도 추경 + 도민생활지원금", ["추경", "4897", "민생지원금", "생활지원금", "추가경정"], "상대 측 (현직)"),
    ("국힘 내부 갈등 (컷오프/반발)", ["컷오프", "주호영", "이진숙", "반윤"], "상대 내부"),
    ("김경수 vs 박완수 행보", ["도민 밀착", "도정 집중", "광폭 행보", "전·현직"], "양측"),
    ("김해 컨벤션 허브 발표", ["컨벤션", "화목지구"], "상대 측 (현직)"),
    ("AI 통합돌봄", ["통합돌봄", "AI 돌봄", "4중 돌봄"], "상대 측 (현직)"),
    ("경남 군수 예비후보 등록", ["군수 예비후보", "39명 등록"], "중립"),
    ("이재명/민주당 경남 방문", ["이재명.*경남", "민주당.*경남.*방문", "동부경남.*압승"], "우리 측"),
    ("김부겸 대구 출마", ["김부겸", "대구.*출마", "필승 카드"], "우리 측"),
    ("AI 로봇 산업 투자", ["AI로봇", "AI 로봇", "피지컬 AI", "로봇 산업"], "상대 측 (현직)"),
    ("경남 북극항로 정책", ["북극항로"], "상대 측 (현직)"),
    ("정부 추경", ["25조", "정부.*추경"], "우리 측"),
    ("안전/치안 공약", ["안전.*치안", "치안.*공약"], "중립"),
    ("공천 부정행위", ["커닝", "부정행위"], "상대 내부"),
    ("경남 원전", ["원전.*건설", "신규원전"], "중립"),
]


def _run_news_clustering(config):
    """뉴스 클러스터링 — 24시간 내 기사 수집 → 사건별 묶기."""
    import re as _re
    from collectors.naver_news import search_news
    from collectors.api_cache import wait_if_needed, record_call

    candidate = config.candidate_name
    opponents = config.opponents or []
    opponent = opponents[0] if opponents else ""
    region = config.region.replace("경상남도", "경남")

    queries = [
        f"{region}도지사", candidate, opponent,
        f"{region} 추경", f"{region} 민생지원금",
        f"국민의힘 {region}", f"민주당 {region}",
        f"정청래 {region}", f"이재명 {region}",
        f"{region} AI", f"{region} 청년",
        f"{region} 공천", f"{region}도 발표",
    ]

    # 수집 (API 레이트 리밋 준수)
    seen_titles = set()
    all_articles = []
    from email.utils import parsedate_to_datetime
    for q in queries:
        try:
            wait_if_needed("naver_news")
            articles = search_news(q, display=100, pages=1)
            record_call("naver_news")
            for a in articles:
                try:
                    pub = parsedate_to_datetime(a["pub_date"])
                    _KST = timezone(timedelta(hours=9))
                    now_kst = datetime.now(_KST)
                    cutoff = now_kst - timedelta(hours=24)
                    if pub > cutoff and a["title"] not in seen_titles:
                        seen_titles.add(a["title"])
                        all_articles.append(a)
                except Exception:
                    pass
        except Exception as e:
            print(f"[NewsClustering] query '{q}' failed: {e}")

    # 클러스터링
    clusters: dict[str, dict] = {}
    for a in all_articles:
        for cluster_name, keywords, side in _CLUSTER_RULES:
            matched = False
            for kw in keywords:
                if _re.search(kw, a["title"]):
                    if cluster_name not in clusters:
                        clusters[cluster_name] = {
                            "name": cluster_name, "side": side,
                            "count": 0, "articles": [],
                        }
                    clusters[cluster_name]["count"] += 1
                    if len(clusters[cluster_name]["articles"]) < 3:
                        clusters[cluster_name]["articles"].append({
                            "title": a["title"],
                            "source": a.get("source", ""),
                        })
                    matched = True
                    break
            if matched:
                break

    # 정렬
    sorted_clusters = sorted(clusters.values(), key=lambda x: x["count"], reverse=True)

    # 진영 영향도 자동 판정 (현직=상대 유리 원칙 적용)
    for c in sorted_clusters:
        side = c["side"]
        cnt = c["count"]
        if side == "상대 측 (현직)":
            c["our_impact"] = -1 if cnt < 20 else -2
            c["opp_impact"] = +2 if cnt < 20 else +3
            c["direction"] = "역공" if cnt >= 10 else "모니터링"
        elif side == "상대 내부":
            c["our_impact"] = +1
            c["opp_impact"] = -2 if cnt >= 10 else -1
            c["direction"] = "방치"
        elif side == "우리 측":
            c["our_impact"] = +2 if cnt >= 10 else +1
            c["opp_impact"] = -1 if cnt >= 20 else 0
            c["direction"] = "선점"
        else:
            c["our_impact"] = 0
            c["opp_impact"] = 0
            c["direction"] = "모니터링"

        # 긴급도
        if cnt >= 30:
            c["urgency"] = "즉시"
        elif cnt >= 10:
            c["urgency"] = "오늘 내"
        elif cnt >= 5:
            c["urgency"] = "이번 주"
        else:
            c["urgency"] = "모니터링"

    print(f"[NewsClustering] {len(all_articles)}건 수집 → {len(sorted_clusters)}개 클러스터")
    return sorted_clusters


# 수집 데이터 글로벌 캐시 — 10분 스캔에서도 이전 수집 데이터 재사용
_collected_data_cache = {
    "youtube_data": {},       # {keyword: YouTubeSignal}
    "social_data": {},        # {keyword: {"blog": SocialSignal, "cafe": SocialSignal}}
    "community_data": {},     # {keyword: CommunityReport}
    "trends_data": {},        # {keyword: TrendSignal}
    "naver_trend_data": {},   # {keyword: NaverTrendSignal}
    "ai_sentiment_data": {},  # {keyword: AISentimentResult}
    "yt_comment_data": {},    # {keyword: YouTubeCommentReport}
    "updated_at": "",
}

# 수집기/엔진 마지막 실행 시각 레지스트리
_last_run_registry: dict = {}  # {"naver_news": "2026-03-21T20:15:33", ...}

def _mark_run(name: str):
    """수집기/엔진 실행 시각 기록."""
    from datetime import datetime
    _last_run_registry[name] = datetime.now().isoformat()

@app.get("/api/v2/org-scan")
async def api_v2_org_scan(session_token: str = Cookie(default=None)):
    """조직 landscape 전체 스캔 — 경남 주요 단체의 정치적 움직임."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.org_signal_detector import scan_org_landscape, ORG_DATABASE
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        results = scan_org_landscape(
            candidate_name=config.candidate_name,
            opponents=config.opponents,
        )
        return {
            "org_database": len(ORG_DATABASE),
            "scanned": len(results),
            "with_signals": sum(1 for r in results if r.signals),
            "results": [r.to_dict() for r in results if r.signals],
            "timestamp": datetime.now().isoformat(),
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v2/enrichment")
async def api_v2_enrichment(session_token: str = Cookie(default=None)):
    """V2 엔진 enrichment 데이터 — score breakdown, readiness, anomaly, mode decision."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    if not _v2_enrichment_cache:
        return {
            "issue_indices": {}, "reaction_indices": {}, "segments": {},
            "score_explanations": [], "readiness": {}, "anomalies": {},
            "youtube_comments": {}, "mode_decision": None, "timestamp": None,
        }
    return _v2_enrichment_cache


@app.get("/api/v2/forecast")
async def api_v2_forecast(session_token: str = Cookie(default=None)):
    """V2 Forecast — 지지율 변화 예측 + 래그 분석 + 학습 피드백."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    if not _v2_enrichment_cache:
        return {"leading_index": None, "lag_analysis": None, "forecast": None, "learning": None}
    return {
        "leading_index": _v2_enrichment_cache.get("leading_index"),
        "lag_analysis": _v2_enrichment_cache.get("lag_analysis"),
        "forecast": _v2_enrichment_cache.get("forecast"),
        "learning": _v2_enrichment_cache.get("learning"),
    }


@app.get("/api/v2/research-report")
async def api_research_report(session_token: str = Cookie(default=None)):
    """여론 영향 요인 분석 — 인쇄용 HTML 보고서."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>여론조사 영향 요인 분석 리포트</title>
<style>
@page { size: A4; margin: 20mm 15mm; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Apple SD Gothic Neo','Malgun Gothic',sans-serif; font-size:10px; color:#222; line-height:1.6; background:#fff; }
.page { page-break-after: always; padding: 10px 0; }
.page:last-child { page-break-after: auto; }
h1 { font-size:18px; color:#1a237e; border-bottom:3px solid #1a237e; padding-bottom:8px; margin-bottom:15px; }
h2 { font-size:13px; color:#1a237e; margin:15px 0 8px; padding:6px 10px; background:#e8eaf6; border-radius:4px; }
h3 { font-size:11px; color:#333; margin:10px 0 5px; }
.meta { color:#666; font-size:9px; margin-bottom:15px; }
.matrix { width:100%; border-collapse:collapse; margin:10px 0; font-size:9px; }
.matrix th { background:#1a237e; color:#fff; padding:6px 8px; text-align:left; }
.matrix td { padding:5px 8px; border-bottom:1px solid #e0e0e0; }
.matrix tr:nth-child(even) { background:#f5f5f5; }
.impact { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:1px; }
.impact.on { background:#f59e0b; }
.impact.off { background:#e0e0e0; }
.card { border:1px solid #e0e0e0; border-radius:6px; padding:10px; margin:8px 0; }
.card-title { font-size:11px; font-weight:bold; color:#1a237e; margin-bottom:5px; }
.evidence { background:#fff8e1; border-left:3px solid #f59e0b; padding:6px 10px; margin:5px 0; font-size:9px; }
.mechanism { background:#e3f2fd; border-left:3px solid #1976d2; padding:6px 10px; margin:5px 0; font-size:9px; }
.gap-good { background:#e8f5e9; border-left:3px solid #4caf50; padding:6px 10px; margin:5px 0; font-size:9px; }
.gap-bad { background:#fce4ec; border-left:3px solid #e53935; padding:6px 10px; margin:5px 0; font-size:9px; }
.source { font-size:8px; color:#666; margin:2px 0; }
.source a { color:#1976d2; }
.summary-box { display:flex; gap:10px; margin:10px 0; }
.summary-item { flex:1; text-align:center; padding:10px; border-radius:6px; }
.summary-item.good { background:#e8f5e9; border:1px solid #4caf50; }
.summary-item.warn { background:#fff8e1; border:1px solid #f59e0b; }
.summary-item.bad { background:#fce4ec; border:1px solid #e53935; }
.summary-item .num { font-size:24px; font-weight:900; }
.footer { text-align:center; color:#999; font-size:8px; margin-top:20px; padding-top:10px; border-top:1px solid #e0e0e0; }
@media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>

<div class="page">
<h1>🔬 여론조사에 영향을 미치는 7대 요인 분석</h1>
<div class="meta">
Election Engine Research Report | 제9대 경남도지사 선거 | """ + datetime.now().strftime("%Y.%m.%d") + """ 생성<br>
학술논문 4건 + 해외연구 4건 + 캠프내부 전략보고서 4건 종합
</div>

<h2>1. 영향 요인 × 엔진 커버리지 매트릭스</h2>
<table class="matrix">
<tr><th>요인</th><th>영향</th><th>측정</th><th>핵심 GAP</th></tr>
<tr><td>🏛 중앙정치 환경 (대통령·정당)</td><td>⭐⭐⭐⭐⭐</td><td>⚠ 부분</td><td>대통령 지지율 자동 연동 필요</td></tr>
<tr><td>🎯 후보 이벤트 (발표·방문·토론)</td><td>⭐⭐⭐⭐⭐</td><td>✅ 충분</td><td>이벤트 임팩트 정량화</td></tr>
<tr><td>📺 미디어 프레이밍 (뉴스 톤·분량)</td><td>⭐⭐⭐⭐</td><td>✅ 충분</td><td>지역 언론 톤 별도 트래킹</td></tr>
<tr><td>💰 경제 체감 (물가·일자리·부동산)</td><td>⭐⭐⭐⭐</td><td>⚠ 부분</td><td>KOSIS 경제지표 자동 수집</td></tr>
<tr><td>🏗 조직 동원 (노조·종교·맘카페)</td><td>⭐⭐⭐</td><td>✅ 충분</td><td>동원→투표율 정량화</td></tr>
<tr><td>⚔ 상대 캠프 행동 (선점·공격)</td><td>⭐⭐⭐⭐</td><td>✅ 충분</td><td>Pre-Trigger 정확도 검증</td></tr>
<tr><td>🗳 투표율 변수 (세대별·지역별)</td><td>⭐⭐⭐⭐⭐</td><td>❌ 미측정</td><td><b>가장 큰 GAP — 당락 결정</b></td></tr>
</table>

<div class="summary-box">
<div class="summary-item good"><div class="num" style="color:#4caf50">4/7</div><div>충분히 측정</div><div style="font-size:8px;color:#666">후보이벤트, 미디어, 조직, 상대행동</div></div>
<div class="summary-item warn"><div class="num" style="color:#f59e0b">2/7</div><div>부분 측정</div><div style="font-size:8px;color:#666">중앙정치, 경제체감</div></div>
<div class="summary-item bad"><div class="num" style="color:#e53935">1/7</div><div>미측정</div><div style="font-size:8px;color:#666">투표율 변수 (당락 결정)</div></div>
</div>
</div>

<div class="page">
<h2>2. 요인별 상세 분석</h2>

<h3>🏛 ① 중앙정치 환경 — 대통령·정당 프리미엄</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐⭐⭐ (매우 큼) — 지방선거 판세의 약 50%를 결정</div>
<p>새 정부 임기 초반의 '대통령 효과'가 여당 후보를 견인. 대통령 지지율과 지방선거 득표율 상관 0.7~0.9.</p>
<div class="evidence">
<b>경남 적용 근거:</b><br>
▸ 7대(2018): 문재인 78% → 김경수 52.8% 당선<br>
▸ 8대(2022): 윤석열 52% → 박완수 65.7% 당선<br>
▸ 경남 민주당 득표율 하락폭 전국 2위(-23.38%p)
</div>
<div class="mechanism"><b>메커니즘:</b> 대통령 지지율 ↑ → 여당 정당 지지율 ↑ → 여당 후보 지지율 ↑</div>
<div class="gap-bad"><b>GAP:</b> 대통령/정당 지지율 주간 자동 수집 → Leading Index 반영 필요</div>
<div class="source">📄 한국갤럽 대통령 직무수행 평가 | 📋 제9대 경남도지사 승리 전략 보고서</div>
</div>

<h3>🎯 ② 후보 이벤트 — 정책발표·방문·토론·스캔들</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐⭐⭐ (매우 큼) — 가장 직접적이고 빠른 영향</div>
<p>정책 발표(+2~5%p), TV 토론(±3~10%p), 스캔들(-3~8%p)로 단기간 큰 변동.</p>
<div class="evidence">
<b>경남 적용 근거:</b><br>
▸ 박완수 단수공천 → 네이버 검색 278% 급등<br>
▸ 사법리스크 프레임 → 현재 7건 모니터링 중<br>
▸ 민생지원금 사건: 도청 보도자료 감지 실패 → 선점 불가
</div>
<div class="mechanism"><b>메커니즘:</b> 후보 행동 → 미디어 보도 → 유권자 인지 → 여론 변화 (1~7일 lag)</div>
<div class="gap-good"><b>엔진 현황:</b> Issue/Reaction Index + Attribution + Pre-Trigger로 감지 ✅</div>
<div class="source">📄 <a href="https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002212933">제20대 총선 투표행태 영향 요인 연구 (KCI)</a> | 📋 경남대전환 Trend Report</div>
</div>

<h3>📺 ③ 미디어 프레이밍 — 뉴스 톤·분량·Horse Race</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐⭐ (큼) — 유권자 인식을 결정하는 프레임</div>
<p>승자편승 효과(앞선 후보에 투표 경향)와 프레임 전쟁(변화 vs 안정)이 핵심.</p>
<div class="evidence">
<b>경남 적용 근거:</b><br>
▸ 김경수 프레임: '변화 리더십' | '경제 공약' | '지역 주도'<br>
▸ 박완수 프레임: '안정 행정' | '경험' | '안전'<br>
▸ 빅카인즈: 김경수 652건 vs 박완수 796건 (노출량 열세 22%)
</div>
<div class="mechanism"><b>메커니즘:</b> 미디어 노출량 ↑ → 인지도 ↑ → 지지율 ↑ (부정 보도 시 역효과)</div>
<div class="gap-good"><b>엔진 현황:</b> AI 감성(Claude) 프레임/톤/위험/기회 감지 ✅</div>
<div class="source">📄 <a href="https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART001250499">대중매체 후보이미지 형성 연구 (KCI)</a> | 🌐 <a href="https://journalism.uoregon.edu/news/six-ways-media-influences-elections">Six ways media influences elections (Oregon)</a> | 🌐 <a href="https://www.gsb.stanford.edu/insights/how-polls-influence-behavior">How Polls Influence Behavior (Stanford)</a></div>
</div>
</div>

<div class="page">
<h3>💰 ④ 경제 체감 — 물가·일자리·부동산</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐⭐ (큼) — 현직에 대한 성과 평가</div>
<p>유권자가 체감하는 경제 상황이 현직 평가를 결정. 경남은 조선업 경기, 물가, 부동산이 직접 변수.</p>
<div class="evidence">
<b>경남 적용 근거:</b><br>
▸ 한국인 투표 최우선 영향 요인 = 경제 이슈 (KCI 실증 연구)<br>
▸ 조선업 호황 → 거제/창원 고용 개선 → 현직(박완수) 유리 요소<br>
▸ 물가 상승 체감 → 현직 불만 → 도전자(김경수) 유리 요소
</div>
<div class="mechanism"><b>메커니즘:</b> 경제 체감 악화 → 현직 책임론 → 도전자 유리 / 개선 → 현직 유리</div>
<div class="gap-bad"><b>GAP:</b> KOSIS 경남 고용률/물가지수 자동 수집 → Leading Index 반영 필요</div>
<div class="source">🌐 <a href="https://www.mdpi.com/2076-0760/12/9/469">Factors Influencing Voting Decision (MDPI)</a> | 📄 <a href="https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002934928">2022 지방선거 투표행태 결정요인 (KCI)</a></div>
</div>

<h3>🏗 ⑤ 조직 동원 — 노조·종교·맘카페·향우회</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐ (보통~큼) — 실제 투표율에 직접 영향</div>
<p>조직적 지지선언과 투표 동원이 투표율과 득표율에 직접 영향. 경남에서 민주노총(5만), 맘카페(25만)의 영향력이 특히 큼.</p>
<div class="evidence">
<b>경남 적용 근거:</b><br>
▸ 7대: 창원 성산구 노동계 밀집지 김경수 62% (최고 득표)<br>
▸ 창원줌마렐라(25만) = 경남 최대 여론 채널 (캠프 보고서)<br>
▸ 맘카페를 '여론의 입법부'로 규정 (캠프 전략 보고서)
</div>
<div class="gap-good"><b>엔진 현황:</b> 25개 단체 + 맘카페 5곳 + 커뮤니티 22곳 세분화 ✅</div>
<div class="source">📋 경남 맘카페 초밀착 공략 방안 | 📋 제9대 승리 전략 보고서</div>
</div>

<h3>⚔ ⑥ 상대 캠프 행동 — 정책선점·네거티브·실수</h3>
<div class="card">
<div class="card-title">영향: ⭐⭐⭐⭐ (큼) — 사전 감지 실패 시 선점 기회 상실</div>
<p>상대 캠프의 정책 선점, 네거티브 공격이 여론을 급변시킬 수 있다.</p>
<div class="evidence">
<b>경남 적용 근거 (실제 사례):</b><br>
▸ 민생지원금 사건: 도청 보도자료 + 기자 엠바고 → 감지 실패 → 선점 불가<br>
▸ → Pre-Trigger Layer 신규 구축: 도청/상대SNS/기자단/정책선점 4채널 감지
</div>
<div class="gap-good"><b>엔진 현황:</b> Pre-Trigger(신규) — 17개 정책 키워드 선점 경고 ✅</div>
<div class="source">🌐 <a href="https://link.springer.com/article/10.1007/s11129-025-09300-y">Persuasion in political campaigns (Springer)</a></div>
</div>

<h3>🗳 ⑦ 투표율 변수 — 세대별·지역별 참여율 (⚠ 최대 GAP)</h3>
<div class="card" style="border:2px solid #e53935">
<div class="card-title" style="color:#e53935">영향: ⭐⭐⭐⭐⭐ (매우 큼) — 당락을 결정하는 최대 변수</div>
<p>같은 지지율이라도 투표율에 따라 결과가 뒤집힌다. 경남 3040 투표율 5%p 상승 = 약 5만표(≈2.5%p) 추가.</p>
<div class="evidence">
<b>경남 적용 근거 (승리 전략 보고서):</b><br>
▸ 2030세대: 50.5% → 37.7% (7년간 -12.8%p 급감)<br>
▸ 60대 이상: 27.5% → 39.5% (+12%p 폭발적 증가)<br>
▸ → 인구 구조만으로 약 13~14만표를 잃고 시작<br>
▸ 3040 지지율 최고이나 투표율 최저 — 사전투표 캠페인 필수
</div>
<div class="mechanism"><b>메커니즘:</b><br>
전체 투표율 ↑ → 무당층 참여 ↑ → 변화 요구 ↑ → 도전자 유리<br>
청년 투표율 ↑ → 민주당 유리 / 농촌 고령 투표율 ↑ → 국힘 유리</div>
<div class="gap-bad"><b>GAP:</b> 투표율 예측 모델 완전 미구현. 사전투표 모니터링, 세대별 투표율 추정 필요.</div>
<div class="source">📄 <a href="https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001519807">지방선거 투표율의 결정요인 연구 (KCI)</a> | 📄 <a href="https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE02380495">선거별 투표율 결정 요인 1987~2010 (한국정당학회보)</a> | 📋 제9대 승리 전략 보고서</div>
</div>
</div>

<div class="page">
<h2>3. Leading Index 예측 정확도 향상 우선순위</h2>
<table class="matrix">
<tr><th>우선순위</th><th>개선 항목</th><th>예상 효과</th><th>난이도</th></tr>
<tr><td>①</td><td><b style="color:#e53935">투표율 예측 모델</b></td><td>당락 결정 변수 — 예측 정확도 +20~30%</td><td>높음</td></tr>
<tr><td>②</td><td><b style="color:#f59e0b">대통령/정당 지지율 자동 연동</b></td><td>판세의 50% — 기본 지형 파악</td><td>중간</td></tr>
<tr><td>③</td><td><b style="color:#f59e0b">경제 지표 자동 수집</b></td><td>현직 평가 핵심 변수</td><td>중간</td></tr>
<tr><td>④</td><td>이벤트 임팩트 정량화</td><td>정책발표 +3%p vs TV토론 +8%p 차등</td><td>중간</td></tr>
<tr><td>⑤</td><td>지역 언론 톤 트래킹</td><td>경남신문/KNN 톤 별도 분석</td><td>소</td></tr>
</table>

<h2>4. 연구 출처 전체 목록</h2>
<table class="matrix">
<tr><th>유형</th><th>제목</th><th>출처</th></tr>
<tr><td>📄 학술</td><td>제20대 총선 유권자 투표행태 영향 요인 연구</td><td>KCI ART002212933</td></tr>
<tr><td>📄 학술</td><td>지역유권자의 투표행태와 후보자 결정요인 (2022 지방선거)</td><td>KCI ART002934928</td></tr>
<tr><td>📄 학술</td><td>대중매체의 후보이미지 형성 및 유권자 투표행위 연구</td><td>KCI ART001250499</td></tr>
<tr><td>📄 학술</td><td>지방선거 투표율의 결정요인 연구</td><td>KCI ART001519807</td></tr>
<tr><td>🌐 해외</td><td>How Polls Influence Behavior</td><td>Stanford GSB</td></tr>
<tr><td>🌐 해외</td><td>Six ways the media influences elections</td><td>U of Oregon</td></tr>
<tr><td>🌐 해외</td><td>Factors Influencing Voting Decision</td><td>MDPI Social Sciences</td></tr>
<tr><td>🌐 해외</td><td>Persuasion and dissuasion in political campaigns</td><td>Springer Nature</td></tr>
<tr><td>📋 내부</td><td>제9대 경남도지사 선거 승리 전략 보고서</td><td>캠프 전략팀 260315</td></tr>
<tr><td>📋 내부</td><td>경남대전환을 위한 Trend Report 01</td><td>캠프 데이터팀 260320</td></tr>
<tr><td>📋 내부</td><td>경남 맘카페 초밀착 공략 방안</td><td>캠프 전략팀</td></tr>
<tr><td>📋 내부</td><td>중도·진보 주요 커뮤니티 20선</td><td>캠프 전략팀</td></tr>
</table>

<div class="footer">
Election Engine Research Report | AI 기반 분석이며 참고용 | """ + datetime.now().strftime("%Y.%m.%d %H:%M") + """ 생성<br>
학술논문 4건 + 해외연구 4건 + 캠프내부 전략보고서 4건 종합
</div>
</div>

</body></html>"""

    return HTMLResponse(content=html)


@app.get("/api/v2/turnout-prediction")
async def api_turnout_prediction(session_token: str = Cookie(default=None)):
    """투표율 예측 + 후보별 예상 득표수 + 시나리오."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    if _v2_enrichment_cache and _v2_enrichment_cache.get("turnout"):
        return _v2_enrichment_cache["turnout"]
    return {"base": None, "scenarios": [], "sensitivity": [], "strategic_insight": "전략 갱신 후 표시"}


@app.get("/api/v2/national-poll")
async def api_national_poll(session_token: str = Cookie(default=None)):
    """대통령/정당 지지율 최신 + 시계열."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from collectors.national_poll_collector import get_latest_national_poll, get_national_poll_trend
    latest = get_latest_national_poll()
    trend = get_national_poll_trend()
    return {"latest": latest.to_dict(), "trend": trend}


@app.get("/api/v2/event-impact")
async def api_event_impact(
    event_type: str = "policy",
    severity: str = "standard",
    is_our: bool = True,
    timing: str = "normal",
    session_token: str = Cookie(default=None),
):
    """이벤트 유형별 예상 여론 영향 정량화."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.event_impact import estimate_event_impact, estimate_all_event_impacts, EVENT_TYPES

    if event_type == "all":
        return {"events": estimate_all_event_impacts(
            is_our_event=is_our, severity=severity, timing=timing,
        )}

    result = estimate_event_impact(
        event_type=event_type,
        severity=severity,
        is_our_event=is_our,
        timing=timing,
    )
    return result.to_dict()


@app.get("/api/v2/event-impact/types")
async def api_event_types(session_token: str = Cookie(default=None)):
    """사용 가능한 이벤트 유형 목록."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.event_impact import EVENT_TYPES
    return {"types": [
        {"id": k, "label": v["label"], "icon": v["icon"],
         "base_impact": v["base_impact"], "range": v["range"]}
        for k, v in EVENT_TYPES.items()
    ]}


@app.get("/api/v2/regional-media")
async def api_regional_media(
    keyword: str = "김경수",
    session_token: str = Cookie(default=None),
):
    """경남 지역 언론 톤 분석."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.regional_media_collector import scan_regional_media
        return scan_regional_media(keyword).to_dict()

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    return result


@app.get("/api/v2/regional-media/compare")
async def api_regional_media_compare(session_token: str = Cookie(default=None)):
    """양 후보 지역 언론 톤 비교."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.regional_media_collector import scan_both_candidates
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opponent = config.opponents[0] if config.opponents else "박완수"
        return scan_both_candidates(config.candidate_name, opponent)

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    return result


@app.get("/api/v2/regional-media/list")
async def api_regional_media_list(session_token: str = Cookie(default=None)):
    """경남 지역 언론사 목록."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from collectors.regional_media_collector import get_media_list
    return {"media": get_media_list()}


@app.get("/api/v2/index-daily")
async def api_index_daily(
    date: str = "",
    session_token: str = Cookie(default=None),
):
    """일일 인덱스 요약 — 스냅샷 + 액션 임팩트 + 예측 정확도."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.index_tracker import generate_daily_summary
    return generate_daily_summary(date)


@app.get("/api/v2/system-health")
async def api_system_health():
    """시스템 전체 상태 점검 — 인증 불필요."""
    import importlib, time as _time
    from datetime import datetime
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

    result = {"checked_at": datetime.now().isoformat(), "engines": [], "collectors": [], "api_keys": [], "data_sources": [], "snapshots": {}, "last_run": dict(_last_run_registry), "errors": []}

    # 엔진 모듈
    for mod_name, func_name, label in [
        ("engines.issue_index", "compute_issue_index", "이슈 지수"),
        ("engines.reaction_index", "compute_reaction_index", "반응 지수"),
        ("engines.segment_mapper", "compute_segment_coverage", "세그먼트 커버리지"),
        ("engines.org_signal_detector", "extract_org_signals", "조직 시그널"),
        ("engines.reaction_attribution", "ReactionAttributor", "귀인 분석"),
        ("engines.leading_index_engine", "compute_leading_index", "선행지수"),
        ("engines.lag_correlator", "compute_lag_correlation", "Lag 상관"),
        ("engines.forecast_engine", "compute_forecast", "지지율 예측"),
        ("engines.learning_feedback", "build_feedback_profile", "학습 피드백"),
        ("engines.turnout_predictor", "predict_turnout", "투표율 예측"),
        ("engines.event_impact", "estimate_event_impact", "이벤트 임팩트"),
        ("engines.index_tracker", "save_daily_snapshot", "인덱스 트래커"),
        ("engines.ai_sentiment", "analyze_sentiment_ai", "AI 감성"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            getattr(mod, func_name)
            result["engines"].append({"name": label, "module": mod_name, "status": "ok"})
        except Exception as e:
            result["engines"].append({"name": label, "module": mod_name, "status": "error", "error": str(e)[:80]})
            result["errors"].append(f"엔진 {label}: {str(e)[:80]}")

    # 수집기
    for mod_name, func_name, label in [
        ("collectors.naver_news", "search_news", "네이버 뉴스"),
        ("collectors.community_collector", "scan_all_communities", "커뮤니티 22곳"),
        ("collectors.youtube_collector", "search_youtube", "유튜브"),
        ("collectors.trends_collector", "get_naver_trend", "네이버 DataLab"),
        ("collectors.unified_collector", "collect_unified_signals", "통합 수집"),
        ("collectors.national_poll_collector", "get_latest_national_poll", "대통령 지지율"),
        ("collectors.economic_collector", "get_latest_economic", "경제 지표"),
        ("collectors.pretrigger_collector", "scan_pretriggers", "Pre-Trigger"),
        ("collectors.regional_media_collector", "scan_regional_media", "지역 언론"),
        ("collectors.news_comment_collector", "fetch_keyword_comments", "뉴스 댓글"),
    ]:
        try:
            mod = importlib.import_module(mod_name)
            getattr(mod, func_name)
            result["collectors"].append({"name": label, "module": mod_name, "status": "ok"})
        except Exception as e:
            result["collectors"].append({"name": label, "module": mod_name, "status": "error", "error": str(e)[:80]})
            result["errors"].append(f"수집기 {label}: {str(e)[:80]}")

    # API 키
    for key, label in [
        ("NAVER_CLIENT_ID", "네이버 API"),
        ("YOUTUBE_API_KEY", "유튜브 API"),
        ("ANTHROPIC_API_KEY", "Claude AI"),
    ]:
        val = os.getenv(key, "")
        result["api_keys"].append({"name": label, "key": key, "status": "ok" if val else "missing", "preview": f"{val[:6]}...{val[-3:]}" if val else ""})
        if not val:
            result["errors"].append(f"API 키 {label} 미설정")

    # 정적 데이터
    try:
        from collectors.national_poll_collector import get_latest_national_poll
        np = get_latest_national_poll()
        result["data_sources"].append({"name": "대통령 지지율", "latest": np.date, "value": f"{np.president_approval}%", "status": "ok"})
    except Exception as e:
        result["data_sources"].append({"name": "대통령 지지율", "status": "error", "error": str(e)[:60]})

    try:
        from collectors.economic_collector import get_latest_economic
        ec = get_latest_economic()
        result["data_sources"].append({"name": "경제 지표", "latest": ec.date, "value": f"고용 {ec.employment_rate}%", "status": "ok"})
    except Exception as e:
        result["data_sources"].append({"name": "경제 지표", "status": "error", "error": str(e)[:60]})

    try:
        from engines.event_impact import EVENT_TYPES
        result["data_sources"].append({"name": "이벤트 유형", "latest": "상시", "value": f"{len(EVENT_TYPES)}개", "status": "ok"})
    except Exception as e:
        result["data_sources"].append({"name": "이벤트 유형", "status": "error", "error": str(e)[:60]})

    try:
        from collectors.regional_media_collector import REGIONAL_MEDIA
        result["data_sources"].append({"name": "지역 언론", "latest": "상시", "value": f"{len(REGIONAL_MEDIA)}개", "status": "ok"})
    except Exception as e:
        result["data_sources"].append({"name": "지역 언론", "status": "error", "error": str(e)[:60]})

    # 스냅샷
    data_dir = Path(os.path.dirname(os.path.dirname(__file__))) / "data" / "index_history"
    if data_dir.exists():
        snaps = sorted(data_dir.glob("snapshot_*.json"))
        result["snapshots"]["count"] = len(snaps)
        if snaps:
            result["snapshots"]["oldest"] = snaps[0].stem.replace("snapshot_", "")
            result["snapshots"]["newest"] = snaps[-1].stem.replace("snapshot_", "")
            result["snapshots"]["last_modified"] = datetime.fromtimestamp(snaps[-1].stat().st_mtime).isoformat()
            import json as _json
            with open(snaps[-1]) as _f:
                latest = _json.load(_f)
            result["snapshots"]["latest_li"] = latest.get("leading_index")
            result["snapshots"]["latest_quality"] = latest.get("data_quality")
    else:
        result["snapshots"]["count"] = 0
        result["errors"].append("스냅샷 디렉토리 없음")

    # 실시간 수집 테스트 (네이버 뉴스만 — 빠르므로)
    try:
        from collectors.naver_news import search_news
        arts = search_news("경남 선거", display=3, pages=1)
        result["live_test"] = {"status": "ok", "articles": len(arts), "latest_title": arts[0]["title"][:40] if arts else ""}
    except Exception as e:
        result["live_test"] = {"status": "error", "error": str(e)[:60]}
        result["errors"].append(f"실시간 수집 실패: {str(e)[:60]}")

    result["summary"] = {
        "engines_ok": sum(1 for e in result["engines"] if e["status"] == "ok"),
        "engines_total": len(result["engines"]),
        "collectors_ok": sum(1 for c in result["collectors"] if c["status"] == "ok"),
        "collectors_total": len(result["collectors"]),
        "api_keys_ok": sum(1 for k in result["api_keys"] if k["status"] == "ok"),
        "api_keys_total": len(result["api_keys"]),
        "error_count": len(result["errors"]),
        "overall": "healthy" if len(result["errors"]) == 0 else "degraded" if len(result["errors"]) <= 2 else "critical",
    }

    return result


@app.get("/api/v2/api-status")
async def api_api_status():
    """API 호출 상태 — rate limit, 캐시, 마지막 호출 시각."""
    from collectors.api_cache import get_all_status, API_CONFIG
    status = get_all_status()
    # _last_run_registry에서 마지막 수집 시각도 병합
    for s in status:
        api_key = next((k for k, v in API_CONFIG.items() if v.api_name == s["api"]), "")
        run_time = _last_run_registry.get(api_key, "")
        s["last_data_update"] = run_time[:19].replace("T", " ") if run_time else "—"
    return {"apis": status, "registry": dict(_last_run_registry)}


@app.get("/api/v2/auto-polls")
async def api_auto_polls(session_token: str = Cookie(default=None)):
    """자동 감지된 여론조사 목록 — 인증 불필요."""

    # 캐시에 있으면 반환
    cached = _v2_enrichment_cache.get("auto_polls") if _v2_enrichment_cache else None
    if cached:
        return {"polls": cached}

    # 캐시 없으면 즉시 수집 (백그라운드)
    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.poll_auto_collector import extract_polls_from_news
        return [p.to_dict() for p in extract_polls_from_news()]

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    return {"polls": result}


@app.get("/api/v2/ai-briefing")
async def api_ai_briefing(session_token: str = Cookie(default=None)):
    """AI 전략 브리핑."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    cached = _v2_enrichment_cache.get("ai_briefing") if _v2_enrichment_cache else None
    if cached:
        return cached
    return {"headline": "갱신 버튼을 눌러 AI 브리핑을 생성하세요", "situation": "", "issues": [], "risks": [], "opportunities": [], "tomorrow": []}


@app.get("/api/v2/index-trend")
async def api_index_trend(
    days: int = 30,
    session_token: str = Cookie(default=None),
):
    """인덱스 추세 (차트용) — 읽기 전용, 인증 불필요."""
    from engines.index_tracker import get_snapshot_trend
    return {"trend": get_snapshot_trend(days)}


@app.get("/api/v2/index-definitions")
async def api_index_definitions(session_token: str = Cookie(default=None)):
    """인덱스 정의 — 이름, 범위, 해석 가이드."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.index_tracker import INDEX_DEFINITIONS
    return {"definitions": INDEX_DEFINITIONS}


@app.get("/api/v2/prediction-accuracy")
async def api_prediction_accuracy(
    index_name: str = "support_forecast",
    session_token: str = Cookie(default=None),
):
    """예측 정확도 리포트 — 여론조사 vs 우리 예측."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.index_tracker import get_prediction_accuracy
    return get_prediction_accuracy(index_name)


@app.get("/api/v2/action-impacts")
async def api_action_impacts(
    date: str = "",
    session_token: str = Cookie(default=None),
):
    """오늘의 액션 임팩트 목록."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.index_tracker import get_action_impacts
    from datetime import date as dt
    if not date:
        date = dt.today().isoformat()
    return {"date": date, "impacts": get_action_impacts(date)}


@app.get("/api/v2/attribution")
async def api_attribution(session_token: str = Cookie(default=None)):
    """귀인 분석 결과 — 행동-반응 연결."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    cached = _v2_enrichment_cache.get("attribution")
    if cached:
        return cached
    return {"total_actions": 0, "attributed_count": 0, "message": "전략 갱신 후 표시"}


@app.get("/api/v2/segment-coverage")
async def api_segment_coverage(
    keyword: str = "김경수",
    session_token: str = Cookie(default=None),
):
    """이슈별 세그먼트 커버리지 점수."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    from engines.segment_mapper import analyze_segments, compute_segment_coverage
    breakdown = analyze_segments(keyword)
    coverage = compute_segment_coverage(breakdown)
    return {
        "breakdown": breakdown.to_dict(),
        "coverage": coverage.to_dict(),
    }


@app.get("/api/v2/news-comments")
async def api_news_comments(
    keyword: str = "김경수",
    max_articles: int = 5,
    session_token: str = Cookie(default=None),
):
    """뉴스 기사 댓글 수집 + 감성 분석."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.news_comment_collector import fetch_keyword_comments
        return fetch_keyword_comments(keyword, max_articles=min(max_articles, 10)).to_dict()

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    return result


@app.get("/api/v2/pretrigger-scan")
async def api_pretrigger_scan(session_token: str = Cookie(default=None)):
    """Pre-Trigger 스캔 — 상대 선제행동/정책선점/도청 모니터링."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.pretrigger_collector import scan_pretriggers
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opponent = config.opponents[0] if config.opponents else "박완수"

        # 최근 뉴스 제목도 전달 (정책 선점 검사용)
        recent_titles = []
        try:
            from collectors.naver_news import search_news
            for q in [f"{opponent} 정책", f"{opponent} 발표", "경남도 지원금"]:
                arts = search_news(q, display=10, pages=1)
                recent_titles.extend(a.get("title", "") for a in arts)
                import time as _t
                _t.sleep(0.3)
        except Exception:
            pass

        report = scan_pretriggers(
            opponent_name=opponent,
            opponent_sns=config.opponent_profiles.get(opponent, {}),
            our_pledges=config.pledges,
            recent_titles=recent_titles,
        )
        return report.to_dict()

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v2/keyword-compare")
async def api_keyword_compare(session_token: str = Cookie(default=None)):
    """후보별 연관어 + 감성 비교 분석."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.keyword_analyzer import analyze_keyword
        from engines.ai_sentiment import analyze_sentiment_ai
        from collectors.naver_news import search_news
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opponent = config.opponents[0] if config.opponents else "박완수"

        results = {}
        for name in [config.candidate_name, opponent]:
            # 연관어 분석
            ka = analyze_keyword(name, candidate_name=config.candidate_name, opponents=config.opponents)
            # 뉴스 제목 수집 → AI 감성
            articles = search_news(f"{name} 경남", display=30, pages=1)
            titles = [a.get("title", "") for a in articles]
            ai = analyze_sentiment_ai(titles, keyword=name, candidate_name=config.candidate_name, opponents=config.opponents)

            results[name] = {
                "co_words": [{"word": w["word"], "count": w["count"], "type": w.get("type", "")} for w in (ka.co_words or [])[:15]],
                "tone": {"dominant": ka.dominant_tone, "score": ka.tone_score, "distribution": ka.tone_distribution},
                "ai_sentiment": ai.to_dict(),
                "total_analyzed": ka.total_analyzed,
                "frames": (ka.frames or [])[:5],
                "narratives": [n.get("narrative", n) if isinstance(n, dict) else n for n in (ka.key_narratives or [])[:3]],
            }

        # 공통 연관어 (겹치는 단어)
        words_a = {w["word"] for w in results.get(config.candidate_name, {}).get("co_words", [])}
        words_b = {w["word"] for w in results.get(opponent, {}).get("co_words", [])}
        shared = list(words_a & words_b)

        return {
            "candidate": config.candidate_name,
            "opponent": opponent,
            "results": results,
            "shared_words": shared[:10],
            "timestamp": datetime.now().isoformat(),
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v2/naver-trend/{keyword}")
async def api_naver_trend(keyword: str, days: int = 30, session_token: str = Cookie(default=None)):
    """네이버 데이터랩 — 성별/연령별 검색 트렌드."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.trends_collector import get_naver_trend
        return get_naver_trend(keyword, days=days).to_dict()

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v2/naver-compare")
async def api_naver_compare(session_token: str = Cookie(default=None)):
    """네이버 데이터랩 — 김경수 vs 박완수 검색 트렌드 비교."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from collectors.trends_collector import get_naver_trend_compare
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opp = config.opponents[0] if config.opponents else "박완수"
        return get_naver_trend_compare(config.candidate_name, opp)

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/v2/lag-history")
async def api_v2_lag_history(session_token: str = Cookie(default=None)):
    """Leading Index + Polling 시계열 히스토리."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    try:
        from engines.lag_correlator import get_history_summary
        return get_history_summary()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/issue-responses")
async def api_issue_responses(session_token: str = Cookie(default=None)):
    """이슈별 대응 패키지 — DB/캐시에서 즉시 반환. 외부 수집은 전략갱신에서만."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    # 캐시가 있으면 즉시 반환 (외부 API 호출 없음)
    if _issue_response_cache["data"]:
        return _issue_response_cache["data"]

    # 캐시 없으면 DB 스코어 기반으로 간이 대응 생성
    def _run():
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from engines.issue_response import IssueResponseEngine
        from models.schemas import IssueScore, CrisisLevel
        config = SAMPLE_GYEONGNAM_CONFIG

        with get_db() as db:
            rows = db.get_latest_scores()

        if not rows:
            return {"error": "데이터 없음 — '전략 갱신' 버튼을 먼저 눌러주세요", "responses": [], "guide": _build_guide()}

        # DB 스코어에서 IssueScore 복원
        level_map = {"CRISIS": CrisisLevel.CRISIS, "ALERT": CrisisLevel.ALERT,
                     "WATCH": CrisisLevel.WATCH, "NORMAL": CrisisLevel.NORMAL}
        scores = []
        for r in rows:
            lv = level_map.get((r.get("crisis_level") or "NORMAL").upper(), CrisisLevel.NORMAL)
            scores.append(IssueScore(
                keyword=r.get("keyword", ""),
                score=r.get("score", 0),
                level=lv,
                breakdown={"sentiment_score": (r.get("negative_ratio") or 0) * 15},
                estimated_halflife_hours=r.get("halflife_hours", 12),
            ))

        engine = IssueResponseEngine(config)
        responses = engine.analyze_all(scores)

        result = _build_issue_response_result(responses, [], config)
        return result

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Executive Summary — 9 KPIs for war room
# ---------------------------------------------------------------------------

@app.get("/api/executive-summary")
async def api_executive_summary(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from engines.polling_tracker import PollingTracker
        from engines.voter_and_opponent import _days_until_election
        config = SAMPLE_GYEONGNAM_CONFIG
        days = _days_until_election(config.election_date)

        polling = PollingTracker(config)
        wp = polling.calculate_win_probability()
        trend = polling.calculate_trend()

        # DB에서 최신 데이터 가져오기
        from storage.database import ElectionDB
        db = ElectionDB()
        scores = db.get_latest_scores()
        db.close()

        crisis_count = sum(1 for s in scores if (s.get("crisis_level", "") or "").upper() == "CRISIS")
        alert_count = sum(1 for s in scores if (s.get("crisis_level", "") or "").upper() == "ALERT")
        avg_score = sum(s.get("score", 0) for s in scores) / max(len(scores), 1)

        # 소셜 버즈 지표 (social_buzz API 데이터 활용)
        digital_buzz_score = 0
        try:
            from collectors.social_collector import search_blogs, search_cafes
            blog = search_blogs(config.candidate_name)
            cafe = search_cafes(config.candidate_name)
            our_total = (blog.total_count if blog else 0) + (cafe.total_count if cafe else 0)
            # 상대 후보 대비 비율로 0~100 스코어
            if config.opponents:
                opp_blog = search_blogs(config.opponents[0])
                opp_cafe = search_cafes(config.opponents[0])
                opp_total = (opp_blog.total_count if opp_blog else 0) + (opp_cafe.total_count if opp_cafe else 0)
                if opp_total > 0:
                    digital_buzz_score = min(100, round(our_total / opp_total * 50))
                else:
                    digital_buzz_score = min(100, our_total)
            else:
                digital_buzz_score = min(100, our_total)
        except Exception:
            pass

        # 긴급대응 레벨
        if crisis_count >= 3:
            rapid_level = "RED"
        elif crisis_count >= 1:
            rapid_level = "ORANGE"
        elif alert_count >= 3:
            rapid_level = "YELLOW"
        else:
            rapid_level = "GREEN"

        return {
            "favorability": wp.get("our_avg", 0),
            "favorability_gap": wp.get("gap", 0),
            "trust_score": min(100, max(0, wp.get("our_avg", 0) * 2 + trend.get("our_trend", 0) * 10)),
            "issue_momentum": round(avg_score, 1),
            "media_sentiment": round(trend.get("our_trend", 0), 2),
            "digital_buzz": digital_buzz_score,
            "regional_risk": crisis_count + alert_count,
            "turnout_readiness": round(max(0, 100 - days) / 100 * 80, 1),
            "rapid_response_level": rapid_level,
            "crisis_count": crisis_count,
            "alert_count": alert_count,
            "days_left": days,
            "win_prob": wp.get("win_prob", 0),
            "momentum": trend.get("momentum", "stable"),
            "trend_daily": trend.get("our_trend", 0),
            "assessment": wp.get("assessment", ""),
            "candidate": config.candidate_name,
            "election_type": config.election_type,
            "slogan": config.slogan,
            "timestamp": datetime.now().isoformat(),
        }

    try:
        return await run_in_threadpool(_run)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Alerts Feed — severity-based alert system
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
async def api_alerts(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    alerts = []
    try:
        with get_db() as db:
            # 이슈 기반 알림
            scores = db.get_latest_scores()
            for s in scores:
                level = (s.get("crisis_level", "") or "").upper()
                if level == "CRISIS":
                    alerts.append({
                        "severity": "critical",
                        "type": "issue",
                        "title": f"위기 이슈: {s.get('keyword', '')}",
                        "detail": f"스코어 {s.get('score', 0):.1f} | 24h {s.get('mention_count', 0)}건",
                        "action": "즉시 대응 필요 — 대변인실 확인",
                        "owner": "대변인",
                        "timestamp": s.get("recorded_at", ""),
                    })
                elif level == "ALERT":
                    alerts.append({
                        "severity": "warning",
                        "type": "issue",
                        "title": f"경계 이슈: {s.get('keyword', '')}",
                        "detail": f"스코어 {s.get('score', 0):.1f}",
                        "action": "모니터링 강화",
                        "owner": "여론분석팀",
                        "timestamp": s.get("recorded_at", ""),
                    })

            # 상대 후보 공격 알림
            opp_rows = db._conn.execute(
                "SELECT * FROM opponent_signals ORDER BY recorded_at DESC LIMIT 10"
            ).fetchall()
            for o in opp_rows:
                o = dict(o)
                prob = o.get("attack_prob", 0)
                if prob >= 0.7:
                    alerts.append({
                        "severity": "critical",
                        "type": "opponent",
                        "title": f"{o.get('opponent_name', '')} 공격 임박 ({prob*100:.0f}%)",
                        "detail": o.get("recommended_action", ""),
                        "action": "선제 대응 준비",
                        "owner": "전략팀",
                        "timestamp": o.get("recorded_at", ""),
                    })
                elif prob >= 0.5:
                    alerts.append({
                        "severity": "warning",
                        "type": "opponent",
                        "title": f"{o.get('opponent_name', '')} 동향 주의 ({prob*100:.0f}%)",
                        "detail": o.get("message_shift", ""),
                        "action": "모니터링",
                        "owner": "여론분석팀",
                        "timestamp": o.get("recorded_at", ""),
                    })
    except Exception:
        pass

    # 정렬: critical first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 9))

    return {"alerts": alerts, "timestamp": datetime.now().isoformat()}


# ---------------------------------------------------------------------------
# Election Calendar
# ---------------------------------------------------------------------------

@app.get("/api/calendar")
async def api_calendar(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    from engines.voter_and_opponent import _days_until_election
    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
    days = _days_until_election(SAMPLE_GYEONGNAM_CONFIG.election_date)

    events = [
        {"date": "2026-02-03", "event": "예비후보 등록 시작", "type": "deadline", "done": True},
        {"date": "2026-03-17", "event": "김경수 예비후보 등록", "type": "milestone", "done": True},
        {"date": "2026-05-04", "event": "후보 등록 시작", "type": "deadline", "done": days < 30},
        {"date": "2026-05-14", "event": "공식 선거운동 시작", "type": "milestone", "done": days < 20},
        {"date": "2026-05-19", "event": "여론조사 공표 금지 시작", "type": "compliance", "done": days < 15},
        {"date": "2026-05-20", "event": "후보 TV 토론 (예상)", "type": "debate", "done": False},
        {"date": "2026-05-29", "event": "사전투표 1일차", "type": "voting", "done": False},
        {"date": "2026-05-30", "event": "사전투표 2일차", "type": "voting", "done": False},
        {"date": "2026-06-02", "event": "선거운동 마감", "type": "deadline", "done": False},
        {"date": "2026-06-03", "event": "투표일", "type": "election", "done": False},
    ]

    # 여론조사 공표 금지 체크
    poll_blackout = days <= 15

    return {
        "days_left": days,
        "election_date": SAMPLE_GYEONGNAM_CONFIG.election_date,
        "events": events,
        "poll_blackout": poll_blackout,
        "current_phase": "예비후보 등록" if days > 30 else ("공식 선거운동" if days > 1 else "투표일"),
    }


# ---------------------------------------------------------------------------
# Social buzz
# ---------------------------------------------------------------------------

@app.get("/api/social-buzz")
async def api_social_buzz(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from concurrent.futures import ThreadPoolExecutor
        from collectors.social_collector import search_blogs, search_cafes
        from collectors.unified_collector import _cached
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        all_candidates = [config.candidate_name] + config.opponents

        # 후보별 블로그+카페 병렬 수집 (YT/Trends는 제외 — 속도 우선)
        def _fetch_one(name):
            blog = _cached(f"sbuzz_blog:{name}", lambda _n=name: search_blogs(_n))
            cafe = _cached(f"sbuzz_cafe:{name}", lambda _n=name: search_cafes(_n))
            b_total = blog.total_count if blog else 0
            c_total = cafe.total_count if cafe else 0
            b_neg = blog.negative_ratio if blog else 0
            b_pos = blog.positive_ratio if blog else 0
            c_neg = cafe.negative_ratio if cafe else 0
            c_pos = cafe.positive_ratio if cafe else 0
            total = b_total + c_total
            sentiment = 0.0
            if total > 0:
                sentiment = round(((b_pos * b_total + c_pos * c_total) -
                                   (b_neg * b_total + c_neg * c_total)) / total, 2)
            return name, {
                "blog": b_total, "cafe": c_total, "video": 0,
                "social_total": total, "sentiment": sentiment,
                "blog_neg": round(b_neg, 2), "blog_pos": round(b_pos, 2),
                "cafe_neg": round(c_neg, 2), "cafe_pos": round(c_pos, 2),
                "youtube_count": 0, "youtube_views": 0, "youtube_top": [],
                "trend_interest": 0, "trend_change": 0,
                "trend_direction": "", "trend_related": [],
                "total_buzz": total,
            }

        candidates = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(_fetch_one, n) for n in all_candidates]
            for f in futures:
                try:
                    name, data = f.result(timeout=6)
                    candidates[name] = data
                except Exception:
                    pass

        # 5. 요약 통계
        our = candidates.get(config.candidate_name, {})
        opp = candidates.get(config.opponents[0], {}) if config.opponents else {}
        summary = {
            "our_total": our.get("total_buzz", 0),
            "opp_total": opp.get("total_buzz", 0),
            "buzz_ratio": round(our.get("total_buzz", 0) / max(opp.get("total_buzz", 0), 1), 2),
            "our_sentiment": our.get("sentiment", 0),
            "opp_sentiment": opp.get("sentiment", 0),
            "sentiment_advantage": round(our.get("sentiment", 0) - opp.get("sentiment", 0), 2),
            "our_trend": our.get("trend_interest", 0),
            "opp_trend": opp.get("trend_interest", 0),
            "trend_advantage": our.get("trend_interest", 0) - opp.get("trend_interest", 0),
            "buzz_leader": max(candidates, key=lambda n: candidates[n].get("total_buzz", 0)) if candidates else "",
            "sentiment_leader": max(candidates, key=lambda n: candidates[n].get("sentiment", -9)) if candidates else "",
        }

        return {
            "candidates": candidates,
            "summary": summary,
            "buzz_leader": summary.get("buzz_leader", ""),
            "sentiment_leader": summary.get("sentiment_leader", ""),
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Pledge comparison
# ---------------------------------------------------------------------------

@app.get("/api/pledges")
async def api_pledges(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.pledge_comparator import PledgeComparator
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        comp = PledgeComparator(SAMPLE_GYEONGNAM_CONFIG)
        matrix = comp.generate_comparison_matrix()
        attacks = comp.find_attack_points()
        defenses = comp.find_defense_points()
        # Regional talking points for top regions
        regional = {}
        for region in ["창원시", "김해시", "거제시"]:
            regional[region] = comp.get_regional_talking_points(region)
        config = SAMPLE_GYEONGNAM_CONFIG
        from engines.pledge_comparator import OPPONENT_PLEDGES
        our_pledges = [
            {"name": name, "numbers": info.get("수치", ""), "deadline": info.get("완료시기", ""),
             "description": info.get("설명", "")}
            for name, info in config.pledges.items()
        ]
        opp_pledges = {}
        for opp_name, opp_data in OPPONENT_PLEDGES.items():
            opp_pledges[opp_name] = {
                "party": opp_data.get("party", ""),
                "pledges": [
                    {"name": p["name"], "category": p.get("category", ""),
                     "description": p.get("description", ""),
                     "numbers": p.get("numbers", ""),
                     "strength": p.get("strength", ""),
                     "weakness": p.get("weakness", "")}
                    for p in opp_data.get("pledges", [])
                ],
            }
        return {
            "our_pledges": our_pledges,
            "opponent_pledges": opp_pledges,
            "candidate": config.candidate_name,
            "slogan": config.slogan,
            "matrix": matrix,
            "attacks": attacks,
            "defenses": defenses,
            "regional": regional,
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Weekly schedule
# ---------------------------------------------------------------------------

@app.get("/api/schedule-week/{start_date}")
async def api_schedule_week(start_date: str, session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    def _run():
        from engines.schedule_optimizer import ScheduleOptimizer
        from engines.voter_and_opponent import calculate_voter_priorities
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG
        opt = ScheduleOptimizer(config)
        segs = calculate_voter_priorities(config)
        plan = opt.generate_weekly_plan(start_date, voter_segments=segs)
        return {
            "week_start": plan.week_start,
            "week_end": plan.week_end,
            "week_theme": plan.week_theme,
            "region_coverage": plan.region_coverage,
            "uncovered": plan.uncovered_regions,
            "days": [
                {
                    "date": ds.date,
                    "theme": ds.day_theme,
                    "total_regions": ds.total_regions,
                    "total_travel": ds.total_travel_min,
                    "key_message": ds.key_message,
                    "events": [
                        {"time": e.time_slot, "region": e.region, "type": e.event_type,
                         "location": e.location_hint, "talking_points": e.talking_points,
                         "priority": e.priority, "notes": e.notes}
                        for e in ds.events
                    ],
                }
                for ds in plan.daily_schedules
            ],
        }

    try:
        result = await run_in_threadpool(_run)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Strategy runner (POST + rate limit + threadpool)
# ---------------------------------------------------------------------------

def _run_strategy_sync():
    """Synchronous strategy pipeline — runs in threadpool.

    v2: V2 엔진 통합 (dedup, anomaly, score_explain, readiness, strategy_mode)
    """
    global _v2_enrichment_cache
    from dotenv import load_dotenv
    load_dotenv(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    )

    from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
    from engines.issue_scoring import calculate_issue_score
    from engines.voter_and_opponent import (
        calculate_voter_priorities,
        analyze_opponents,
    )
    from engines.polling_tracker import PollingTracker
    from engines.pledge_comparator import PledgeComparator
    from engines.strategy_synthesizer import StrategySynthesizer
    from collectors.naver_news import collect_issue_signals, collect_opponent_data
    from storage.database import ElectionDB

    # V2 엔진 임포트
    from engines.news_deduplicator import NewsDeduplicator
    from engines.anomaly_detector import AnomalyDetector
    from engines.score_explainer import build_score_explanation
    from engines.response_readiness import ResponseReadinessScorer
    from engines.strategy_mode_v2 import StrategyModeSelector

    config = SAMPLE_GYEONGNAM_CONFIG

    # --- 키워드를 JSON에서 로드, type별 분리 ---
    kw_data = _load_keywords()
    all_kws = kw_data.get("keywords", [])

    # candidate 타입: 후보 버즈 추적 (이슈 스코어링 제외)
    candidate_kws = [k["keyword"] for k in all_kws if k.get("type", "").startswith("candidate")]
    # issue 타입: 이슈 레이더용 (스코어링 대상), high/medium 우선
    issue_kws_high = [k["keyword"] for k in all_kws if k.get("type") == "issue" and k.get("priority") in ("high", "medium")]
    issue_kws_low = [k["keyword"] for k in all_kws if k.get("type") == "issue" and k.get("priority") == "low"]

    # API 호출 제한: high/medium 전체 + low에서 최대 5개
    issue_kws = issue_kws_high + issue_kws_low[:5]

    # fallback: JSON이 비었으면 기본 키워드 사용
    if not issue_kws:
        issue_kws = [
            "경남도지사 선거", "경남도지사 공약", "경남 조선업 일자리",
            "경남 교통 BRT", "경남 청년 정책", "부울경 행정통합",
            "경남 우주항공", "창원 특례시",
        ]

    # _v2_enrichment_cache 초기화 (None이면 dict로)
    if _v2_enrichment_cache is None:
        _v2_enrichment_cache = {}

    # --- 후보 버즈 수집 (별도 — 이슈 스코어링에 넣지 않음) ---
    candidate_buzz = {}
    if candidate_kws:
        try:
            cand_signals = collect_issue_signals(
                candidate_kws,
                candidate_name=config.candidate_name,
                opponents=config.opponents,
            )

            # 후보 키워드별 제목 수집 (AI 감성분석용)
            from collectors.naver_news import _last_collection_meta
            cand_titles_map = {}
            for cs in cand_signals:
                meta = _last_collection_meta.get(cs.keyword, {})
                raw_articles = meta.get("raw_articles", [])
                cand_titles_map[cs.keyword] = [
                    a.get("title", "") for a in raw_articles[:15]
                ]

            # AI 6분류 감성분석 (1회 배치 호출, 6시간 캐시)
            cand_ai_sentiment = {}
            try:
                from engines.ai_sentiment import analyze_candidate_buzz_batch
                cand_ai_sentiment = analyze_candidate_buzz_batch(
                    keyword_titles=cand_titles_map,
                    candidate_name=config.candidate_name,
                    opponents=config.opponents,
                )
            except Exception as e:
                print(f"[CandidateBuzz AI] Warning: {e}")

            for cs in cand_signals:
                ai_sent = cand_ai_sentiment.get(cs.keyword)
                candidate_buzz[cs.keyword] = {
                    "mention_count": cs.mention_count,
                    "velocity": cs.velocity,
                    "negative_ratio": cs.negative_ratio,
                    "media_tier": cs.media_tier,
                    "candidate_linked": cs.candidate_linked,
                    "portal_trending": cs.portal_trending,
                    "tv_reported": cs.tv_reported,
                    # AI 6분류 감성분석
                    "ai_sentiment": ai_sent.to_dict() if ai_sent else None,
                }
            _mark_run("candidate_buzz")
        except Exception as e:
            print(f"[CandidateBuzz] Warning: {e}")

    _v2_enrichment_cache["candidate_buzz"] = candidate_buzz

    # --- 이슈 시그널 수집 (이슈 레이더용) ---
    signals = collect_issue_signals(
        issue_kws,
        candidate_name=config.candidate_name,
        opponents=config.opponents,
    )

    _mark_run("naver_news")

    if not signals:
        return {"error": "뉴스 수집 실패 — 네이버 API를 확인하세요."}

    # --- V2 Step 1: News Deduplication ---
    dedup = NewsDeduplicator()
    dedup_results = {}
    sig_articles_map = {}  # keyword → articles (원본 기사)
    for sig in signals:
        # signal에서 기사 데이터 추출 (raw_articles가 있으면 사용)
        articles = getattr(sig, 'raw_articles', None) or []
        if articles:
            metrics = dedup.get_dedup_metrics(articles)
            dedup_results[sig.keyword] = metrics
            sig_articles_map[sig.keyword] = articles

    # --- V2 Step 2: Anomaly Detection ---
    anomaly_detector = AnomalyDetector()
    anomaly_results = []
    anomaly_map = {}
    for sig in signals:
        ar = anomaly_detector.analyze(
            keyword=sig.keyword,
            current_24h=sig.mention_count,
            current_6h=0,
        )
        anomaly_results.append(ar)
        anomaly_map[sig.keyword] = ar

    # --- V2 Step 3: Issue Scoring (with anomaly + dedup enrichment) ---
    issue_scores = sorted(
        [
            calculate_issue_score(
                sig, config,
                anomaly_result=anomaly_map.get(sig.keyword),
                dedup_metrics=dedup_results.get(sig.keyword),
            )
            for sig in signals
        ],
        key=lambda x: x.score,
        reverse=True,
    )

    # --- Collect social/community/youtube/trends for Index computation ---
    # 이전 수집 데이터를 글로벌 캐시에서 로드 (10분 스캔 시에도 활용)
    global _collected_data_cache
    social_data = dict(_collected_data_cache.get("social_data", {}))
    community_data = dict(_collected_data_cache.get("community_data", {}))
    youtube_data = dict(_collected_data_cache.get("youtube_data", {}))
    trends_data = dict(_collected_data_cache.get("trends_data", {}))
    try:
        from collectors.social_collector import search_blogs, search_cafes
        from collectors.community_collector import scan_all_communities
        from collectors.youtube_collector import search_youtube, fetch_keyword_comments
        from collectors.trends_collector import get_search_trend
        from concurrent.futures import ThreadPoolExecutor

        kw_list = [iss.keyword for iss in issue_scores[:10]]

        from collectors.api_cache import can_call, wait_if_needed, record_call, get_cached, set_cached

        def _fetch_social(kw):
            cached = get_cached("naver_news", f"social_{kw}")
            if cached: return kw, cached[0], cached[1]
            wait_if_needed("naver_news")
            blog = search_blogs(kw)
            record_call("naver_news")
            wait_if_needed("naver_news")
            cafe = search_cafes(kw)
            record_call("naver_news")
            set_cached("naver_news", f"social_{kw}", (blog, cafe))
            return kw, blog, cafe

        def _fetch_community(kw):
            cached = get_cached("community", kw)
            if cached: return kw, cached
            wait_if_needed("community")
            result = scan_all_communities(kw)
            record_call("community")
            set_cached("community", kw, result)
            return kw, result

        def _fetch_youtube(kw):
            if not can_call("youtube"):
                record_call("youtube", success=False, error="일일 쿼터 90% 도달")
                return kw, None
            cached = get_cached("youtube", kw)
            if cached: return kw, cached
            wait_if_needed("youtube")
            result = search_youtube(kw, max_results=5)
            record_call("youtube", units=100)  # search = 100 units
            set_cached("youtube", kw, result)
            return kw, result

        def _fetch_trends(kw):
            cached = get_cached("google_trends", kw)
            if cached: return kw, cached
            if not can_call("google_trends"):
                return kw, None
            wait_if_needed("google_trends")
            result = get_search_trend(kw)
            record_call("google_trends")
            set_cached("google_trends", kw, result)
            return kw, result

        import time as _time

        # 소셜 (블로그+카페) — 순차 (API rate limit 방지)
        for kw in kw_list:
            try:
                blog = search_blogs(kw)
                cafe = search_cafes(kw)
                social_data[kw] = {"blog": blog, "cafe": cafe}
            except Exception:
                pass
            _time.sleep(0.3)  # rate limit 방지

        _mark_run("social_collector")
        _time.sleep(1)  # API 쿨다운

        # 커뮤니티 (상위 5개 키워드만, 순차)
        for kw in kw_list[:5]:
            try:
                community_data[kw] = scan_all_communities(kw)
            except Exception:
                pass
            _time.sleep(0.5)

        _mark_run("community")

        # 유튜브 + 트렌드 (병렬 가능 — 다른 API)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for kw, yt in pool.map(lambda k: _fetch_youtube(k), kw_list[:5]):
                youtube_data[kw] = yt

        _mark_run("youtube")

        for kw in kw_list[:5]:
            try:
                trends_data[kw] = get_search_trend(kw)
            except Exception:
                pass
        _mark_run("trends")

        # Pre-Trigger 스캔 (상대 선제행동 사전 감지)
        pretrigger_data = None
        try:
            from collectors.pretrigger_collector import scan_pretriggers
            all_titles = []
            for sig in signals:
                if hasattr(sig, 'raw_articles') and sig.raw_articles:
                    all_titles.extend(a.get("title", "") for a in sig.raw_articles)
            pretrigger_data = scan_pretriggers(
                opponent_name=config.opponents[0] if config.opponents else "박완수",
                our_pledges=config.pledges,
                recent_titles=all_titles,
            )
            _mark_run("pretrigger")
            if pretrigger_data.critical_count > 0:
                print(f"[PreTrigger] ⚠ CRITICAL {pretrigger_data.critical_count}건 감지!")
        except Exception as e:
            print(f"[PreTrigger] Warning: {e}")

        # AI 감성 분석 (Claude Haiku 배치)
        ai_sentiment_data = dict(_collected_data_cache.get("ai_sentiment_data", {}))
        try:
            from engines.ai_sentiment import analyze_sentiment_ai
            sig_map_ai = {s.keyword: s for s in signals}
            for kw in kw_list[:5]:
                sig = sig_map_ai.get(kw)
                titles = []
                if sig and hasattr(sig, 'raw_articles') and sig.raw_articles:
                    titles = [a.get("title", "") for a in sig.raw_articles[:20]]
                # 블로그/카페 제목도 추가
                sd_ai = social_data.get(kw, {})
                if sd_ai.get("blog") and sd_ai["blog"].top_items:
                    titles.extend(item.get("title", "") for item in sd_ai["blog"].top_items[:5])
                if sd_ai.get("cafe") and sd_ai["cafe"].top_items:
                    titles.extend(item.get("title", "") for item in sd_ai["cafe"].top_items[:5])
                # YouTube 영상 제목 추가 (추가 API 콜 0 — 이미 수집된 데이터)
                yt_ai = youtube_data.get(kw)
                if yt_ai and hasattr(yt_ai, 'top_videos') and yt_ai.top_videos:
                    titles.extend(v.title for v in yt_ai.top_videos[:5] if v.title)
                # 커뮤니티 게시물 제목 추가 (추가 API 콜 0)
                cr_ai = community_data.get(kw)
                if cr_ai and hasattr(cr_ai, 'signals'):
                    for cs in cr_ai.signals[:3]:
                        titles.extend(cs.recent_titles[:3])
                if titles:
                    ai_sentiment_data[kw] = analyze_sentiment_ai(
                        titles=titles,
                        keyword=kw,
                        candidate_name=config.candidate_name,
                        opponents=config.opponents,
                    )
                    import time as _t2
                    _t2.sleep(0.5)
            _mark_run("ai_sentiment")
        except Exception as e:
            print(f"[AI Sentiment] Warning: {e}")

        # 네이버 데이터랩 (성별/연령별 검색 트렌드)
        naver_trend_data = dict(_collected_data_cache.get("naver_trend_data", {}))
        try:
            from collectors.trends_collector import get_naver_trend
            for kw in kw_list[:5]:
                try:
                    naver_trend_data[kw] = get_naver_trend(kw, days=30)
                except Exception:
                    pass
        except Exception as e:
            print(f"[NaverDataLab] Import warning: {e}")

        # 유튜브 댓글 (상위 3개 키워드, 영상당 30댓글)
        yt_comment_data = dict(_collected_data_cache.get("yt_comment_data", {}))
        for kw in kw_list[:3]:
            try:
                yt_comment_data[kw] = fetch_keyword_comments(kw, top_n_videos=3, max_comments_per_video=30)
            except Exception:
                pass

    except Exception as e:
        print(f"[Collector] Warning: {e}")

    # --- Issue Index + Reaction Index (분리 산출, full data) ---
    issue_index_map = {}
    reaction_index_map = {}
    org_signal_map = {}
    try:
        from engines.issue_index import compute_issue_index
        from engines.reaction_index import compute_reaction_index
        from engines.org_signal_detector import extract_org_signals

        sig_map_idx = {s.keyword: s for s in signals}

        # 조직 시그널 추출 (v2: 뉴스 + 커뮤니티 + owned channel)
        for iss in issue_scores:
            news_titles = []
            community_titles = []
            sig = sig_map_idx.get(iss.keyword)
            if sig and hasattr(sig, 'raw_articles') and sig.raw_articles:
                news_titles.extend(a.get("title", "") for a in sig.raw_articles)
            cr = community_data.get(iss.keyword)
            if cr:
                for cs in cr.signals:
                    community_titles.extend(cs.recent_titles[:5])

            all_titles = news_titles + community_titles
            org_signal_map[iss.keyword] = extract_org_signals(
                titles=all_titles,
                keyword=iss.keyword,
                candidate_name=config.candidate_name,
                opponents=config.opponents,
                media_tier=sig.media_tier if sig else 3,
                community_titles=community_titles,
            )

        for iss in issue_scores:
            sig = sig_map_idx.get(iss.keyword)
            dr = dedup_results.get(iss.keyword, {})
            ar = anomaly_map.get(iss.keyword)
            org = org_signal_map.get(iss.keyword)
            sd = social_data.get(iss.keyword, {})
            cr = community_data.get(iss.keyword)
            yt = youtube_data.get(iss.keyword)
            tr = trends_data.get(iss.keyword)

            blog_sig = sd.get("blog")
            cafe_sig = sd.get("cafe")

            blog_count = blog_sig.total_count if blog_sig else 0
            cafe_count = cafe_sig.total_count if cafe_sig else 0
            yt_count = yt.recent_count if yt else 0
            yt_views = yt.total_views if yt else 0
            yt_cr = yt_comment_data.get(iss.keyword) if 'yt_comment_data' in dir() else None
            yt_comments = yt_cr.total_comments if yt_cr else 0
            yt_comment_sentiment = yt_cr.net_sentiment if yt_cr else 0.0
            trend_interest = tr.interest_now if tr else 0
            trend_change = tr.change_7d if tr else 0
            comm_total = cr.total_mentions if cr else 0
            nv = naver_trend_data.get(iss.keyword)
            naver_interest = nv.interest_now if nv else 0
            naver_change = nv.change_7d if nv else 0

            # ── YouTube 제목으로 candidate_linked 보강 (추가 API 0) ──
            candidate_linked_final = sig.candidate_linked if sig else False
            if not candidate_linked_final and yt and hasattr(yt, 'top_videos') and yt.top_videos:
                candidate_linked_final = any(
                    config.candidate_name in v.title
                    for v in yt.top_videos if v.title
                )

            # ── Issue Index ──
            ii = compute_issue_index(
                keyword=iss.keyword,
                mention_count=sig.mention_count if sig else 0,
                deduped_stories=dr.get("deduped_story_count", 0),
                media_tier=sig.media_tier if sig else 3,
                tier1_count=iss.breakdown.get("tier1_count", 0),
                source_diversity=iss.breakdown.get("source_diversity", 0),
                tv_reported=sig.tv_reported if sig else False,
                portal_trending=sig.portal_trending if sig else False,
                velocity=sig.velocity if sig else 0,
                surprise_score=ar.surprise_score if ar else 0,
                day_over_day=ar.day_over_day if ar else 0,
                candidate_linked=candidate_linked_final,
                candidate_action_linked=getattr(sig, 'candidate_action_linked', False),
                message_theme=getattr(sig, 'message_theme', ""),
                region=getattr(sig, 'region', ""),
                blog_count=blog_count,
                cafe_count=cafe_count,
                video_count=yt_count,
                youtube_count=yt_count,
                trend_interest=trend_interest,
                community_mentions=comm_total,
                naver_interest=naver_interest,
                naver_change_7d=naver_change,
            )
            issue_index_map[iss.keyword] = ii

            # ── Reaction Index (v3: 5-layer + velocity + confidence) ──
            yt_cr = yt_comment_data.get(iss.keyword) if 'yt_comment_data' in dir() else None
            ai_sent = ai_sentiment_data.get(iss.keyword)
            ri = compute_reaction_index(
                keyword=iss.keyword,
                # Layer 1: Community
                community_signals=cr.signals if cr else [],
                community_resonance=cr.community_resonance if cr else 0,
                community_has_viral=cr.has_any_viral if cr else False,
                community_derision=max((s.derision_score for s in cr.signals), default=0) if cr else 0,
                community_dominant_tone=ai_sent.dominant_tone if ai_sent else (cr.dominant_tone if cr else ""),
                # Layer 2: Content Creation
                blog_count=blog_count,
                cafe_count=cafe_count,
                video_count=yt_count,
                youtube_count=yt_count,
                youtube_views=yt_views,
                owned_channel_active=False,
                # Layer 3: Sentiment (AI 강화)
                negative_ratio=sig.negative_ratio if sig else 0,
                positive_ratio=1.0 - (sig.negative_ratio if sig else 0.5),
                news_net_sentiment=ai_sent.net_sentiment if ai_sent else 0.0,
                blog_net_sentiment=blog_sig.net_sentiment if blog_sig else 0,
                cafe_net_sentiment=cafe_sig.net_sentiment if cafe_sig else 0,
                tone_distribution=ai_sent.tone_distribution if ai_sent else {},
                candidate_linked=sig.candidate_linked if sig else False,
                candidate_name=config.candidate_name,
                opponents=config.opponents,
                # Layer 4: Search
                trend_interest=trend_interest,
                trend_change_7d=trend_change,
                trend_direction=tr.trend_direction if tr else "",
                naver_interest=naver_interest,
                naver_change_7d=naver_change,
                naver_gender_skew=nv.gender_skew if nv else "",
                naver_peak_age=nv.peak_age if nv else "",
                # Layer 5: YouTube Comments
                youtube_comments=yt_cr.total_comments if yt_cr else 0,
                yt_comment_net_sentiment=yt_cr.net_sentiment if yt_cr else 0,
                yt_comment_positive_ratio=yt_cr.positive_ratio if yt_cr else 0,
                yt_comment_negative_ratio=yt_cr.negative_ratio if yt_cr else 0,
                yt_comment_mobilization=yt_cr.mobilization_detected if yt_cr else False,
                yt_top_positive=yt_cr.top_positive[0][:80] if yt_cr and yt_cr.top_positive else "",
                yt_top_negative=yt_cr.top_negative[0][:80] if yt_cr and yt_cr.top_negative else "",
                # Velocity
                surprise_score=ar.surprise_score if ar else 0,
                day_over_day=ar.day_over_day if ar else 0,
                is_anomaly=ar.is_anomaly if ar else False,
                # Secondary
                endorsement_count=org.endorsement_count if org else 0,
                withdrawal_count=org.withdrawal_count if org else 0,
                org_net_sentiment=org.net_org_sentiment if org else 0,
                org_high_influence=org.high_influence_count if org else 0,
                change_pct=ar.day_over_day if ar else 0,
                region=getattr(sig, 'region', ""),
            )
            reaction_index_map[iss.keyword] = ri

        # ── Segment Analysis ──
        from engines.segment_mapper import analyze_segments
        segment_map = {}
        for iss in issue_scores:
            cr = community_data.get(iss.keyword)
            org = org_signal_map.get(iss.keyword)
            sig = sig_map_idx.get(iss.keyword)

            # 활성 플랫폼 결정
            active_platforms = []
            sd = social_data.get(iss.keyword, {})
            if sd.get("blog") and sd["blog"].total_count > 0:
                active_platforms.append("blog")
            if sd.get("cafe") and sd["cafe"].total_count > 0:
                active_platforms.append("cafe")
            if youtube_data.get(iss.keyword) and youtube_data[iss.keyword].recent_count > 0:
                active_platforms.append("youtube")
            if trends_data.get(iss.keyword) and trends_data[iss.keyword].interest_now > 10:
                active_platforms.append("trend")

            # 지역 힌트
            region_hints = {}
            if sig and getattr(sig, 'region', ''):
                region_hints[sig.region] = 3
            # 키워드에서 지역 추출
            for rn in ["창원", "김해", "진주", "거제", "양산", "통영", "사천", "밀양"]:
                if rn in iss.keyword:
                    region_hints[rn] = region_hints.get(rn, 0) + 5

            seg = analyze_segments(
                keyword=iss.keyword,
                community_signals=cr.signals if cr else [],
                active_platforms=active_platforms,
                org_type=org.signals[0].org_type if org and org.signals else "",
                region_hints=region_hints,
                naver_gender_skew=nv.gender_skew if nv else "",
                naver_peak_age=nv.peak_age if nv else "",
                naver_age_breakdown=nv.age_breakdown if nv else {},
                naver_male_interest=nv.male_interest if nv else 0,
                naver_female_interest=nv.female_interest if nv else 0,
            )
            segment_map[iss.keyword] = seg

        # ── Attribution Analysis (v4) ──
        from engines.reaction_attribution import ReactionAttributor
        attributor = ReactionAttributor(
            candidate_name=config.candidate_name,
            regions=config.regions if hasattr(config, 'regions') else {},
        )
        # 행동 추출 (자체 채널에서)
        attribution_actions = []
        try:
            channel_metrics = _v2_enrichment_cache.get("channels", [])
            if channel_metrics:
                attribution_actions = attributor.extract_actions_from_channels(channel_metrics)
        except Exception:
            pass

        # 귀인 매칭
        attributions = []
        if attribution_actions and unified_signals:
            try:
                attributions = attributor.attribute_reactions(
                    actions=attribution_actions,
                    unified_signals=unified_signals,
                    polling_data=polling_result,
                )
                attr_summary = attributor.build_summary(
                    attribution_actions, attributions, unified_signals,
                )
                _v2_enrichment_cache["attribution"] = {
                    "total_actions": attr_summary.total_actions,
                    "attributed_count": attr_summary.attributed_count,
                    "strongest": attr_summary.strongest_linkage,
                    "unlinked": attr_summary.unlinked_reactions[:5],
                    "movement": attr_summary.movement_detected[:5],
                    "top": [
                        {
                            "action": a.action.description[:50],
                            "keyword": a.keyword,
                            "confidence": round(a.confidence, 2),
                            "delta": round(a.reaction_delta, 0),
                            "grade_change": f"{a.reaction_grade_before}→{a.reaction_grade_after}",
                        }
                        for a in attributions[:5]
                    ],
                }
            except Exception as e:
                print(f"[Attribution] Warning: {e}")
                attributions = []
        else:
            attributions = []

    except Exception as e:
        print(f"[Index] Warning: {e}")
        segment_map = {}
        attributions = []

    # --- V2 Step 4: Response Readiness ---
    readiness_scorer = ResponseReadinessScorer(config)
    readiness_map = {}
    for issue in issue_scores:
        rdns = readiness_scorer.score(
            keyword=issue.keyword,
            issue_score=issue.score,
        )
        readiness_map[issue.keyword] = rdns

    # --- V2 Step 5: Score Explanation ---
    _sig_map = {s.keyword: s for s in signals}
    score_explanations = []
    explanation_map = {}
    for issue in issue_scores:
        kw = issue.keyword
        dr = dedup_results.get(kw, {})
        _sig = _sig_map.get(kw)
        explanation = build_score_explanation(
            keyword=kw,
            score_breakdown=issue.breakdown,
            total_score=issue.score,
            crisis_level=issue.level.name,
            raw_mentions=dr.get("raw_mentions") or (getattr(_sig, "mention_count", 0) if _sig else 0),
            deduped_stories=dr.get("deduped_story_count", 0),
            anomaly_result=anomaly_map.get(kw),
            readiness_result=readiness_map.get(kw),
        )
        score_explanations.append(explanation)
        explanation_map[kw] = explanation

    voter_segments = calculate_voter_priorities(config, issue_scores)
    opponent_data = collect_opponent_data(config.opponents, region=config.region)
    opponent_signals = analyze_opponents(config, opponent_data, issue_scores)

    polling = PollingTracker(config)
    polling_result = polling.calculate_win_probability()
    polling_trend = polling.calculate_trend()

    comparator = PledgeComparator(config)
    attack_points = comparator.find_attack_points(config.opponents[0] if config.opponents else "")
    defense_points = comparator.find_defense_points()

    # --- V2 Step 6: Strategy Mode Decision ---
    mode_selector = StrategyModeSelector()
    from engines.voter_and_opponent import _days_until_election
    days_left = _days_until_election(config.election_date)

    candidate_crisis = any(
        issue.level.name == "CRISIS" and config.candidate_name in issue.keyword
        for issue in issue_scores
    )

    mode_decision = mode_selector.decide(
        issue_scores=issue_scores,
        polling_gap=polling_result.get("gap", 0.0),
        momentum=polling_trend.get("momentum", "stable"),
        our_trend=polling_trend.get("our_trend", 0.0),
        opponent_signals=opponent_signals,
        days_left=days_left,
        candidate_linked_crisis=candidate_crisis,
    )

    synthesizer = StrategySynthesizer(config)
    strategy = synthesizer.synthesize(
        issue_scores=issue_scores,
        opponent_signals=opponent_signals,
        voter_segments=voter_segments,
        polling_data=polling_result,
        attack_points=attack_points,
        defense_points=defense_points,
        mode_override=mode_decision,
    )

    # --- 수집 데이터 글로벌 캐시 갱신 (다음 10분 스캔에서 재사용) ---
    _collected_data_cache["social_data"].update(social_data)
    _collected_data_cache["youtube_data"].update(youtube_data)
    _collected_data_cache["community_data"].update(community_data)
    _collected_data_cache["trends_data"].update(trends_data)
    if 'naver_trend_data' in dir() and naver_trend_data:
        _collected_data_cache["naver_trend_data"].update(naver_trend_data)
    if 'ai_sentiment_data' in dir() and ai_sentiment_data:
        _collected_data_cache["ai_sentiment_data"].update(ai_sentiment_data)
    if 'yt_comment_data' in dir() and yt_comment_data:
        _collected_data_cache["yt_comment_data"].update(yt_comment_data)
    _collected_data_cache["updated_at"] = datetime.now().isoformat()

    # --- Persist ---
    db = ElectionDB()
    try:
        db.save_issue_scores(issue_scores, signals)
        db.save_voter_priorities(voter_segments)
        db.save_opponent_signals(opponent_signals)
    finally:
        db.close()

    # --- 전체 캐시 초기화 (소셜/이슈 새 데이터 반영) ---
    try:
        from collectors.unified_collector import _cache as unified_cache
        unified_cache.clear()
    except Exception:
        pass

    # --- V2 enriched 캐시 저장 (score explanations) ---
    # candidate_buzz 보존 (파이프라인 앞에서 이미 저장됨)
    _prev_buzz = _v2_enrichment_cache.get("candidate_buzz", {}) if _v2_enrichment_cache else {}
    _v2_enrichment_cache = {
        "candidate_buzz": _prev_buzz,
        "score_explanations": [e.to_dict() for e in score_explanations],
        "readiness": {
            kw: {
                "fact": r.fact_readiness,
                "message": r.message_readiness,
                "legal": r.legal_readiness,
                "total": r.total_readiness,
                "grade": r.readiness_grade,
                "fact_detail": r.fact_detail,
                "message_detail": r.message_detail,
                "legal_detail": r.legal_detail,
                "override": r.recommended_stance_override,
                "override_reason": r.override_reason,
            }
            for kw, r in readiness_map.items()
        },
        "anomalies": {
            kw: {
                "surprise_score": ar.surprise_score,
                "z_score": round(ar.z_score, 2),
                "is_anomaly": ar.is_anomaly,
                "is_surge": ar.is_surge,
                "reason": ar.anomaly_reason,
                "day_over_day": round(ar.day_over_day, 1),
            }
            for kw, ar in anomaly_map.items()
        },
        "issue_indices": {kw: ii.to_dict() for kw, ii in issue_index_map.items()},
        "reaction_indices": {kw: ri.to_dict() for kw, ri in reaction_index_map.items()},
        "youtube_comments": {
            kw: cr.to_dict()
            for kw, cr in (yt_comment_data if 'yt_comment_data' in dir() else {}).items()
        },
        "segments": {kw: seg.to_dict() for kw, seg in segment_map.items()} if segment_map else {},
        "naver_trends": {kw: nv.to_dict() for kw, nv in naver_trend_data.items()} if naver_trend_data else {},
        "ai_sentiment": {kw: s.to_dict() for kw, s in ai_sentiment_data.items()} if ai_sentiment_data else {},
        "pretrigger": pretrigger_data.to_dict() if pretrigger_data else {"signals": [], "critical": 0, "warning": 0},
        "national_poll": national_poll_data.to_dict() if 'national_poll_data' in dir() and national_poll_data else None,
        "mode_decision": {
            "mode": mode_decision.mode,
            "mode_korean": mode_decision.mode_korean,
            "confidence": mode_decision.confidence,
            "dominant_pressure": mode_decision.dominant_pressure,
            "reasoning": mode_decision.reasoning,
            "pressures": {
                "crisis": round(mode_decision.pressures.crisis_pressure, 1),
                "polling_gap": round(mode_decision.pressures.polling_gap_pressure, 1),
                "momentum": round(mode_decision.pressures.momentum_pressure, 1),
                "opportunity": round(mode_decision.pressures.opportunity_pressure, 1),
            },
            "pressure_reasons": {
                "crisis": mode_decision.pressures.crisis_reasons,
                "polling_gap": mode_decision.pressures.polling_reasons,
                "momentum": mode_decision.pressures.momentum_reasons,
                "opportunity": mode_decision.pressures.opportunity_reasons,
            },
        },
        "timestamp": datetime.now().isoformat(),
    }

    # --- Auto-evaluate previous decisions (closes the learning loop) ---
    try:
        from engines.outcome_evaluator import evaluate_issue_stance
        from engines.learning_feedback import build_feedback_profile
        issue_score_map = {s.keyword: s for s in issue_scores}
        sig_map_eval = {s.keyword: s for s in signals}

        with get_db() as eval_db:
            # 24h 이내 미평가 결정 조회
            pending = eval_db._conn.execute("""
                SELECT d.decision_id, d.decision_type, d.keyword, d.recommended_value,
                       d.confidence, d.context_snapshot
                FROM v5_decisions d
                LEFT JOIN v5_outcomes o ON d.decision_id = o.decision_id
                WHERE o.decision_id IS NULL
                  AND d.created_at >= datetime('now', '-48 hours')
                  AND d.decision_type = 'issue_stance'
            """).fetchall()

            auto_outcomes = []
            for row in pending:
                row = dict(row)
                kw = row.get("keyword", "")
                iss = issue_score_map.get(kw)
                sig = sig_map_eval.get(kw)
                if not iss:
                    continue

                import json as _json
                ctx = _json.loads(row.get("context_snapshot", "{}")) if isinstance(row.get("context_snapshot"), str) else (row.get("context_snapshot") or {})

                class _FakeRecord:
                    pass
                rec = _FakeRecord()
                rec.decision_id = row["decision_id"]
                rec.decision_type = row["decision_type"]
                rec.keyword = kw
                rec.recommended_value = row.get("recommended_value", "")
                rec.confidence = row.get("confidence", "")
                rec.context_snapshot = ctx

                neg_ratio = sig.negative_ratio if sig else 0.0
                outcome = evaluate_issue_stance(rec, iss.score, iss.level.name, neg_ratio)
                auto_outcomes.append(outcome)

            if auto_outcomes:
                eval_db.save_outcomes(auto_outcomes)

        # 피드백 프로파일 재구축 (평가 결과 반영)
        build_feedback_profile()
    except Exception as e:
        print(f"[Auto-eval] Warning: {e}")

    # --- Gap 1: Lag Correlation (Leading Index ↔ Polling) ---
    try:
        from engines.lag_correlator import (
            record_index_snapshot, record_poll_snapshot,
            seed_from_polling_tracker, compute_lag_correlation,
        )
        from engines.leading_index_engine import compute_leading_index
        from engines.forecast_engine import compute_forecast
        from engines.learning_feedback import build_feedback_profile, adjust_confidence

        # 대통령/정당 지지율 수집 (v3)
        try:
            from collectors.national_poll_collector import get_latest_national_poll
            national_poll_data = get_latest_national_poll()
            _mark_run("national_poll")
        except Exception as e:
            national_poll_data = None
            print(f"[NationalPoll] Warning: {e}")

        # 경남 경제 지표 수집 (v3)
        try:
            from collectors.economic_collector import get_latest_economic
            economic_data = get_latest_economic()
            _mark_run("economic")
        except Exception as e:
            economic_data = None
            print(f"[Economic] Warning: {e}")

        # 지역 언론 톤: 파이프라인 자동 수집 제거 — 일반 뉴스 검색과 중복 (66콜 절약)
        # 온디맨드 API (/api/v2/regional-media)는 유지
        regional_media_data = None

        # 뉴스 댓글 수집 (v4) — 상위 키워드에 대해
        news_comment_data = {}
        try:
            from collectors.news_comment_collector import fetch_keyword_comments
            top_keywords = list(issue_index_map.keys())[:3] if issue_index_map else [config.candidate_name]
            for nck in top_keywords:
                ncr = fetch_keyword_comments(nck, max_articles=3)
                if ncr.total_comments > 0:
                    news_comment_data[nck] = ncr
                import time as _t; _t.sleep(0.5)
            _mark_run("news_comment")
        except Exception as e:
            print(f"[NewsComment] Warning: {e}")

        # 이벤트 컨텍스트 감지 (v4) — 최근 이슈에서 이벤트 유형 추론
        event_context = None
        try:
            if issue_scores and len(issue_scores) > 0:
                top_issue = issue_scores[0]
                # 상위 이슈가 후보 연결 + HOT 이상이면 이벤트 컨텍스트 생성
                if hasattr(top_issue, 'level') and str(top_issue.level) in ("CRISIS", "ALERT"):
                    event_context = {"event_type": "scandal", "severity": "major"}
                elif hasattr(top_issue, 'candidate_action_linked') and top_issue.candidate_action_linked:
                    event_context = {"event_type": "policy", "severity": "standard"}
        except Exception:
            pass

        # Leading Index 계산 (v4: + 이벤트 컨텍스트 + 지역 언론)
        leading_index = compute_leading_index(
            issue_scores=issue_scores,
            anomaly_results=anomaly_results,
            polling_data=polling_result,
            candidate_name=config.candidate_name,
            opponents=config.opponents,
            issue_signals=signals,
            tenant_id=config.tenant_id,
            issue_index_map=issue_index_map,
            reaction_index_map=reaction_index_map,
            naver_trend_data=naver_trend_data,
            ai_sentiment_data=ai_sentiment_data,
            national_poll=national_poll_data.to_dict() if national_poll_data else None,
            economic_data=economic_data.to_dict() if economic_data else None,
            event_context=event_context,
        )

        # 히스토리 기록
        record_index_snapshot(leading_index.index, leading_index.direction)
        seed_from_polling_tracker(polling)  # 기존 poll 데이터 로드
        our_avg = polling_result.get("our_avg", 0)
        gap = polling_result.get("gap", 0)
        if our_avg > 0:
            record_poll_snapshot(our_avg, gap)

        # Lag 상관 분석
        lag_analysis = compute_lag_correlation()

        # Gap 2: Forecast
        forecast = compute_forecast(
            leading_index=leading_index.index,
            leading_direction=leading_index.direction,
            lag_analysis=lag_analysis,
            current_gap=gap,
            current_our=our_avg,
            momentum=polling_trend.get("momentum", "stable"),
            days_left=days_left,
        )

        # Gap 3: Learning Feedback
        feedback_profile = build_feedback_profile()

        # confidence 자동 조정 (mode_decision)
        adjusted_mode_confidence = adjust_confidence(
            mode_decision.confidence, "campaign_mode", mode_decision.mode,
        )

        # V2 enrichment에 추가
        _v2_enrichment_cache["leading_index"] = leading_index.to_dict()
        _v2_enrichment_cache["lag_analysis"] = lag_analysis.to_dict()
        _v2_enrichment_cache["forecast"] = forecast.to_dict()
        _v2_enrichment_cache["learning"] = feedback_profile.to_dict()
        _v2_enrichment_cache["national_poll"] = national_poll_data.to_dict() if national_poll_data else None
        _v2_enrichment_cache["economic"] = economic_data.to_dict() if economic_data else None

        # 투표율 예측 (v3)
        try:
            from engines.turnout_predictor import predict_turnout
            turnout_pred = predict_turnout(
                honeymoon_score=national_poll_data.honeymoon_score if national_poll_data else 0,
                reaction_index_avg=sum(
                    (ri.final_score if hasattr(ri, 'final_score') else ri.get('final_score', 0))
                    for ri in reaction_index_map.values()
                ) / max(len(reaction_index_map), 1) if reaction_index_map else 0,
                poll_gap=polling_result.get("gap", 0),
                org_endorsement_count=sum(o.endorsement_count for o in org_signal_map.values()) if org_signal_map else 0,
                economic_sentiment=economic_data.economic_sentiment if economic_data else 0,
            )
            _v2_enrichment_cache["turnout"] = turnout_pred.to_dict()
        except Exception as e:
            print(f"[Turnout] Warning: {e}")
        _v2_enrichment_cache["mode_decision"]["confidence"] = adjusted_mode_confidence
        _v2_enrichment_cache["mode_decision"]["original_confidence"] = mode_decision.confidence

        # 일일 인덱스 스냅샷 저장 (v4)
        try:
            from engines.index_tracker import DailySnapshot, save_daily_snapshot
            from datetime import date as _date
            rx_avg = sum(
                (ri.final_score if hasattr(ri, 'final_score') else ri.get('final_score', 0))
                for ri in reaction_index_map.values()
            ) / max(len(reaction_index_map), 1) if reaction_index_map else 0
            ix_avg = sum(
                (ii.index if hasattr(ii, 'index') else ii.get('index', 0))
                for ii in issue_index_map.values()
            ) / max(len(issue_index_map), 1) if issue_index_map else 0

            # 우리 vs 상대 키워드 분리
            opp_names = config.opponents if hasattr(config, 'opponents') else ["박완수"]
            our_ii, our_ri, opp_ii, opp_ri = [], [], [], []
            for kw, ii_val in issue_index_map.items():
                score = ii_val.index if hasattr(ii_val, 'index') else ii_val.get('index', 0)
                is_opp = any(o in kw for o in opp_names)
                if is_opp:
                    opp_ii.append(score)
                else:
                    our_ii.append(score)
            for kw, ri_val in reaction_index_map.items():
                score = ri_val.final_score if hasattr(ri_val, 'final_score') else ri_val.get('final_score', 0)
                is_opp = any(o in kw for o in opp_names)
                if is_opp:
                    opp_ri.append(score)
                else:
                    our_ri.append(score)

            snap = DailySnapshot(
                date=_date.today().isoformat(),
                leading_index=leading_index.index,
                leading_direction=leading_index.direction,
                issue_index_avg=round(sum(our_ii) / max(len(our_ii), 1), 1) if our_ii else round(ix_avg, 1),
                reaction_index_avg=round(sum(our_ri) / max(len(our_ri), 1), 1) if our_ri else round(rx_avg, 1),
                opp_issue_avg=round(sum(opp_ii) / max(len(opp_ii), 1), 1) if opp_ii else 0,
                opp_reaction_avg=round(sum(opp_ri) / max(len(opp_ri), 1), 1) if opp_ri else 0,
                attribution_confidence_avg=round(
                    sum(a.confidence for a in attributions) / max(len(attributions), 1), 2
                ) if attributions else 0,
                attribution_count=len(attributions) if attributions else 0,
                support_forecast_kim=forecast.scenarios[1].our_change if hasattr(forecast, 'scenarios') and len(forecast.scenarios) > 1 else 0,
                support_forecast_gap=polling_result.get("gap", 0),
                turnout_predicted_gap=turnout_pred.base_scenario.gap if turnout_pred and turnout_pred.base_scenario else 0,
                poll_actual_kim=polling_result.get("our_avg", 0),
                actions_count=len(attributions) if attributions else 0,
                data_quality="high" if len(issue_index_map) >= 5 else "medium" if len(issue_index_map) >= 2 else "low",
            )
            save_daily_snapshot(snap)
            _mark_run("index_tracker")
            _mark_run("leading_index")
            print(f"[IndexTracker] Daily snapshot saved: {_date.today()}")
        except Exception as e:
            print(f"[IndexTracker] Warning: {e}")

        # 여론조사 자동 수집
        try:
            from collectors.poll_auto_collector import extract_polls_from_news
            auto_polls = extract_polls_from_news()
            if auto_polls:
                _v2_enrichment_cache["auto_polls"] = [p.to_dict() for p in auto_polls]
                _mark_run("poll_auto")
                print(f"[PollAuto] {len(auto_polls)}건 여론조사 감지")
        except Exception as e:
            print(f"[PollAuto] Warning: {e}")

        # AI 브리핑 생성
        try:
            from engines.ai_briefing import generate_briefing
            top_iss = [{"keyword": iss.keyword, "score": iss.score,
                        "mention_count": getattr(iss, 'mention_count', 0),
                        "sentiment": "긍정" if getattr(iss, 'negative_ratio', 0.5) < 0.3 else "부정" if getattr(iss, 'negative_ratio', 0.5) > 0.5 else "중립"}
                       for iss in issue_scores[:5]]
            briefing_result = generate_briefing(
                poll_kim=polling_result.get("our_avg", 0),
                poll_park=polling_result.get("our_avg", 0) - polling_result.get("gap", 0),
                poll_source="최근 여론조사",
                leading_index=leading_index.index,
                leading_direction=leading_index.direction,
                leading_delta=leading_index.index_delta,
                turnout_gap=turnout_pred.base_scenario.gap if turnout_pred and turnout_pred.base_scenario else 0,
                top_issues=top_iss,
                president_approval=national_poll_data.president_approval if national_poll_data else 0,
                party_gap=0,
                crisis_count=sum(1 for iss in issue_scores if str(iss.level) == "CRISIS"),
                crisis_issues=[iss.keyword for iss in issue_scores if str(iss.level) == "CRISIS"][:3],
            )
            _v2_enrichment_cache["ai_briefing"] = briefing_result.to_dict()
            _mark_run("ai_briefing")
            print(f"[AI Briefing] Generated: {briefing_result.headline[:50]}")
        except Exception as e:
            print(f"[AI Briefing] Warning: {e}")

    except Exception as e:
        print(f"[V2 Gap Fill] Warning: {e}")

    # --- 이슈 대응 캐시 갱신 (채널 데이터 + readiness 포함) ---
    try:
        from engines.issue_response import IssueResponseEngine
        ir_engine = IssueResponseEngine(config)
        ir_responses = ir_engine.analyze_all(issue_scores, signals, readiness_map=readiness_map)

        # 시그널에서 채널 데이터 추출
        sig_map = {s.keyword: s for s in signals}
        resp_list = []
        for r in ir_responses:
            sig = sig_map.get(r.keyword)
            expl = explanation_map.get(r.keyword)
            rdns = readiness_map.get(r.keyword)
            anom = anomaly_map.get(r.keyword)
            entry = {
                "keyword": r.keyword, "score": r.score, "level": r.level.name,
                "stance": r.stance, "stance_reason": r.stance_reason,
                "owner": r.owner, "urgency": r.urgency, "golden_time": r.golden_time_hours,
                "response_message": r.response_message, "talking_points": r.talking_points,
                "do_not_say": r.do_not_say, "related_pledges": r.related_pledges,
                "pivot_to": r.pivot_to, "lifecycle": r.lifecycle,
                "trend": r.trend_direction, "duration": r.estimated_duration,
                "scenario_best": r.scenario_best, "scenario_worst": r.scenario_worst,
                "channels": {
                    "news": sig.mention_count if sig else 0,
                    "blog": 0, "cafe": 0, "video": 0,
                    "total": sig.mention_count if sig else 0,
                    "prev_total": 0, "change": 0, "change_pct": 0,
                    "youtube": 0, "yt_views": 0,
                },
                "top_blogs": [], "top_cafe": [], "top_youtube": [],
                "trend_data": {},
                # V2 enrichment
                "score_explanation": expl.to_dict() if expl else None,
                "readiness": {
                    "fact": rdns.fact_readiness,
                    "message": rdns.message_readiness,
                    "legal": rdns.legal_readiness,
                    "total": rdns.total_readiness,
                    "grade": rdns.readiness_grade,
                } if rdns else None,
                "anomaly": {
                    "surprise": anom.surprise_score,
                    "is_anomaly": anom.is_anomaly,
                    "reason": anom.anomaly_reason,
                } if anom else None,
            }
            resp_list.append(entry)

        global _issue_response_cache
        _issue_response_cache["data"] = {
            "responses": resp_list,
            "guide": _build_guide(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception:
        pass

    # --- 뉴스 클러스터링 (오늘의 전장) ---
    try:
        news_clusters = _run_news_clustering(config)
        _v2_enrichment_cache["news_clusters"] = news_clusters
        _v2_enrichment_cache["news_clusters_timestamp"] = datetime.now().isoformat()
        print(f"[Pipeline] News clustering: {len(news_clusters)}개 클러스터")
    except Exception as e:
        print(f"[NewsClustering] Warning: {e}")

    # --- 엔리치먼트 캐시 스냅샷 저장 (재시작 후 복원용) ---
    _save_enrichment_snapshot()

    # --- Build response ---
    return {
        "candidate": config.candidate_name,
        "election_type": config.election_type,
        "main_opponent": config.opponents[0] if config.opponents else "",
        "strategy": {
            "mode": mode_decision.mode,
            "mode_korean": mode_decision.mode_korean,
            "mode_confidence": mode_decision.confidence,
            "mode_reasoning": mode_decision.reasoning,
            "dominant_pressure": mode_decision.dominant_pressure,
            "pressures": {
                "crisis": round(mode_decision.pressures.crisis_pressure, 1),
                "polling_gap": round(mode_decision.pressures.polling_gap_pressure, 1),
                "momentum": round(mode_decision.pressures.momentum_pressure, 1),
                "opportunity": round(mode_decision.pressures.opportunity_pressure, 1),
            },
            "top_priority": strategy.top_priority,
            "key_messages": strategy.key_messages,
            "win_probability": strategy.win_probability,
            "risk_level": strategy.risk_level,
            "days_left": strategy.days_left,
        },
        "issues": [
            {
                "keyword": s.keyword,
                "score": s.score,
                "level": s.level.name,
                "mention_count": (
                    sig.mention_count
                    if (
                        sig := next(
                            (x for x in signals if x.keyword == s.keyword), None
                        )
                    )
                    else 0
                ),
                # V2 enrichment
                "explanation": explanation_map[s.keyword].to_dict() if s.keyword in explanation_map else None,
                "anomaly": {
                    "surprise": anomaly_map[s.keyword].surprise_score,
                    "is_anomaly": anomaly_map[s.keyword].is_anomaly,
                    "is_surge": anomaly_map[s.keyword].is_surge,
                    "reason": anomaly_map[s.keyword].anomaly_reason,
                } if s.keyword in anomaly_map else None,
                "issue_index": issue_index_map[s.keyword].to_dict() if s.keyword in issue_index_map else None,
                "reaction_index": reaction_index_map[s.keyword].to_dict() if s.keyword in reaction_index_map else None,
                "readiness": {
                    "total": readiness_map[s.keyword].total_readiness,
                    "grade": readiness_map[s.keyword].readiness_grade,
                    "fact": readiness_map[s.keyword].fact_readiness,
                    "message": readiness_map[s.keyword].message_readiness,
                    "legal": readiness_map[s.keyword].legal_readiness,
                } if s.keyword in readiness_map else None,
            }
            for s in issue_scores
        ],
        "regions": [
            {
                "region": s.region,
                "priority": s.priority_score,
                "heat": s.local_issue_heat,
                "swing": s.swing_index,
                "voters": s.voter_count,
            }
            for s in voter_segments
        ],
        "opponents": [
            {
                "name": s.opponent_name,
                "mentions": s.recent_mentions,
                "attack_prob": s.attack_prob_72h,
                "action": s.recommended_action,
            }
            for s in opponent_signals
        ],
        "polling": polling_result,
        "attacks": attack_points[:5],
    }


# ---------------------------------------------------------------------------
# Keyword Monitor — CRUD for monitor_keywords.json
# ---------------------------------------------------------------------------

_KEYWORDS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "monitor_keywords.json",
)


def _load_keywords():
    try:
        with open(_KEYWORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"keywords": [], "updated_at": ""}


def _save_keywords(data):
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(_KEYWORDS_FILE), exist_ok=True)
    with open(_KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/api/v2/keywords")
async def api_v2_keywords():
    """키워드 목록 조회."""
    return _load_keywords()


@app.post("/api/v2/keywords")
async def api_v2_keywords_add(request: Request):
    """키워드 추가."""
    body = await request.json()
    keyword = body.get("keyword", "").strip()
    category = body.get("category", "기타").strip()
    priority = body.get("priority", "medium").strip()
    kw_type = body.get("type", "issue").strip()
    if kw_type not in ("candidate", "issue"):
        kw_type = "issue"
    if not keyword:
        return JSONResponse({"error": "키워드를 입력하세요"}, status_code=400)
    data = _load_keywords()
    # 중복 체크
    if any(k["keyword"] == keyword for k in data["keywords"]):
        return JSONResponse({"error": f"'{keyword}' 이미 존재합니다"}, status_code=409)
    data["keywords"].append({"keyword": keyword, "category": category, "priority": priority, "type": kw_type})
    _save_keywords(data)
    return {"ok": True, "total": len(data["keywords"])}


@app.delete("/api/v2/keywords")
async def api_v2_keywords_delete(request: Request):
    """키워드 삭제."""
    body = await request.json()
    keyword = body.get("keyword", "").strip()
    if not keyword:
        return JSONResponse({"error": "삭제할 키워드를 입력하세요"}, status_code=400)
    data = _load_keywords()
    before = len(data["keywords"])
    data["keywords"] = [k for k in data["keywords"] if k["keyword"] != keyword]
    if len(data["keywords"]) == before:
        return JSONResponse({"error": f"'{keyword}' 찾을 수 없습니다"}, status_code=404)
    _save_keywords(data)
    return {"ok": True, "total": len(data["keywords"])}


@app.get("/api/v2/news-clusters")
async def api_v2_news_clusters(session_token: str = Cookie(default=None)):
    """오늘의 뉴스 클러스터 — 사건별 묶기 + 진영 영향도."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    if not _v2_enrichment_cache:
        return {"clusters": [], "timestamp": ""}
    return {
        "clusters": _v2_enrichment_cache.get("news_clusters", []),
        "timestamp": _v2_enrichment_cache.get("news_clusters_timestamp", ""),
    }


@app.get("/api/v2/strategic-report")
async def api_v2_strategic_report(session_token: str = Cookie(default=None)):
    """전략대응 리포트 — data/strategic_report_*.md 중 최신 파일을 HTML로 반환."""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    import glob as _glob
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    files = sorted(_glob.glob(os.path.join(data_dir, "strategic_report_*.md")), reverse=True)
    if not files:
        return {"html": "<p style='color:#78909c'>리포트가 없습니다. 리포트를 먼저 생성해주세요.</p>", "filename": "", "date": ""}
    latest = files[0]
    with open(latest, "r", encoding="utf-8") as f:
        md_text = f.read()
    # Simple markdown → HTML conversion (no external dependency)
    import re as _re
    html = md_text
    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Headers
    html = _re.sub(r"^######\s+(.+)$", r"<h6>\1</h6>", html, flags=_re.M)
    html = _re.sub(r"^#####\s+(.+)$", r"<h5>\1</h5>", html, flags=_re.M)
    html = _re.sub(r"^####\s+(.+)$", r"<h4>\1</h4>", html, flags=_re.M)
    html = _re.sub(r"^###\s+(.+)$", r"<h3>\1</h3>", html, flags=_re.M)
    html = _re.sub(r"^##\s+(.+)$", r"<h2>\1</h2>", html, flags=_re.M)
    html = _re.sub(r"^#\s+(.+)$", r"<h1>\1</h1>", html, flags=_re.M)
    # Bold & italic
    html = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = _re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    # Inline code
    html = _re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # Blockquote
    html = _re.sub(r"^&gt;\s*(.+)$", r"<blockquote>\1</blockquote>", html, flags=_re.M)
    # HR
    html = _re.sub(r"^---+$", r"<hr>", html, flags=_re.M)
    # Table conversion
    lines = html.split("\n")
    out_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(_re.match(r"^[-:]+$", c) for c in cells):
                continue  # separator row
            if not in_table:
                out_lines.append("<table>")
                tag = "th"
                in_table = True
            else:
                tag = "td"
            row = "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
            out_lines.append(row)
        else:
            if in_table:
                out_lines.append("</table>")
                in_table = False
            out_lines.append(line)
    if in_table:
        out_lines.append("</table>")
    html = "\n".join(out_lines)
    # Lists
    html = _re.sub(r"^(\d+)\.\s+(.+)$", r"<li>\2</li>", html, flags=_re.M)
    html = _re.sub(r"^[-*]\s+(.+)$", r"<li>\1</li>", html, flags=_re.M)
    # Wrap consecutive <li> lines with <ul>
    html = _re.sub(r"(?:(?:^|\n)<li>.*?</li>)+", lambda m: "<ul>" + m.group(0) + "</ul>", html, flags=_re.S)
    # Paragraphs for remaining plain lines
    final_lines = []
    for line in html.split("\n"):
        stripped = line.strip()
        if not stripped:
            final_lines.append("")
        elif stripped.startswith("<"):
            final_lines.append(line)
        else:
            final_lines.append(f"<p>{line}</p>")
    html = "\n".join(final_lines)
    fname = os.path.basename(latest)
    # Extract date from filename
    date_match = _re.search(r"(\d{8})", fname)
    date_str = f"{date_match.group(1)[:4]}-{date_match.group(1)[4:6]}-{date_match.group(1)[6:]}" if date_match else ""
    return {"html": html, "filename": fname, "date": date_str}


@app.get("/api/v2/candidate-buzz")
async def api_v2_candidate_buzz():
    """후보 버즈 모니터링 데이터 (이슈 스코어링과 분리)."""
    if not _v2_enrichment_cache:
        return {"buzz": {}, "timestamp": ""}
    buzz = _v2_enrichment_cache.get("candidate_buzz", {})
    return {"buzz": buzz, "timestamp": _v2_enrichment_cache.get("timestamp", "")}


@app.post("/api/run-strategy")
async def run_strategy(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    global _last_run_time, _strategy_running
    now = time.time()

    if _strategy_running:
        return JSONResponse({"error": "갱신 진행 중입니다. 완료 후 다시 시도해주세요."}, status_code=429)

    if now - _last_run_time < RATE_LIMIT_SECONDS:
        remaining = int(RATE_LIMIT_SECONDS - (now - _last_run_time))
        return JSONResponse({"error": f"{remaining}초 후에 다시 시도해주세요."}, status_code=429)

    _last_run_time = now
    _strategy_running = True
    try:
        result = await run_in_threadpool(_run_strategy_sync)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        _strategy_running = False
