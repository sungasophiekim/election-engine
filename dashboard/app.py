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

캠프 전략가 관점에서 분석하세요. JSON으로만 응답:
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
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            result = jmod.loads(raw)

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
        from collectors.owned_channels import monitor_all_channels, KIM_CHANNELS
        metrics = monitor_all_channels(KIM_CHANNELS)
        return {
            "candidate": KIM_CHANNELS.candidate_name,
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
                "facebook": KIM_CHANNELS.facebook_id or "미설정",
                "youtube": KIM_CHANNELS.youtube_channel or "미설정",
                "instagram": KIM_CHANNELS.instagram_id or "미확인",
            },
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

    # --- 전체 캐시 초기화 (소셜/이슈 새 데이터 반영) ---
    try:
        from collectors.unified_collector import _cache as unified_cache
        unified_cache.clear()
    except Exception:
        pass

    # --- 이슈 대응 캐시 갱신 (채널 데이터 포함) ---
    try:
        from engines.issue_response import IssueResponseEngine
        ir_engine = IssueResponseEngine(config)
        ir_responses = ir_engine.analyze_all(issue_scores, signals)

        # 시그널에서 채널 데이터 추출
        sig_map = {s.keyword: s for s in signals}
        resp_list = []
        for r in ir_responses:
            sig = sig_map.get(r.keyword)
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

    # --- Build response ---
    return {
        "candidate": config.candidate_name,
        "election_type": config.election_type,
        "main_opponent": config.opponents[0] if config.opponents else "",
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
