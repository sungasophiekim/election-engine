"""텔레그램 봇 v2 — 버튼형 UI + Alert 시스템 + AI 학습 피드백"""
import os
import json
import threading
import time
import httpx
from pathlib import Path
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

from v1config.settings import LEGACY_DATA as _DATA
CORRECTIONS_PATH = _DATA / "side_corrections.json"
ENRICHMENT_PATH = _DATA / "enrichment_snapshot.json"
CUSTOM_KEYWORDS_PATH = _DATA / "custom_keywords.json"
HISTORY_PATH = _DATA / "indices_history.json"
WHITELIST_PATH = _DATA / "telegram_whitelist.json"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://election-engine.onrender.com")


def _load_whitelist() -> dict:
    """화이트리스트 로드 — user_ids + chat_ids"""
    try:
        with open(WHITELIST_PATH) as f:
            return json.load(f)
    except Exception:
        return {"user_ids": [], "chat_ids": [], "open": True}  # 초기엔 open=True


def _save_whitelist(wl: dict):
    _DATA.mkdir(parents=True, exist_ok=True)
    with open(WHITELIST_PATH, "w") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)


def _is_allowed(user_id: int, chat_id: int) -> bool:
    """화이트리스트 체크 — open=True면 모두 허용, False면 등록된 ID만"""
    wl = _load_whitelist()
    if wl.get("open", True):
        return True
    return user_id in wl.get("user_ids", []) or chat_id in wl.get("chat_ids", [])

# ── 대화 상태 관리 (chat_id → state) ──
_user_state: dict = {}

# ── Alert 대상 chat_id 저장 ──
_alert_chats: set = set()


# ═══════════════════════════════════════
# 데이터 로더
# ═══════════════════════════════════════
def _load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _snap():
    return _load(ENRICHMENT_PATH)

def _to_kst(iso_str: str) -> str:
    """UTC ISO 문자열 → KST 'YYYY-MM-DD HH:MM' 변환"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str[:16].replace("T", " ")

def _corrections():
    return _load(CORRECTIONS_PATH, {"corrections": [], "rules": []})

def _custom_kws():
    return _load(CUSTOM_KEYWORDS_PATH, [])

def _history():
    return _load(HISTORY_PATH, [])


# ═══════════════════════════════════════
# 토큰 + API 헬퍼
# ═══════════════════════════════════════
def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        env_path = _DATA.parent / ".env"
        if env_path.exists():
            for line in open(env_path):
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip()
    return token.replace("\n", "").replace("\r", "")


def _send(base, chat_id, text, buttons=None, edit_msg=None):
    """메시지 전송 (버튼 포함)"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})

    try:
        if edit_msg:
            payload["message_id"] = edit_msg
            httpx.post(f"{base}/editMessageText", json=payload, timeout=10)
        else:
            httpx.post(f"{base}/sendMessage", json=payload, timeout=10)
    except Exception:
        pass


# ═══════════════════════════════════════
# Alert 시스템 — 외부에서 호출
# ═══════════════════════════════════════
def send_alert(text: str, buttons=None):
    """스케줄러에서 Alert 발송 시 호출"""
    token = _get_token()
    if not token or not _alert_chats:
        return
    base = f"https://api.telegram.org/bot{token}"
    for chat_id in _alert_chats:
        _send(base, chat_id, text, buttons)


# ═══════════════════════════════════════
# 메인 메뉴
# ═══════════════════════════════════════
def _main_menu(snap=None):
    if not snap:
        snap = _snap()
    ci = snap.get("cluster_issue", {})
    cr = snap.get("cluster_reaction", {})
    corr = snap.get("turnout", {}).get("correction", {})
    d_day = corr.get("d_day", "?")

    def g(v):
        return "우세" if v > 55 else "열세" if v < 45 else "접전"

    issue = ci.get("issue_index", 50)
    reaction = cr.get("reaction_index", 50)
    pandse = corr.get("pandse_index", 50)
    ts = _to_kst(snap.get("timestamp", ""))

    text = f"""🏛 <b>김경수 캠프 AI 전략 어시스턴트</b>

이슈 <b>{issue:.1f}pt</b> {g(issue)} | 반응 <b>{reaction:.1f}pt</b> {g(reaction)} | 판세 <b>{pandse:.1f}pt</b> {g(pandse)}

D-{d_day} · 갱신 {ts}"""

    buttons = [
        [{"text": "📊 대시보드", "callback_data": "dashboard"}, {"text": "📡 TOP 이슈", "callback_data": "issues"}],
        [{"text": "🧠 민심 레이더", "callback_data": "radar"}, {"text": "📈 지수 현황", "callback_data": "indices"}],
        [{"text": "🔧 이슈 수정", "callback_data": "fix_menu"}, {"text": "🔍 키워드 관리", "callback_data": "kw_menu"}],
        [{"text": "📋 데일리 요약", "callback_data": "daily"}, {"text": "📌 규칙 목록", "callback_data": "rules"}],
        [{"text": "✏️ 전략 메모", "callback_data": "memo_menu"}, {"text": "🔧 시스템 상태", "callback_data": "sys_status"}],
        [{"text": "🚀 시스템 관리", "callback_data": "sys_admin"}],
    ]
    return text, buttons


