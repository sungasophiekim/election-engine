"""텔레그램 봇 — 이슈 side 수정 + 규칙 관리 + 최근이슈 조회"""
import os
import json
import threading
import time
import httpx
from pathlib import Path
from datetime import datetime

CORRECTIONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "side_corrections.json"
ENRICHMENT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "enrichment_snapshot.json"
CUSTOM_KEYWORDS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "custom_keywords.json"


def _load_custom_keywords() -> list:
    try:
        with open(CUSTOM_KEYWORDS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _save_custom_keywords(keywords: list):
    CUSTOM_KEYWORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CUSTOM_KEYWORDS_PATH, "w") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)


def _load_corrections() -> dict:
    try:
        with open(CORRECTIONS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"corrections": [], "rules": []}


def _save_corrections(data: dict):
    CORRECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CORRECTIONS_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_enrichment() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            for line in open(env_path):
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1]
    return token


_bot_started = False

def start_telegram_bot():
    """텔레그램 봇 폴링 시작 (백그라운드 스레드) — 중복 실행 방지"""
    global _bot_started
    if _bot_started:
        print("[텔레그램] 봇 이미 실행 중 — 중복 시작 방지", flush=True)
        return
    _bot_started = True

    token = _get_token()
    if not token:
        print("[텔레그램] 봇 토큰 없음 — 봇 비활성", flush=True)
        _bot_started = False
        return

    def _poll():
        base = f"https://api.telegram.org/bot{token}"
        offset = 0
        # 시작 시 pending updates 건너뛰기 (중복 응답 방지)
        try:
            resp = httpx.get(f"{base}/getUpdates", params={"offset": -1, "timeout": 0}, timeout=5)
            data = resp.json()
            updates = data.get("result", [])
            if updates:
                offset = updates[-1]["update_id"] + 1
                print(f"[텔레그램] {len(updates)}건 pending 건너뜀 (offset={offset})", flush=True)
        except Exception:
            pass
        print(f"[텔레그램] 봇 시작 (offset={offset})", flush=True)

        while True:
            try:
                resp = httpx.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
                data = resp.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    text = msg.get("text", "").strip()
                    chat_id = msg.get("chat", {}).get("id")
                    if not text or not chat_id:
                        continue

                    reply = _handle_command(text)
                    if reply:
                        httpx.post(f"{base}/sendMessage", json={
                            "chat_id": chat_id,
                            "text": reply,
                            "parse_mode": "HTML",
                        }, timeout=10)

            except Exception as e:
                print(f"[텔레그램] 폴링 에러: {e}", flush=True)
                time.sleep(10)

    t = threading.Thread(target=_poll, daemon=True)
    t.start()


def _handle_command(text: str) -> str:
    """명령어 처리"""
    if text.startswith("/수정") or text.startswith("/correct"):
        return _cmd_correct(text)
    elif text.startswith("/규칙") and not text.startswith("/규칙목록"):
        return _cmd_add_rule(text)
    elif text.startswith("/규칙목록") or text.startswith("/rules"):
        return _cmd_list_rules()
    elif text.startswith("/키워드추가") or text.startswith("/addkw"):
        return _cmd_add_keyword(text)
    elif text.startswith("/키워드삭제") or text.startswith("/delkw"):
        return _cmd_del_keyword(text)
    elif text.startswith("/키워드목록") or text.startswith("/keywords"):
        return _cmd_list_keywords()
    elif text.startswith("/최근이슈") or text.startswith("/issues"):
        return _cmd_recent_issues()
    elif text.startswith("/지수") or text.startswith("/index"):
        return _cmd_indices()
    elif text.startswith("/help") or text.startswith("/도움"):
        return _cmd_help()
    elif text.startswith("/start"):
        return _cmd_help()
    return None


