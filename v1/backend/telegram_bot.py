"""텔레그램 봇 v2 — 버튼형 UI + Alert 시스템 + AI 학습 피드백"""
import os
import json
import threading
import time
import httpx
from pathlib import Path
from datetime import datetime

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
CORRECTIONS_PATH = _DATA / "side_corrections.json"
ENRICHMENT_PATH = _DATA / "enrichment_snapshot.json"
CUSTOM_KEYWORDS_PATH = _DATA / "custom_keywords.json"
HISTORY_PATH = _DATA / "indices_history.json"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://election-engine.onrender.com")

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
    ts = snap.get("timestamp", "")[:16].replace("T", " ")

    text = f"""🏛 <b>김경수 캠프 AI 전략 어시스턴트</b>

이슈 <b>{issue:.1f}pt</b> {g(issue)} | 반응 <b>{reaction:.1f}pt</b> {g(reaction)} | 판세 <b>{pandse:.1f}pt</b> {g(pandse)}

D-{d_day} · 갱신 {ts}"""

    buttons = [
        [{"text": "📊 대시보드", "callback_data": "dashboard"}, {"text": "📡 TOP 이슈", "callback_data": "issues"}],
        [{"text": "🧠 민심 레이더", "callback_data": "radar"}, {"text": "📈 지수 현황", "callback_data": "indices"}],
        [{"text": "🔧 이슈 수정", "callback_data": "fix_menu"}, {"text": "🔍 키워드 관리", "callback_data": "kw_menu"}],
        [{"text": "📋 데일리 요약", "callback_data": "daily"}, {"text": "📌 규칙 목록", "callback_data": "rules"}],
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
    clusters = snap.get("news_clusters", [])
    lines = ["📡 <b>TOP 이슈</b>\n"]
    for i, c in enumerate(clusters[:8], 1):
        side = c.get("side", "?")
        emoji = "🔵" if "우리" in side else "🔴" if "상대" in side else "⚪"
        lines.append(f"{emoji} <b>{i}. {c.get('name','')}</b>")
        lines.append(f"   {c.get('count',0)}건 | {side} | 감성{c.get('sentiment',0):+d}")
        if c.get("tip"):
            lines.append(f"   💡 {c['tip'][:50]}")
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
    cr = snap.get("cluster_reaction", {})
    details = cr.get("details", [])
    lines = ["🧠 <b>민심 반응 레이더</b>\n"]

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

갱신: {snap.get('timestamp', '')[:16].replace('T', ' ')}"""

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

    summary = rpt.get("executive_summary", "요약 없음")[:400]
    theme = rpt.get("daily_theme", {})
    urgent = [e for e in rpt.get("execution", []) if "즉시" in e.get("when", "") or "오늘" in e.get("when", "")]
    schedule = rpt.get("field_schedule", rpt.get("messages", []))

    lines = [f"📋 <b>데일리 전략 요약</b> ({rpt.get('date', '')})\n"]
    if theme:
        lines.append(f"🏷 테마: <b>{theme.get('keyword', '')}</b>\n")
    lines.append(summary)

    if urgent:
        lines.append("\n⚡ <b>긴급 액션</b>")
        for i, e in enumerate(urgent[:3], 1):
            lines.append(f"{'①②③'[i-1]} {e.get('what','')}")

    if schedule:
        lines.append("\n📍 <b>현장 일정</b>")
        for s in schedule[:2]:
            region = s.get("region", "")
            msg = s.get("message", "")
            lines.append(f"• {region}: \"{msg}\"")

    buttons = [
        [{"text": "🔗 전체 리포트", "url": f"{DASHBOARD_URL}"}],
        back[0],
    ]
    _send(base, chat_id, "\n".join(lines), buttons, edit_msg=msg_id)


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
                        msg_id = cb["message"]["message_id"]
                        cb_data = cb.get("data", "")
                        _alert_chats.add(chat_id)

                        # 키워드 추가 버튼
                        if cb_data == "kw_add":
                            _user_state[chat_id] = {"action": "awaiting_keyword"}
                            _send(base, chat_id, "🔍 추가할 키워드를 입력해주세요:")
                            # answer callback
                            httpx.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                            continue

                        _handle_callback(cb_data, chat_id, msg_id, base)
                        httpx.post(f"{base}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                        continue

                    # 텍스트 메시지
                    msg = update.get("message", {})
                    text = msg.get("text", "").strip()
                    chat_id = msg.get("chat", {}).get("id")
                    if text and chat_id:
                        _handle_text(text, chat_id, base)

            except Exception as e:
                print(f"[텔레그램] 폴링 에러: {e}", flush=True)
                time.sleep(10)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()