# ═══════════════════════════════════════
# 콜백 핸들러
# ═══════════════════════════════════════
def _handle_callback(cb_data, chat_id, msg_id, base):
    """인라인 버튼 콜백 처리"""
    snap = _snap()
    back = [[{"text": "◀ 메뉴", "callback_data": "menu"}]]

    if cb_data == "menu":
        text, buttons = _main_menu(snap)
        _send(base, chat_id, text, buttons, edit_msg=msg_id)

    elif cb_data == "dashboard":
        _cb_dashboard(snap, chat_id, msg_id, base, back)

    elif cb_data == "issues":
        _cb_issues(snap, chat_id, msg_id, base, back)

    elif cb_data == "radar":
        _cb_radar(snap, chat_id, msg_id, base, back)

    elif cb_data == "indices":
        _cb_indices(snap, chat_id, msg_id, base, back)

    elif cb_data == "daily":
        _cb_daily(chat_id, msg_id, base, back)

    elif cb_data == "fix_menu":
        _cb_fix_menu(snap, chat_id, msg_id, base)

    elif cb_data.startswith("fix_"):
        _cb_fix_issue(cb_data, snap, chat_id, msg_id, base)

    elif cb_data.startswith("side_"):
        _cb_set_side(cb_data, chat_id, msg_id, base)

    elif cb_data == "kw_menu":
        _cb_kw_menu(chat_id, msg_id, base)

    elif cb_data.startswith("kwdel_"):
        _cb_kw_delete(cb_data, chat_id, msg_id, base)

    elif cb_data == "rules":
        _cb_rules(chat_id, msg_id, base, back)

    elif cb_data == "sys_status":
        _cb_sys_status(snap, chat_id, msg_id, base, back)

    elif cb_data == "sys_admin":
        _cb_sys_admin(chat_id, msg_id, base, back)

    elif cb_data == "sys_collect":
        _cb_sys_collect(chat_id, msg_id, base, back)

    elif cb_data == "sys_restart":
        _cb_sys_restart(chat_id, msg_id, base, back)

    elif cb_data == "sys_deploy":
        _cb_sys_deploy(chat_id, msg_id, base, back)

    elif cb_data == "sys_log":
        _cb_sys_log(chat_id, msg_id, base, back)

    elif cb_data == "memo_menu":
        _cb_memo_menu(chat_id, msg_id, base, back)

    elif cb_data.startswith("memo_cat_"):
        cat = cb_data.replace("memo_cat_", "")
        _user_state[chat_id] = {"action": "awaiting_memo", "category": cat}
        cat_labels = {"memo": "자유 메모", "what_worked": "성공 사례", "what_failed": "실패/문제", "correction": "판단 수정"}
        _send(base, chat_id,
              f"✏️ <b>{cat_labels.get(cat, '메모')}</b>\n\n내용을 입력하세요:\n(예: 봉암공단 방문 반응 좋았음, 제조업 종사자 호응 높았다)",
              [[{"text": "◀ 취소", "callback_data": "memo_menu"}]], edit_msg=msg_id)

    elif cb_data == "memo_history":
        _cb_memo_history(chat_id, msg_id, base, back)


def _cb_dashboard(snap, chat_id, msg_id, base, back):
    ci = snap.get("cluster_issue", {})
    cr = snap.get("cluster_reaction", {})
    corr = snap.get("turnout", {}).get("correction", {})
    hist = _history()[-24:]

    issue = ci.get("issue_index", 50)
    reaction = cr.get("reaction_index", 50)
    pandse = corr.get("pandse_index", 50)

    def bar(v):
        filled = int(v / 10)
        return "█" * filled + "░" * (10 - filled)

    def g(v):
        return "우세" if v > 55 else "열세" if v < 45 else "접전"

    # 24h 변동
    h24_text = ""
    if len(hist) >= 2:
        d_issue = issue - hist[0].get("issue_index", 50)
        d_reaction = reaction - hist[0].get("reaction_index", 50)
        d_pandse = pandse - hist[0].get("pandse", 50)
        def arrow(v): return "↑" if v > 0.5 else "↓" if v < -0.5 else "→"
        h24_text = f"\n24h: 이슈{d_issue:+.1f}{arrow(d_issue)} 반응{d_reaction:+.1f}{arrow(d_reaction)} 판세{d_pandse:+.1f}{arrow(d_pandse)}"

    text = f"""📊 <b>War Room 현황</b>

이슈  {bar(issue)} <b>{issue:.1f}pt</b> {g(issue)}
반응  {bar(reaction)} <b>{reaction:.1f}pt</b> {g(reaction)}
판세  {bar(pandse)} <b>{pandse:.1f}pt</b> {g(pandse)}
{h24_text}

D-{corr.get('d_day', '?')} · {snap.get('timestamp', '')[:16].replace('T', ' ')}"""

    buttons = [
        [{"text": "🔗 대시보드 열기", "url": DASHBOARD_URL}],
        [{"text": "📡 TOP 이슈", "callback_data": "issues"}, {"text": "📈 지수 상세", "callback_data": "indices"}],
        back[0],
    ]
    _send(base, chat_id, text, buttons, edit_msg=msg_id)