def _cmd_correct(text: str) -> str:
    """/수정 이슈명 → 우리유리|상대유리 | 이유"""
    try:
        # 파싱: /수정 이슈명 → side | reason
        parts = text.replace("/수정", "").replace("/correct", "").strip()
        if "→" in parts:
            issue_name, rest = parts.split("→", 1)
        elif "->" in parts:
            issue_name, rest = parts.split("->", 1)
        else:
            return "❌ 형식: /수정 이슈명 → 우리유리 | 이유"

        issue_name = issue_name.strip()
        if "|" in rest:
            side, reason = rest.split("|", 1)
        else:
            side = rest
            reason = ""

        side = side.strip()
        reason = reason.strip()

        if side not in ["우리유리", "우리 유리", "상대유리", "상대 유리", "중립", "양면"]:
            return f"❌ side는 '우리유리', '상대유리', '중립', '양면' 중 하나\n입력: {side}"

        # 저장
        corrections = _load_corrections()
        corrections["corrections"].append({
            "issue": issue_name,
            "side": side,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        # 최근 50건 유지
        corrections["corrections"] = corrections["corrections"][-50:]
        _save_corrections(corrections)

        return f"✅ 수정 반영됨\n이슈: {issue_name}\n→ {side}\n이유: {reason or '없음'}\n\n다음 AI 분석 시 반영됩니다."

    except Exception as e:
        return f"❌ 파싱 에러: {e}\n형식: /수정 이슈명 → 우리유리 | 이유"


def _cmd_add_rule(text: str) -> str:
    """/규칙 영구 규칙 추가"""
    rule = text.replace("/규칙", "").strip()
    if not rule or len(rule) < 5:
        return "❌ 형식: /규칙 경남 수출 실적은 항상 상대유리 (현직 도정 성과)"

    corrections = _load_corrections()
    corrections["rules"].append({
        "rule": rule,
        "timestamp": datetime.now().isoformat(),
    })
    corrections["rules"] = corrections["rules"][-30:]  # 최근 30개
    _save_corrections(corrections)

    return f"✅ 영구 규칙 추가됨\n📌 {rule}\n\n모든 향후 AI 분석에 적용됩니다."


def _cmd_list_rules() -> str:
    """/규칙목록"""
    corrections = _load_corrections()
    rules = corrections.get("rules", [])
    recent = corrections.get("corrections", [])[-10:]

    lines = ["📌 <b>등록된 규칙</b>"]
    if rules:
        for i, r in enumerate(rules, 1):
            lines.append(f"{i}. {r['rule']}")
    else:
        lines.append("(없음)")

    lines.append(f"\n🔧 <b>최근 수정 {len(recent)}건</b>")
    for c in recent[-5:]:
        lines.append(f"· {c['issue']} → {c['side']}")

    return "\n".join(lines)


def _cmd_add_keyword(text: str) -> str:
    """/키워드추가 키워드"""
    kw = text.replace("/키워드추가", "").replace("/addkw", "").strip()
    if not kw or len(kw) < 2:
        return "❌ 형식: /키워드추가 김경수 메가시티"

    keywords = _load_custom_keywords()
    # 중복 체크
    existing = [k["keyword"] for k in keywords]
    if kw in existing:
        return f"⚠️ 이미 등록된 키워드: {kw}"

    keywords.append({
        "keyword": kw,
        "added_at": datetime.now().isoformat(),
        "source": "telegram",
    })
    keywords = keywords[-20:]  # 최대 20개
    _save_custom_keywords(keywords)

    return f"✅ 키워드 추가됨\n🔍 {kw}\n\n다음 반응수집 시 트래킹 시작됩니다.\n현재 등록: {len(keywords)}개"


def _cmd_del_keyword(text: str) -> str:
    """/키워드삭제 키워드"""
    kw = text.replace("/키워드삭제", "").replace("/delkw", "").strip()
    if not kw:
        return "❌ 형식: /키워드삭제 김경수 메가시티"

    keywords = _load_custom_keywords()
    before = len(keywords)
    keywords = [k for k in keywords if k["keyword"] != kw]
    _save_custom_keywords(keywords)

    if len(keywords) < before:
        return f"✅ 키워드 삭제됨: {kw}\n현재 등록: {len(keywords)}개"
    return f"⚠️ 해당 키워드 없음: {kw}"


def _cmd_list_keywords() -> str:
    """/키워드목록"""
    keywords = _load_custom_keywords()
    if not keywords:
        return "📋 등록된 커스텀 키워드 없음\n\n/키워드추가 키워드명 으로 추가"

    lines = ["📋 <b>커스텀 트래킹 키워드</b>"]
    for i, k in enumerate(keywords, 1):
        added = k.get("added_at", "")[:10]
        lines.append(f"{i}. 🔍 {k['keyword']} ({added})")
    lines.append(f"\n총 {len(keywords)}개 · 반응수집 시 자동 트래킹")
    return "\n".join(lines)


def _cmd_recent_issues() -> str:
    """/최근이슈 — 현재 TOP 10 클러스터 + 뉴스 링크"""
    snap = _load_enrichment()
    clusters = snap.get("news_clusters", [])
    if not clusters:
        return "❌ 클러스터 데이터 없음"

    lines = ["📊 <b>현재 TOP 이슈</b>\n"]
    for i, c in enumerate(clusters[:10], 1):
        side = c.get("side", "?")
        emoji = "🔵" if "우리" in side else "🔴" if "상대" in side else "⚪"
        lines.append(f"{emoji} <b>{i}. {c.get('name','')}</b> | {c.get('count',0)}건 | {side}")
        # 기사 링크 표시 (최대 2개)
        articles = c.get("articles", [])
        for art in articles[:2]:
            title = art.get("title", "")
            url = art.get("url", "")
            if url and title:
                lines.append(f"   📎 <a href=\"{url}\">{title[:40]}{'…' if len(title) > 40 else ''}</a>")
            elif title:
                lines.append(f"   • {title[:50]}")
        lines.append("")  # 빈 줄 구분

    ts = snap.get("timestamp", "")[:16].replace("T", " ")
    lines.append(f"갱신: {ts}")
    lines.append("수정: /수정 이슈명 → 우리유리 | 이유")

    return "\n".join(lines)


def _cmd_indices() -> str:
    """/지수 — 현재 3개 지수"""
    snap = _load_enrichment()
    ci = snap.get("cluster_issue", {})
    cr = snap.get("cluster_reaction", {})
    corr = snap.get("turnout", {}).get("correction", {})

    issue = ci.get("issue_index", 50)
    reaction = cr.get("reaction_index", 50)
    pandse = corr.get("pandse_index", 50)

    def grade(v):
        return "우세" if v > 55 else "열세" if v < 45 else "접전"

    return f"""📊 <b>현재 지수</b>
이슈: {issue:.1f}pt ({grade(issue)})
반응: {reaction:.1f}pt ({grade(reaction)})
판세: {pandse:.1f}pt ({grade(pandse)})
D-{corr.get('d_day', '?')}

갱신: {snap.get('timestamp', '')[:16].replace('T', ' ')}"""


def _cmd_help() -> str:
    return """🤖 <b>김경수 캠프 AI 어시스턴트</b>

<b>모니터링</b>
/최근이슈 — TOP 10 이슈 확인
/지수 — 3개 지수 현황

<b>이슈 판정 수정</b>
/수정 이슈명 → 우리유리 | 이유
/규칙 규칙내용 — 영구 규칙 추가
/규칙목록 — 등록된 규칙 확인

<b>키워드 트래킹</b>
/키워드추가 키워드명 — 반응 추적 시작
/키워드삭제 키워드명
/키워드목록 — 등록된 키워드 확인

<b>예시</b>
/수정 경남 수출 → 상대유리 | 현직 성과
/키워드추가 김경수 메가시티
/규칙 경남 SOC 준공은 항상 상대유리"""
