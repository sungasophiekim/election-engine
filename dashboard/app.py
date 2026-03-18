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
from datetime import datetime
from typing import Optional

from fastapi import Cookie, FastAPI, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="Election Engine Dashboard")
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

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
RATE_LIMIT_SECONDS = 60


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
    return templates.TemplateResponse("index.html", {"request": request})


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
        return [dict(r) for r in rows]


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
        opponent_name = body.get("opponent_name", "박완수")
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


@app.get("/api/polls")
async def api_list_polls(session_token: str = Cookie(default=None)):
    """저장된 여론조사 전체 목록"""
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)
    with get_db() as db:
        return db.get_all_polls()


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
            "digital_buzz": 0,  # social collector 연동 시 채움
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
        from collectors.social_collector import compare_candidate_buzz, collect_social_signals
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        config = SAMPLE_GYEONGNAM_CONFIG

        buzz = compare_candidate_buzz(config.candidate_name, config.opponents)
        signals = collect_social_signals(
            ["경남도지사 선거", "부울경 행정통합", "경남 우주항공"],
            candidate_name=config.candidate_name,
            opponents=config.opponents,
        )
        summary = signals.get("summary", {})
        return {"buzz": buzz, "summary": summary}

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
        return {
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
    """Synchronous strategy pipeline — runs in threadpool."""
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

    config = SAMPLE_GYEONGNAM_CONFIG

    # --- Collect signals ---
    signals = collect_issue_signals(
        [
            "경남도지사 선거",
            "경남도지사 공약",
            f"{config.candidate_name} 경남",
            "경남 조선업 일자리",
            "경남 교통 BRT",
            "경남 청년 정책",
            "부울경 행정통합",
            "경남 우주항공",
            "김경수 경남",
            "창원 특례시",
        ],
        candidate_name=config.candidate_name,
        opponents=config.opponents,
    )

    if not signals:
        return {"error": "뉴스 수집 실패 — 네이버 API를 확인하세요."}

    # --- Analyze ---
    issue_scores = sorted(
        [calculate_issue_score(sig, config) for sig in signals],
        key=lambda x: x.score,
        reverse=True,
    )

    voter_segments = calculate_voter_priorities(config, issue_scores)
    opponent_data = collect_opponent_data(config.opponents, region=config.region)
    opponent_signals = analyze_opponents(config, opponent_data, issue_scores)

    polling = PollingTracker(config)
    polling_result = polling.calculate_win_probability()

    comparator = PledgeComparator(config)
    attack_points = comparator.find_attack_points(config.opponents[0] if config.opponents else "")
    defense_points = comparator.find_defense_points()

    synthesizer = StrategySynthesizer(config)
    strategy = synthesizer.synthesize(
        issue_scores=issue_scores,
        opponent_signals=opponent_signals,
        voter_segments=voter_segments,
        polling_data=polling_result,
        attack_points=attack_points,
        defense_points=defense_points,
    )

    # --- Persist ---
    db = ElectionDB()
    try:
        db.save_issue_scores(issue_scores, signals)
        db.save_voter_priorities(voter_segments)
        db.save_opponent_signals(opponent_signals)
    finally:
        db.close()

    # --- Build response ---
    return {
        "strategy": {
            "mode": strategy.campaign_mode.value,
            "mode_reasoning": strategy.mode_reasoning,
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


@app.post("/api/run-strategy")
async def run_strategy(session_token: str = Cookie(default=None)):
    if not check_auth(session_token):
        return JSONResponse({"error": "인증 필요"}, status_code=401)

    global _last_run_time
    now = time.time()
    if now - _last_run_time < RATE_LIMIT_SECONDS:
        remaining = int(RATE_LIMIT_SECONDS - (now - _last_run_time))
        return JSONResponse(
            {"error": f"{remaining}초 후에 다시 시도해주세요."},
            status_code=429,
        )

    _last_run_time = now
    try:
        result = await run_in_threadpool(_run_strategy_sync)
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