def _cb_issues(snap, chat_id, msg_id, base, back):
    clusters = snap.get("news_clusters") or []
    lines = ["📡 <b>TOP 이슈</b>\n"]
    if not clusters:
        lines.append("⚠ 이슈 데이터가 아직 없습니다.\n스케줄러 갱신을 기다려주세요.")
    for i, c in enumerate(clusters[:8], 1):
        side = c.get("side", "?")
        emoji = "🔵" if "우리" in side else "🔴" if "상대" in side else "⚪"
        lines.append(f"{emoji} <b>{i}. {c.get('name','')}</b>")
        lines.append(f"   {c.get('count',0)}건 | {side} | 감성{c.get('sentiment',0):+d}")
        if c.get("summary"):
            lines.append(f"   {c['summary'][:60]}")
        if c.get("why"):
            lines.append(f"   → {c['why'][:60]}")
        lines.append("")

    # AI 요약
    ai_issue = snap.get("ai_issue_summary", "")
    if ai_issue:
        lines.append(f"🤖 {ai_issue}")

    buttons = [
        [{"text": "🔧 수정하기", "callback_data": "fix_menu"}, {"text": "🧠 민심 레이더", "callback_data": "radar"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_radar(snap, chat_id, msg_id, base, back):
    cr = snap.get("cluster_reaction") or {}
    details = cr.get("details") or []
    lines = ["🧠 <b>민심 반응 레이더</b>\n"]

    if not details:
        lines.append("⚠ 민심 데이터가 아직 없습니다.\n스케줄러 갱신을 기다려주세요.")

    for det in details[:6]:
        kw = det.get("keyword", "")[:20]
        side = det.get("side", "?")
        tag = "🔍" if side == "커스텀" else ("🔵" if "우리" in side else "🔴" if "상대" in side else "⚪")
        sources = det.get("sources", {})

        # 소스별 요약
        parts = []
        for sname in ["blog", "cafe", "community", "youtube", "news_comments"]:
            s = sources.get(sname, {})
            cnt = s.get("count", 0) or s.get("comments", 0) or s.get("mentions", 0)
            sent = s.get("net_sentiment", 0)
            if cnt > 0:
                sn = {"blog": "블로그", "cafe": "카페", "community": "커뮤", "youtube": "유튜브", "news_comments": "댓글"}.get(sname, sname)
                parts.append(f"{sn} {cnt}건")

        lines.append(f"{tag} <b>{kw}</b>")
        if parts:
            lines.append(f"   {' · '.join(parts)}")

        # 커뮤니티 breakdown
        bd = sources.get("community", {}).get("breakdown", [])
        for b in bd[:2]:
            tone = "+" if b.get("sentiment", 0) > 0.1 else "-" if b.get("sentiment", 0) < -0.1 else "·"
            lines.append(f"   {tone} {b.get('name','')}: {b.get('mentions',0)}건")
        lines.append("")

    # AI 요약
    ai_rx = snap.get("ai_reaction_summary", "")
    if ai_rx:
        lines.append(f"🤖 {ai_rx}")

    buttons = [
        [{"text": "🔍 키워드 관리", "callback_data": "kw_menu"}, {"text": "📡 TOP 이슈", "callback_data": "issues"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_indices(snap, chat_id, msg_id, base, back):
    ci = snap.get("cluster_issue", {})
    cr = snap.get("cluster_reaction", {})
    corr = snap.get("turnout", {}).get("correction", {})
    hist = _history()[-24:]

    issue = ci.get("issue_index", 50)
    reaction = cr.get("reaction_index", 50)
    pandse = corr.get("pandse_index", 50)

    def g(v):
        return "우세" if v > 55 else "열세" if v < 45 else "접전"

    # 24h min/max
    h24 = ""
    if len(hist) >= 2:
        i_vals = [h.get("issue_index", 50) for h in hist]
        r_vals = [h.get("reaction_index", 50) for h in hist]
        p_vals = [h.get("pandse", 50) for h in hist]
        h24 = f"""
24h 범위:
  이슈 {min(i_vals):.1f} ~ {max(i_vals):.1f}
  반응 {min(r_vals):.1f} ~ {max(r_vals):.1f}
  판세 {min(p_vals):.1f} ~ {max(p_vals):.1f}"""

    # 판세 팩터 요약
    factors = corr.get("factors", [])
    f_text = ""
    if factors:
        top3 = sorted(factors, key=lambda f: abs(f.get("value", 0)), reverse=True)[:4]
        f_text = "\n판세 팩터:\n" + "\n".join(f"  {f['name']} {f['value']:+.1f}" for f in top3)

    text = f"""📈 <b>지수 현황</b>

이슈  <b>{issue:.1f}pt</b> ({g(issue)})
반응  <b>{reaction:.1f}pt</b> ({g(reaction)})
판세  <b>{pandse:.1f}pt</b> ({g(pandse)})
D-{corr.get('d_day', '?')}
{h24}{f_text}

갱신: {_to_kst(snap.get('timestamp', ''))}"""

    buttons = [
        [{"text": "📊 대시보드", "callback_data": "dashboard"}, {"text": "📡 TOP 이슈", "callback_data": "issues"}],
        back[0],
    ]
    _send(base, chat_id, text, buttons, edit_msg=msg_id)


def _cb_daily(chat_id, msg_id, base, back):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        fp = _DATA / "daily_reports" / f"{today}.json"
        if not fp.exists():
            # 어제 리포트
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            fp = _DATA / "daily_reports" / f"{yesterday}.json"
        if not fp.exists():
            _send(base, chat_id, "📋 데일리 리포트 없음\n대시보드에서 먼저 생성하세요.", back, edit_msg=msg_id)
            return
        with open(fp) as f:
            rpt = json.load(f)
    except Exception:
        _send(base, chat_id, "📋 리포트 로드 실패", back, edit_msg=msg_id)
        return

    summary = rpt.get("executive_summary", "요약 없음")
    theme = rpt.get("daily_theme", {})
    situation = rpt.get("situation_diagnosis", {})
    decision = rpt.get("decision_layer", {})
    strategies = rpt.get("strategies", [])
    urgent = [e for e in rpt.get("execution", []) if "즉시" in e.get("when", "") or "오늘" in e.get("when", "")]
    schedule = rpt.get("field_schedule", rpt.get("messages", []))
    risks = rpt.get("risk_management", [])

    lines = [f"📋 <b>데일리 전략 요약</b> ({rpt.get('date', '')})\n"]

    # 테마 + D-day
    d_day = rpt.get("d_day", "")
    if theme:
        lines.append(f"🏷 테마: <b>{theme.get('keyword', theme.get('theme', ''))}</b>" + (f" · D-{d_day}" if d_day else ""))

    # 핵심 진단
    lines.append(f"\n🔍 <b>핵심 진단</b>")
    # 요약을 문장 단위로 불렛
    for sent in summary.split(". "):
        sent = sent.strip().rstrip(".")
        if sent:
            lines.append(f"  • {sent}")

    # 국면 판단
    moment = decision.get("moment_type", decision.get("phase", ""))
    if moment:
        lines.append(f"\n🎯 <b>국면: {moment}</b>")
    protect = decision.get("must_protect", decision.get("defend", ""))
    push = decision.get("can_push", decision.get("push", ""))
    if protect:
        lines.append(f"  🛡 지켜야 할 것: {protect}")
    if push:
        lines.append(f"  🗡 밀어볼 것: {push}")

    # 긴급 액션
    if urgent:
        lines.append(f"\n⚡ <b>긴급 액션</b>")
        nums = "①②③④⑤"
        for i, e in enumerate(urgent[:3]):
            lines.append(f"  {nums[i]} {e.get('what','')}")

    # TOP 이슈 (상위 5개)
    issues = situation.get("issue_state", [])
    if issues:
        lines.append(f"\n📡 <b>TOP 이슈</b>")
        for iss in issues[:5]:
            side_icon = "🔵" if "우리" in str(iss.get("side", "")) else "🔴" if "상대" in str(iss.get("side", "")) else "⚪"
            lines.append(f"  {side_icon} {iss.get('name','')} ({iss.get('count',0)}건) — {iss.get('spreading','')}")

    # 전략 요약
    if strategies:
        lines.append(f"\n📐 <b>대응 전략</b>")
        for i, s in enumerate(strategies[:3], 1):
            timeline = s.get("timeline", "")
            is_urgent = "즉시" in timeline or "오늘" in timeline
            icon = "🔴" if is_urgent else "🔵"
            lines.append(f"  {icon} <b>{s.get('title','')}</b>")
            if s.get("action"):
                lines.append(f"     → {s['action']}")
            if s.get("target"):
                lines.append(f"     🎯 {s['target']}")

    # 현장 일정
    if schedule:
        lines.append(f"\n📍 <b>현장 일정</b>")
        for s in schedule[:3]:
            region = s.get("region", "")
            loc = s.get("location", "")
            msg = s.get("message", "")
            target = s.get("target_segment", s.get("target", ""))
            time_str = s.get("when", s.get("time", ""))
            lines.append(f"  • <b>{region}</b> {time_str}")
            if loc:
                lines.append(f"     📍 {loc}")
            if msg:
                lines.append(f"     💬 \"{msg}\"")
            if target:
                lines.append(f"     🎯 {target}")

    # 위기 관리
    if risks:
        lines.append(f"\n⛔ <b>위기 관리</b>")
        for r in risks[:3]:
            lines.append(f"  • {r.get('risk','')}: {r.get('response','')}")

    buttons = [
        [{"text": "🔗 전체 리포트", "url": f"{DASHBOARD_URL}"}],
        back[0],
    ]
    full_text = "\n".join(lines)
    # 텔레그램 4096자 제한: 초과 시 분할 전송
    if len(full_text) > 4000:
        # 첫 메시지: 핵심 진단 + 국면 + 긴급 액션 (edit)
        split_idx = full_text.find("\n📡 ")
        if split_idx == -1:
            split_idx = 3900
        _send(base, chat_id, full_text[:split_idx], None, edit_msg=msg_id)
        # 두 번째 메시지: 나머지 + 버튼 (새 메시지)
        _send(base, chat_id, full_text[split_idx:], buttons)
    else:
        _send(base, chat_id, full_text, buttons, edit_msg=msg_id)


def _cb_fix_menu(snap, chat_id, msg_id, base):
    clusters = snap.get("news_clusters", [])
    lines = ["🔧 <b>이슈 판정 수정</b>\n수정할 이슈를 선택하세요:"]
    buttons = []
    for i, c in enumerate(clusters[:8]):
        side = c.get("side", "?")
        emoji = "🔵" if "우리" in side else "🔴" if "상대" in side else "⚪"
        lines.append(f"{emoji} {i+1}. {c.get('name','')[:20]} ({side})")
        buttons.append([{"text": f"{i+1}. {c.get('name','')[:18]}", "callback_data": f"fix_{i}"}])
    buttons.append([{"text": "◀ 메뉴", "callback_data": "menu"}])
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_memo_menu(chat_id, msg_id, base, back):
    """전략 메모 메뉴 — 카테고리 선택"""
    text = ("✏️ <b>전략 메모</b>\n\n"
            "캠프 현장 판단을 기록하면\n"
            "🧠 다음 AI 리포트에 학습·반영됩니다.\n\n"
            "카테고리를 선택하세요:")
    buttons = [
        [{"text": "📝 자유 메모", "callback_data": "memo_cat_memo"}],
        [{"text": "✅ 성공 사례", "callback_data": "memo_cat_what_worked"}, {"text": "❌ 실패/문제", "callback_data": "memo_cat_what_failed"}],
        [{"text": "🔄 판단 수정", "callback_data": "memo_cat_correction"}],
        [{"text": "📜 최근 메모 보기", "callback_data": "memo_history"}],
        back[0],
    ]
    _send(base, chat_id, text, buttons, edit_msg=msg_id)


def _cb_memo_history(chat_id, msg_id, base, back):
    """최근 3일 메모 조회"""
    fb_dir = _DATA / "strategy_feedback"
    lines = ["📜 <b>최근 전략 메모</b>\n"]
    cat_icons = {"memo": "📝", "what_worked": "✅", "what_failed": "❌", "correction": "🔄"}
    found = False
    for i in range(3):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        fp = fb_dir / f"{d}.json"
        if not fp.exists():
            continue
        try:
            fb = json.load(open(fp))
            entries = fb.get("entries", [])
            if entries:
                found = True
                lines.append(f"<b>{d}</b>")
                for e in entries[-5:]:
                    icon = cat_icons.get(e.get("category", ""), "📝")
                    src = "📱" if e.get("source") == "telegram" else "💻"
                    lines.append(f"  {icon}{src} {e.get('text', '')[:80]}")
                lines.append("")
        except Exception:
            pass
    if not found:
        lines.append("아직 등록된 메모가 없습니다.\n✏️ 전략 메모를 등록해보세요!")
    lines.append("🧠 등록된 메모는 AI 리포트 생성 시 자동 반영됩니다.")
    buttons = [
        [{"text": "✏️ 메모 추가", "callback_data": "memo_menu"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_fix_issue(cb_data, snap, chat_id, msg_id, base):
    idx = int(cb_data.replace("fix_", ""))
    clusters = snap.get("news_clusters", [])
    if idx >= len(clusters):
        return
    c = clusters[idx]
    name = c.get("name", "")
    _user_state[chat_id] = {"action": "fix_reason", "issue": name, "idx": idx}

    text = f"🔧 <b>{name}</b>\n현재: {c.get('side','?')}\n\n변경할 판정:"
    buttons = [
        [{"text": "🔵 우리유리", "callback_data": f"side_{idx}_우리유리"}, {"text": "🔴 상대유리", "callback_data": f"side_{idx}_상대유리"}],
        [{"text": "⚪ 중립", "callback_data": f"side_{idx}_중립"}, {"text": "🟡 양면", "callback_data": f"side_{idx}_양면"}],
        [{"text": "◀ 뒤로", "callback_data": "fix_menu"}],
    ]
    _send(base, chat_id, text, buttons, edit_msg=msg_id)


def _cb_set_side(cb_data, chat_id, msg_id, base):
    parts = cb_data.replace("side_", "").split("_", 1)
    idx = int(parts[0])
    new_side = parts[1]

    snap = _snap()
    clusters = snap.get("news_clusters", [])
    if idx >= len(clusters):
        return
    name = clusters[idx].get("name", "")

    # 이유 입력 대기
    _user_state[chat_id] = {"action": "awaiting_reason", "issue": name, "side": new_side}
    text = f"✏️ 이유를 입력해주세요:\n\n\"{name}\" → {new_side}\n\n(예: 선심성 논란 때문에 오히려 우리유리)"
    _send(base, chat_id, text, edit_msg=msg_id)


def _cb_kw_menu(chat_id, msg_id, base):
    keywords = _custom_kws()
    lines = ["🔍 <b>트래킹 키워드 관리</b>\n"]
    if keywords:
        for i, k in enumerate(keywords, 1):
            lines.append(f"{i}. 🔍 {k['keyword']}")
        lines.append(f"\n총 {len(keywords)}/20개")
    else:
        lines.append("등록된 키워드 없음")

    buttons = [[{"text": "➕ 키워드 추가", "callback_data": "kw_add"}]]
    if keywords:
        # 삭제 버튼들
        for k in keywords[:5]:
            buttons.append([{"text": f"🗑 {k['keyword']}", "callback_data": f"kwdel_{k['keyword']}"}])
    buttons.append([{"text": "◀ 메뉴", "callback_data": "menu"}])
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_kw_delete(cb_data, chat_id, msg_id, base):
    kw = cb_data.replace("kwdel_", "")
    keywords = _custom_kws()
    keywords = [k for k in keywords if k["keyword"] != kw]
    _save(CUSTOM_KEYWORDS_PATH, keywords)
    # 키워드 메뉴로 돌아가기
    _cb_kw_menu(chat_id, msg_id, base)


def _cb_rules(chat_id, msg_id, base, back):
    corr = _corrections()
    rules = corr.get("rules", [])
    recent = corr.get("corrections", [])[-5:]

    lines = ["📌 <b>등록된 규칙</b>\n"]
    if rules:
        for i, r in enumerate(rules, 1):
            lines.append(f"{i}. {r['rule']}")
    else:
        lines.append("(없음)")

    if recent:
        lines.append(f"\n🔧 <b>최근 수정</b>")
        for c in recent:
            lines.append(f"· {c['issue'][:15]} → {c['side']}")

    _send(base, chat_id, "\n".join(lines), back, edit_msg=msg_id)


# ═══════════════════════════════════════
# 텍스트 메시지 핸들러 (대화 상태 기반)
# ═══════════════════════════════════════
def _handle_text(text, chat_id, base):
    """텍스트 메시지 처리 — 대화 상태 + 명령어"""
    state = _user_state.get(chat_id, {})

    # 메모 입력 대기 중
    if state.get("action") == "awaiting_memo":
        category = state.get("category", "memo")
        del _user_state[chat_id]
        today = datetime.now().strftime("%Y-%m-%d")
        cat_labels = {"memo": "메모", "what_worked": "성공", "what_failed": "실패", "correction": "판단수정"}

        # 피드백 저장
        fb_dir = _DATA / "strategy_feedback"
        fb_dir.mkdir(parents=True, exist_ok=True)
        fp = fb_dir / f"{today}.json"
        fb_data = {"date": today, "entries": []}
        if fp.exists():
            try:
                fb_data = json.load(open(fp))
            except Exception:
                pass
        fb_data["entries"].append({
            "category": category,
            "text": text.strip(),
            "source": "telegram",
            "timestamp": datetime.now().isoformat(),
        })
        fb_data["entries"] = fb_data["entries"][-50:]
        with open(fp, "w") as f:
            json.dump(fb_data, f, ensure_ascii=False, indent=2)

        reply = (f"✅ 전략 메모 저장 완료\n\n"
                 f"📂 [{cat_labels.get(category, '메모')}] {text.strip()[:100]}\n"
                 f"📅 {today}\n\n"
                 f"🧠 다음 데일리 리포트 AI 분석에 반영됩니다.")
        buttons = [[{"text": "✏️ 추가 메모", "callback_data": "memo_menu"}, {"text": "◀ 메뉴", "callback_data": "menu"}]]
        _send(base, chat_id, reply, buttons)
        return

    # 이유 입력 대기 중
    if state.get("action") == "awaiting_reason":
        issue = state["issue"]
        side = state["side"]
        reason = text.strip()
        del _user_state[chat_id]

        # correction 저장
        corr = _corrections()
        corr["corrections"].append({
            "issue": issue, "side": side, "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        corr["corrections"] = corr["corrections"][-50:]
        _save(CORRECTIONS_PATH, corr)

        # enrichment에서도 즉시 수정
        try:
            snap = _snap()
            for c in snap.get("news_clusters", []):
                if issue in c.get("name", ""):
                    c["side"] = side
            with open(ENRICHMENT_PATH, "w") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass

        reply = f"✅ 수정 완료\n\n\"{issue}\" → <b>{side}</b>\n이유: {reason}\n\n즉시 반영 + 다음 AI 분석에도 학습됩니다."
        buttons = [[{"text": "📡 TOP 이슈", "callback_data": "issues"}, {"text": "◀ 메뉴", "callback_data": "menu"}]]
        _send(base, chat_id, reply, buttons)
        return

    # 키워드 추가 대기 중
    if state.get("action") == "awaiting_keyword":
        kw = text.strip()
        del _user_state[chat_id]
        if len(kw) < 2:
            _send(base, chat_id, "❌ 키워드가 너무 짧습니다.")
            return
        keywords = _custom_kws()
        if kw in [k["keyword"] for k in keywords]:
            _send(base, chat_id, f"⚠️ 이미 등록: {kw}")
            return
        keywords.append({"keyword": kw, "added_at": datetime.now().isoformat(), "source": "telegram"})
        keywords = keywords[-20:]
        _save(CUSTOM_KEYWORDS_PATH, keywords)
        reply = f"✅ 키워드 추가됨\n🔍 <b>{kw}</b>\n\n다음 반응수집 시 트래킹 시작"
        buttons = [[{"text": "🔍 키워드 관리", "callback_data": "kw_menu"}, {"text": "◀ 메뉴", "callback_data": "menu"}]]
        _send(base, chat_id, reply, buttons)
        return

    # 명령어 처리
    if text.startswith("/start") or text.startswith("/menu"):
        _alert_chats.add(chat_id)  # Alert 수신 등록
        t, b = _main_menu()
        _send(base, chat_id, t, b)
    elif text.startswith("/수정"):
        _handle_text_correct(text, chat_id, base)
    elif text.startswith("/규칙") and not text.startswith("/규칙목록"):
        rule = text.replace("/규칙", "").strip()
        if rule and len(rule) >= 5:
            corr = _corrections()
            corr["rules"].append({"rule": rule, "timestamp": datetime.now().isoformat()})
            corr["rules"] = corr["rules"][-30:]
            _save(CORRECTIONS_PATH, corr)
            _send(base, chat_id, f"✅ 영구 규칙 추가\n📌 {rule}")
        else:
            _send(base, chat_id, "❌ /규칙 규칙내용 (5자 이상)")
    elif text.startswith("/키워드추가"):
        kw = text.replace("/키워드추가", "").strip()
        if kw:
            _user_state[chat_id] = {"action": "awaiting_keyword"}
            _handle_text(kw, chat_id, base)  # 바로 처리
        else:
            _send(base, chat_id, "키워드를 입력해주세요:")
            _user_state[chat_id] = {"action": "awaiting_keyword"}
    else:
        # 알 수 없는 메시지 → 메뉴 표시
        _alert_chats.add(chat_id)
        t, b = _main_menu()
        _send(base, chat_id, t, b)


def _handle_text_correct(text, chat_id, base):
    """텍스트 기반 /수정 명령 호환"""
    parts = text.replace("/수정", "").strip()
    if "→" in parts or "->" in parts:
        sep = "→" if "→" in parts else "->"
        issue_name, rest = parts.split(sep, 1)
        issue_name = issue_name.strip()
        side = rest.split("|")[0].strip() if "|" in rest else rest.strip()
        reason = rest.split("|")[1].strip() if "|" in rest else ""

        corr = _corrections()
        corr["corrections"].append({
            "issue": issue_name, "side": side, "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        corr["corrections"] = corr["corrections"][-50:]
        _save(CORRECTIONS_PATH, corr)
        _send(base, chat_id, f"✅ 수정됨: {issue_name} → {side}")
    else:
        _send(base, chat_id, "형식: /수정 이슈명 → 우리유리 | 이유")


# ═══════════════════════════════════════
# 봇 시작
# ═══════════════════════════════════════
_bot_started = False

def start_telegram_bot():
    """텔레그램 봇 폴링 시작"""
    global _bot_started
    if _bot_started:
        print("[텔레그램] 봇 이미 실행 중", flush=True)
        return
    _bot_started = True

    token = _get_token()
    if not token:
        print("[텔레그램] 봇 토큰 없음", flush=True)
        _bot_started = False
        return

    def _poll():
        base = f"https://api.telegram.org/bot{token}"
        offset = 0
        # pending 건너뛰기
        try:
            resp = httpx.get(f"{base}/getUpdates", params={"offset": -1, "timeout": 0}, timeout=5)
            updates = resp.json().get("result", [])
            if updates:
                offset = updates[-1]["update_id"] + 1
        except Exception:
            pass
        print(f"[텔레그램] 봇 v2 시작", flush=True)

        while True:
            try:
                resp = httpx.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
                data = resp.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # 콜백 쿼리 (버튼 클릭)
                    cb = update.get("callback_query")
                    if cb:
                        chat_id = cb["message"]["chat"]["id"]
                        user_id = cb.get("from", {}).get("id", 0)
                        msg_id = cb["message"]["message_id"]
                        cb_data = cb.get("data", "")

                        # 화이트리스트 체크
                        if not _is_allowed(user_id, chat_id):
                            httpx.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                            continue

                        _alert_chats.add(chat_id)

                        # 키워드 추가 버튼
                        if cb_data == "kw_add":
                            _user_state[chat_id] = {"action": "awaiting_keyword"}
                            _send(base, chat_id, "🔍 추가할 키워드를 입력해주세요:")
                            httpx.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                            continue

                        _handle_callback(cb_data, chat_id, msg_id, base)
                        httpx.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                        continue

                    # 텍스트 메시지
                    msg = update.get("message", {})
                    text = msg.get("text", "").strip()
                    chat_id = msg.get("chat", {}).get("id")
                    user_id = msg.get("from", {}).get("id", 0)
                    if not text or not chat_id:
                        continue

                    # /myid — 자신의 ID 확인 (항상 허용)
                    if text.startswith("/myid"):
                        _send(base, chat_id, f"👤 user_id: <code>{user_id}</code>\n💬 chat_id: <code>{chat_id}</code>")
                        continue

                    # /허용 user_id — 화이트리스트 추가 (현재 허용된 사용자만)
                    if text.startswith("/허용"):
                        wl = _load_whitelist()
                        if wl.get("open", True) or user_id in wl.get("user_ids", []):
                            parts = text.replace("/허용", "").strip().split()
                            for p in parts:
                                try:
                                    new_id = int(p)
                                    if new_id not in wl.get("user_ids", []):
                                        wl.setdefault("user_ids", []).append(new_id)
                                except ValueError:
                                    pass
                            _save_whitelist(wl)
                            _send(base, chat_id, f"✅ 화이트리스트 업데이트\n허용 user_ids: {wl.get('user_ids', [])}")
                        continue

                    # /허용그룹 — 현재 그룹을 화이트리스트에 추가
                    if text.startswith("/허용그룹"):
                        wl = _load_whitelist()
                        if wl.get("open", True) or user_id in wl.get("user_ids", []):
                            if chat_id not in wl.get("chat_ids", []):
                                wl.setdefault("chat_ids", []).append(chat_id)
                            _save_whitelist(wl)
                            _send(base, chat_id, f"✅ 이 그룹이 화이트리스트에 추가됨\nchat_id: {chat_id}")
                        continue

                    # /잠금 — open 모드 종료, 화이트리스트 모드 활성화
                    if text.startswith("/잠금"):
                        wl = _load_whitelist()
                        if wl.get("open", True) or user_id in wl.get("user_ids", []):
                            # 현재 user를 자동 등록
                            if user_id not in wl.get("user_ids", []):
                                wl.setdefault("user_ids", []).append(user_id)
                            if chat_id not in wl.get("chat_ids", []):
                                wl.setdefault("chat_ids", []).append(chat_id)
                            wl["open"] = False
                            _save_whitelist(wl)
                            _send(base, chat_id, f"🔒 화이트리스트 모드 활성화\n허용된 user만 봇 사용 가능\n\nuser_ids: {wl['user_ids']}\nchat_ids: {wl['chat_ids']}")
                        continue

                    # 화이트리스트 체크
                    if not _is_allowed(user_id, chat_id):
                        continue  # 무응답

                    _handle_text(text, chat_id, base)

            except Exception as e:
                print(f"[텔레그램] 폴링 에러: {e}", flush=True)
                time.sleep(10)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()

    # 자동 헬스체크 — 60분 이상 갱신 없으면 알림
    def _health_monitor():
        while True:
            time.sleep(3600)  # 60분마다 체크
            try:
                snap = _snap()
                ts = snap.get("timestamp", "")
                if not ts:
                    continue
                from datetime import datetime
                last = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                diff = (datetime.now() - last).total_seconds()
                if diff > 3600:  # 60분 이상
                    mins = int(diff / 60)
                    send_alert(f"⚠️ <b>시스템 경고</b>\n\n스케줄러 {mins}분째 갱신 없음.\n마지막: {ts[:16]}\n\n/상태 로 확인하세요.")
            except Exception:
                pass

    threading.Thread(target=_health_monitor, daemon=True).start()


# ═══════════════════════════════════════
# 시스템 운영 명령어
# ═══════════════════════════════════════

def _cb_sys_status(snap, chat_id, msg_id, base, back):
    """시스템 상태 진단"""
    from datetime import datetime

    ts = snap.get("timestamp", "")
    clusters = snap.get("news_clusters", [])
    cr = snap.get("cluster_reaction", {})
    corr = snap.get("turnout", {}).get("correction", {})

    # 마지막 갱신 시간 차이
    status_emoji = "🟢"
    diff_min = 0
    if ts:
        try:
            last = datetime.fromisoformat(ts)
            diff_min = int((datetime.now() - last).total_seconds() / 60)
            if diff_min > 60:
                status_emoji = "🔴"
            elif diff_min > 30:
                status_emoji = "🟡"
        except Exception:
            pass

    # 클러스터 품질 체크
    cluster_names = [c.get("name", "") for c in clusters[:5]]
    bad_names = [n for n in cluster_names if n in ("선거/공천", "기타", "산업/경제", "도정/예산", "KF-21/방산", "청년/복지", "정당/정치")]
    cluster_quality = "❌ 카테고리 분류됨" if bad_names else f"✅ 사건 클러스터 {len(clusters)}개"

    # 반응 데이터
    reaction_details = len(cr.get("details", []))
    reaction_mentions = cr.get("total_mentions", 0)

    lines = [
        f"{status_emoji} <b>시스템 상태</b>\n",
        f"마지막 갱신: {_to_kst(ts) if ts else '없음'}",
        f"갱신 경과: {diff_min}분 전",
        f"",
        f"<b>데이터 상태:</b>",
        f"  클러스터: {cluster_quality}",
        f"  반응 수집: {reaction_details}개 키워드 / {reaction_mentions}건",
        f"  판세지수: {corr.get('pandse_index', '?')}pt (D-{corr.get('d_day', '?')})",
        f"",
        f"<b>클러스터 TOP 5:</b>",
    ]
    for i, c in enumerate(clusters[:5], 1):
        lines.append(f"  {i}. {c.get('name','')} ({c.get('count',0)}건)")

    if bad_names:
        lines.append(f"\n⚠️ 카테고리 분류 감지: {', '.join(bad_names)}")
        lines.append("→ /수집 으로 재수집 필요")

    buttons = [
        [{"text": "🔄 수동 수집", "callback_data": "sys_collect"}, {"text": "📋 최근 로그", "callback_data": "sys_log"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_sys_admin(chat_id, msg_id, base, back):
    """시스템 관리 메뉴"""
    lines = [
        "🔧 <b>시스템 관리</b>\n",
        "수동 수집: 즉시 데이터 수집 실행",
        "스케줄러 재시작: 스레드 재시작",
        "재배포: Render 서버 재배포",
        "백업: 전체 학습데이터 다운로드",
    ]
    buttons = [
        [{"text": "🔄 수동 수집", "callback_data": "sys_collect"}, {"text": "♻️ 스케줄러 재시작", "callback_data": "sys_restart"}],
        [{"text": "🚀 재배포", "callback_data": "sys_deploy"}, {"text": "💾 백업 다운로드", "url": f"{DASHBOARD_URL}/api/admin/backup"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


def _cb_sys_collect(chat_id, msg_id, base, back):
    """수동 데이터 수집 트리거"""
    try:
        import threading as _th
        from scheduler import _update_all
        _th.Thread(target=_update_all, daemon=True).start()
        _send(base, chat_id, "🔄 수동 수집 시작됨.\n10분 후 /상태 에서 확인하세요.", back, edit_msg=msg_id)
    except Exception as e:
        _send(base, chat_id, f"❌ 수집 실행 실패: {e}", back, edit_msg=msg_id)


def _cb_sys_restart(chat_id, msg_id, base, back):
    """스케줄러 스레드 재시작"""
    try:
        from scheduler import start_scheduler
        start_scheduler()
        _send(base, chat_id, "♻️ 스케줄러 재시작 요청됨.\n새 스레드가 시작됩니다.", back, edit_msg=msg_id)
    except Exception as e:
        _send(base, chat_id, f"❌ 재시작 실패: {e}", back, edit_msg=msg_id)


def _cb_sys_deploy(chat_id, msg_id, base, back):
    """Render 재배포 트리거"""
    try:
        deploy_hook = os.environ.get("RENDER_DEPLOY_HOOK", "")
        if not deploy_hook:
            _send(base, chat_id, "❌ RENDER_DEPLOY_HOOK 환경변수가 설정되지 않았습니다.", back, edit_msg=msg_id)
            return
        resp = httpx.post(deploy_hook, timeout=10)
        if resp.status_code == 200:
            _send(base, chat_id, "🚀 Render 재배포 트리거 완료.\n빌드+배포까지 3~5분 소요.", back, edit_msg=msg_id)
        else:
            _send(base, chat_id, f"❌ 배포 트리거 실패: HTTP {resp.status_code}", back, edit_msg=msg_id)
    except Exception as e:
        _send(base, chat_id, f"❌ 배포 실패: {e}", back, edit_msg=msg_id)


def _cb_sys_log(chat_id, msg_id, base, back):
    """최근 에러 로그"""
    try:
        snap = _snap()
        ts = _to_kst(snap.get("timestamp", ""))
        clusters = snap.get("news_clusters", [])
        cr = snap.get("cluster_reaction", {})

        # 클러스터 품질 진단
        issues = []
        cluster_names = [c.get("name", "") for c in clusters]
        bad = [n for n in cluster_names if "/" in n or n in ("기타",)]
        if bad:
            issues.append(f"⚠️ 카테고리 분류 감지: {', '.join(bad[:3])}")
        if not clusters:
            issues.append("❌ 클러스터 데이터 없음")

        # 반응 데이터
        details = cr.get("details", [])
        empty_opinions = sum(1 for d in details if not d.get("sources", {}).get("community", {}).get("ai_opinions"))
        if empty_opinions > 5:
            issues.append(f"⚠️ AI 시민의견 없는 키워드: {empty_opinions}개")

        # summary/why 누락
        no_summary = sum(1 for c in clusters if not c.get("summary"))
        if no_summary > 3:
            issues.append(f"⚠️ summary 누락: {no_summary}/{len(clusters)}개")

        if not issues:
            issues.append("✅ 특이사항 없음")

        lines = [
            "📋 <b>시스템 진단 로그</b>\n",
            f"마지막 갱신: {ts}",
            f"클러스터: {len(clusters)}개",
            f"반응 키워드: {len(details)}개",
            "",
            "<b>진단 결과:</b>",
        ] + issues

        _send(base, chat_id, "\n".join(lines), back, edit_msg=msg_id)
    except Exception as e:
        _send(base, chat_id, f"❌ 로그 조회 실패: {e}", back, edit_msg=msg_id)
