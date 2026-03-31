"""전략 실행 레이어 API — AI 기반 데일리/위클리 전략 브리핑"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional
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


def _load_report_meta() -> dict:
    """report_meta.json 로드 — last_daily_generated_at 등 저장"""
    meta_path = LEGACY_DATA / "report_meta.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_report_meta(meta: dict):
    """report_meta.json 저장"""
    meta_path = LEGACY_DATA / "report_meta.json"
    LEGACY_DATA.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _load_polls() -> list:
    try:
        with open(LEGACY_DATA / "polls.json") as f:
            return json.load(f).get("polls", [])
    except Exception:
        return []


def _filter_history_since(history: list, since_iso: Optional[str]) -> list:
    """since_iso 이후의 history entries만 반환. None이면 전체 반환."""
    if not since_iso or not history:
        return history
    filtered = [h for h in history if h.get("date", "") > since_iso]
    # 필터 후 빈 결과 → 최근 24건 폴백
    if not filtered:
        return history[-24:]
    return filtered


def _accumulate_top_clusters(filtered_history: list, current_clusters: list, limit: int = 5) -> list:
    """24시간 history의 top_clusters를 누적하여 TOP N 반환 — 상세 정보 포함."""
    from collections import Counter, defaultdict
    cluster_scores: Counter = Counter()
    cluster_sides: dict = {}
    cluster_hours: Counter = Counter()  # 몇 시간 동안 등장했는지
    cluster_details: dict = {}  # 가장 최신 상세 정보 보관

    # history에서 누적
    for entry in filtered_history:
        for c in entry.get("top_clusters", []):
            name = c.get("name", "")
            if not name:
                continue
            cluster_scores[name] += c.get("count", 1)
            cluster_hours[name] += 1
            cluster_sides[name] = c.get("side", cluster_sides.get(name, "중립"))
            # 상세 정보는 최신 것으로 덮어쓰기 (summary/why/tip이 있는 경우만)
            if c.get("summary") or c.get("why"):
                cluster_details[name] = {
                    "summary": c.get("summary", ""), "why": c.get("why", ""),
                    "tip": c.get("tip", ""), "community_expected": c.get("community_expected", ""),
                    "sentiment": c.get("sentiment", 0),
                }

    # 현재 클러스터도 반영 (가중치 2배 — 최신 데이터 우선)
    for c in current_clusters:
        name = c.get("name", "")
        if not name:
            continue
        cluster_scores[name] += c.get("count", 1) * 2
        cluster_hours[name] += 1
        cluster_sides[name] = c.get("side", "중립")
        cluster_details[name] = {
            "summary": c.get("summary", ""), "why": c.get("why", ""),
            "tip": c.get("tip", ""), "community_expected": c.get("community_expected", ""),
            "sentiment": c.get("sentiment", 0),
        }

    # TOP N 추출
    top = cluster_scores.most_common(limit)
    result = []
    for name, score in top:
        detail = cluster_details.get(name, {})
        result.append({
            "name": name,
            "side": cluster_sides.get(name, "중립"),
            "accumulated_score": score,
            "hours_appeared": cluster_hours.get(name, 0),
            "summary": detail.get("summary", ""),
            "why": detail.get("why", ""),
            "tip": detail.get("tip", ""),
            "community_expected": detail.get("community_expected", ""),
            "sentiment": detail.get("sentiment", 0),
        })
    return result


def _accumulate_top_reactions(filtered_history: list, limit: int = 5) -> list:
    """24시간 history의 반응 데이터를 누적하여 TOP N 반환."""
    from collections import Counter, defaultdict
    reaction_mentions: Counter = Counter()
    reaction_sentiments: defaultdict = defaultdict(list)
    reaction_sides: dict = {}
    reaction_sources: defaultdict = defaultdict(set)

    for entry in filtered_history:
        for rx in entry.get("top_reactions", []):
            kw = rx.get("keyword", "")
            if not kw:
                continue
            reaction_sides[kw] = rx.get("side", reaction_sides.get(kw, "중립"))
            for sname, sdata in rx.get("sources", {}).items():
                cnt = sdata.get("count", 0)
                sent = sdata.get("net_sentiment", 0)
                reaction_mentions[kw] += cnt
                if sent != 0:
                    reaction_sentiments[kw].append(sent)
                reaction_sources[kw].add(sname)

    top = reaction_mentions.most_common(limit)
    result = []
    for kw, total_mentions in top:
        sents = reaction_sentiments.get(kw, [])
        avg_sent = sum(sents) / len(sents) if sents else 0
        result.append({
            "keyword": kw,
            "side": reaction_sides.get(kw, "중립"),
            "total_mentions": total_mentions,
            "avg_sentiment": round(avg_sent, 3),
            "tone": "긍정" if avg_sent > 0.05 else "부정" if avg_sent < -0.05 else "중립",
            "sources": list(reaction_sources.get(kw, [])),
        })
    return result


def _load_history() -> list:
    try:
        with open(LEGACY_DATA / "indices_history.json") as f:
            return json.load(f)
    except Exception:
        return []


def _build_chart_data(history_entries: list) -> dict:
    """history entries에서 프론트엔드 차트용 데이터 생성."""
    if not history_entries:
        return {"timestamps": [], "issue_index": [], "reaction_index": [], "pandse": [], "summary": {}}
    timestamps = [h.get("date", "") for h in history_entries]
    issue_vals = [float(h.get("issue_index", 50)) for h in history_entries]
    reaction_vals = [float(h.get("reaction_index", 50)) for h in history_entries]
    pandse_vals = [float(h.get("pandse", 50)) for h in history_entries]

    def _summary(vals):
        if not vals:
            return {"min": 0, "max": 0, "current": 0, "range": 0}
        return {
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
            "current": round(vals[-1], 1),
            "range": round(max(vals) - min(vals), 1),
        }

    return {
        "timestamps": timestamps,
        "issue_index": issue_vals,
        "reaction_index": reaction_vals,
        "pandse": pandse_vals,
        "summary": {
            "issue": _summary(issue_vals),
            "reaction": _summary(reaction_vals),
            "pandse": _summary(pandse_vals),
        },
    }


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


def _build_daily_context(snap: dict, since_timestamp: Optional[str] = None) -> str:
    clusters = snap.get("news_clusters", [])
    buzz = snap.get("candidate_buzz", {})
    corr = snap.get("turnout", {}).get("correction", {})
    pandse = corr.get("pandse_index", 50)
    d_day = corr.get("d_day", "?")
    factors = corr.get("factors", [])
    polls = _load_polls()
    latest_poll = polls[-1] if polls else {}

    full_history = _load_history()
    # since_timestamp 기반 필터링
    filtered_history = _filter_history_since(full_history, since_timestamp)
    history = filtered_history[-7:]
    history_24h = filtered_history[-24:] if len(filtered_history) >= 2 else full_history[-24:]

    # 24시간 누적 TOP 5 이슈 + 반응 (리포트 핵심 데이터)
    accumulated_clusters = _accumulate_top_clusters(history_24h, clusters, limit=5)
    accumulated_reactions = _accumulate_top_reactions(history_24h, limit=5)

    # 24시간 지수 흐름 분석
    h24_analysis = ""
    if len(history_24h) >= 2:
        issue_vals = [h.get("issue_index", 50) for h in history_24h]
        reaction_vals = [h.get("reaction_index", 50) for h in history_24h]
        pandse_vals = [h.get("pandse", 50) for h in history_24h]

        issue_min, issue_max = min(issue_vals), max(issue_vals)
        reaction_min, reaction_max = min(reaction_vals), max(reaction_vals)
        pandse_min, pandse_max = min(pandse_vals), max(pandse_vals)

        # 최고/최저 시점의 이슈 클러스터
        issue_max_idx = issue_vals.index(issue_max)
        issue_min_idx = issue_vals.index(issue_min)
        max_entry = history_24h[issue_max_idx]
        min_entry = history_24h[issue_min_idx]

        max_clusters = max_entry.get("top_clusters", [])
        min_clusters = min_entry.get("top_clusters", [])
        max_cluster_text = ", ".join(f"{c['name']}({c['side']})" for c in max_clusters[:3]) if max_clusters else "없음"
        min_cluster_text = ", ".join(f"{c['name']}({c['side']})" for c in min_clusters[:3]) if min_clusters else "없음"

        h24_analysis = f"""### 24시간 지수 흐름 ({history_24h[0].get('date','')} ~ {history_24h[-1].get('date','')}, {len(history_24h)}건)
- 이슈지수: {issue_min:.1f}pt ~ {issue_max:.1f}pt (현재 {issue_vals[-1]:.1f}pt)
  - 최고 시점({max_entry.get('date','')}, {issue_max:.1f}pt): {max_cluster_text}
  - 최저 시점({min_entry.get('date','')}, {issue_min:.1f}pt): {min_cluster_text}
- 반응지수: {reaction_min:.1f}pt ~ {reaction_max:.1f}pt (현재 {reaction_vals[-1]:.1f}pt)
- 판세지수: {pandse_min:.1f}pt ~ {pandse_max:.1f}pt (현재 {pandse_vals[-1]:.1f}pt)

시간별 상세:
""" + "\n".join(
            f"  {h.get('date','')}: 이슈{h.get('issue_index',50):.1f} 반응{h.get('reaction_index',50):.1f} 판세{h.get('pandse',50):.1f}" +
            (f" | TOP: {', '.join(c['name'] for c in h.get('top_clusters',[])[:2])}" if h.get('top_clusters') else "")
            for h in history_24h
        )

    kim_m = sum(v.get("mention_count", 0) for k, v in buzz.items() if "김경수" in k)
    park_m = sum(v.get("mention_count", 0) for k, v in buzz.items() if "박완수" in k)
    kim_sents = [v.get("ai_sentiment", {}) for k, v in buzz.items() if "김경수" in k]
    park_sents = [v.get("ai_sentiment", {}) for k, v in buzz.items() if "박완수" in k]

    cluster_text = "\n".join(
        f"{i+1}. {c.get('name','')} | {c.get('side','중립')} | {c.get('count',0)}건 | 감성{c.get('sentiment',0):+d} | 시민반응: {c.get('community_expected','?')} | tip: {c.get('tip','')}"
        for i, c in enumerate(clusters[:10])
    ) or "없음"

    # 24시간 누적 TOP 5 이슈 (상세 포함)
    accumulated_text = "\n".join(
        f"{i+1}. {c.get('name','')} | {c.get('side','중립')} | 누적점수 {c.get('accumulated_score',0)} | {c.get('hours_appeared',0)}시간 지속 | 감성{c.get('sentiment',0):+d}\n"
        f"   요약: {c.get('summary','없음')}\n"
        f"   이유: {c.get('why','없음')}\n"
        f"   시민반응: {c.get('community_expected','?')} | tip: {c.get('tip','없음')}"
        for i, c in enumerate(accumulated_clusters)
    ) or "없음"

    # 24시간 누적 TOP 5 반응 (민심 감성 누적)
    accumulated_reaction_text = "\n".join(
        f"{i+1}. [{rx.get('side','?')}] {rx.get('keyword','')} | 총 {rx.get('total_mentions',0)}건 | 감성 {rx.get('avg_sentiment',0):+.3f} ({rx.get('tone','중립')}) | 소스: {', '.join(rx.get('sources',[]))}"
        for i, rx in enumerate(accumulated_reactions)
    ) or "없음"

    # 이슈지수 (가중지수)
    ci = snap.get("cluster_issue", {})
    issue_index = ci.get("issue_index", 50)
    issue_text = f"이슈지수: {issue_index:.1f}pt (50=중립, >50 우리유리) | 우리 {ci.get('kim_count',0)}건(가중{ci.get('kim_score',0)}) vs 상대 {ci.get('park_count',0)}건(가중{ci.get('park_score',0)})"

    # 반응지수 (실데이터 기반)
    cr = snap.get("cluster_reaction", {})
    reaction_text = f"반응지수: 김경수 {cr.get('kim_sentiment',0):+d} / 박완수 {cr.get('park_sentiment',0):+d}"
    if cr.get("total_mentions"):
        reaction_text += f" | {cr['total_mentions']}건 수집 ({', '.join(cr.get('sources_collected',[]))})"
    # 반응 상세 (키워드별)
    rx_details = cr.get("details", [])
    reaction_detail = ""
    for rx in rx_details[:10]:
        srcs = rx.get("sources", {})
        src_sents = []
        for sname, sdata in srcs.items():
            s = sdata.get("net_sentiment", 0)
            cnt = sdata.get("count", 0) or sdata.get("comments", 0) or sdata.get("mentions", 0)
            if cnt > 0 or s != 0:
                src_sents.append(f"{sname}={s:+.2f}({cnt}건)")
        if src_sents:
            reaction_detail += f"  - [{rx.get('side','?')}] {rx.get('keyword','')}: {' | '.join(src_sents)}\n"

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

### {issue_text}

### {reaction_text}

### 반응지수 상세 (이슈별 소스 감성)
{reaction_detail or "없음"}

### 뉴스 노출 (24시간)
- 김경수: {kim_m}건 | 박완수: {park_m}건

### 후보별 버즈 상세 (AI 감성분석)
{buzz_detail}

### 현재 시점 뉴스 클러스터 TOP 10 (최신 1시간)
{cluster_text}

### ★ 24시간 누적 TOP 5 이슈 (리포트 핵심 — 지속성·영향력 기준)
{accumulated_text}

### ★ 24시간 누적 TOP 5 민심 반응 (리포트 핵심 — 채널별 감성 누적)
{accumulated_reaction_text}

### 현재 시점 반응지수 상세 (최신 1시간, 이슈별 소스 감성)
{reaction_detail or "없음"}

### AI 한줄 해석
- 이슈: {snap.get('ai_issue_summary', '없음')}
- 반응: {snap.get('ai_reaction_summary', '없음')}

{h24_analysis}

### 최근 7회 지표 추이 (일별)
{trend_text}

### 구조적 배경
- 경남 보수 텃밭. 7대(2018) 투표율 65.8%
- 연령구조: 2030세대 37.7%(감소), 60+ 39.5%(증가) → 인구만으로 13~14만표 열세
- 투표율 반영 시 여론조사 격차가 뒤집힐 수 있음 (60대 투표율 72.5% vs 20대 52%)
- 40대 지지율 64.1%로 최고 → 핵심 결집 대상
- 20대 부동층 44.9% → 설득 아닌 동원 필요 (무관심이 본질)
- 현직(박완수)은 예산·행정력·미디어 접근성에서 구조적 우위"""


def _load_daily_cache(today: str):
    """파일에서 오늘자 데일리 리포트 로드"""
    fp = LEGACY_DATA / "daily_reports" / f"{today}.json"
    if fp.exists():
        try:
            with open(fp) as f:
                data = json.load(f)
            if not data.get("error"):
                return data
        except Exception:
            pass
    return None


def _save_daily_cache(today: str, data: dict):
    """데일리 리포트를 파일로 영구 저장"""
    report_dir = LEGACY_DATA / "daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    fp = report_dir / f"{today}.json"
    with open(fp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


import threading

_generating = {"daily": False, "weekly": False}


def _generate_daily_sync():
    """백그라운드에서 데일리 리포트 생성 — report_meta 기반 누적 필터링"""
    global _generating
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        print(f"[Strategy] 데일리 생성 시작 ({today})", flush=True)
        snap = _load_snap()
        if not snap:
            print("[Strategy] WARNING: snap이 비어있음", flush=True)

        # report_meta에서 이전 생성 시각 읽기
        meta = _load_report_meta()
        since_ts = meta.get("last_daily_generated_at")
        print(f"[Strategy] meta 로드 완료, since_ts={since_ts}", flush=True)

        context = _build_daily_context(snap, since_timestamp=since_ts)
        print(f"[Strategy] context 빌드 완료 ({len(context)}자)", flush=True)
        _ensure_env()

        import anthropic
        client = anthropic.Anthropic()

        today_str = datetime.now().strftime("%m/%d")
        weekday_kr = ["월","화","수","목","금","토","일"][datetime.now().weekday()]

        prompt, system_msg = _build_daily_prompt(context, today_str, weekday_kr)
        print(f"[Strategy] AI 호출 시작...", flush=True)

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            system=system_msg,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        print(f"[Strategy] AI 응답 수신 ({len(text)}자)", flush=True)
        # 여야 표기 자동 교정 (AI가 국힘=여당으로 잘못 쓰는 패턴 강제 수정)
        for _old, _new in [
            ("여당 약세", "야당(국힘) 약세"), ("여당 분열", "야당(국힘) 분열"),
            ("여당 내홍", "야당(국힘) 내홍"), ("여당 지지율", "야당(국힘) 지지율"),
            ("여당이 유리", "야당(국힘)이 유리"), ("여당 약화", "야당(국힘) 약화"),
            ("여당 위기", "야당(국힘) 위기"), ("여당 갈등", "야당(국힘) 갈등"),
            ("여당 공천", "야당(국힘) 공천"), ("여당 비리", "야당(국힘) 비리"),
            ("여당의 분열", "야당(국힘)의 분열"), ("여당의 내홍", "야당(국힘)의 내홍"),
        ]:
            text = text.replace(_old, _new)
        data = _parse_json(text)
        data["generated_at"] = datetime.now().isoformat()
        data["d_day"] = snap.get("turnout", {}).get("correction", {}).get("d_day", "?")
        data["date"] = today
        data["data_since"] = since_ts or "all"

        # chart_data 첨부
        full_history = _load_history()
        filtered_for_chart = _filter_history_since(full_history, since_ts)
        data["chart_data"] = _build_chart_data(filtered_for_chart)

        if not data.get("error"):
            _cache["daily"]["date"] = today
            _cache["daily"]["data"] = data
            _save_daily_cache(today, data)
            # 성공 후에만 타임스탬프 기록
            meta["last_daily_generated_at"] = datetime.now().isoformat()
            _save_report_meta(meta)
            print(f"[Strategy] 데일리 리포트 생성 완료 (since={since_ts or 'all'})", flush=True)
        else:
            print(f"[Strategy] AI 응답에 error 포함: {data.get('error','')[:100]}", flush=True)
            _cache["daily"]["data"] = data
    except Exception as e:
        import traceback
        print(f"[Strategy] 데일리 생성 실패: {e}", flush=True)
        traceback.print_exc()
        _cache["daily"]["data"] = {"error": str(e), "generated_at": datetime.now().isoformat()}
    finally:
        _generating["daily"] = False


@router.get("/daily-briefing")
def daily_briefing():
    """최신 데일리 리포트 조회 (아카이브에서 로드, AI 호출 없음)"""
    # 생성 중이면 상태 반환
    if _generating.get("daily"):
        return {"status": "generating", "message": "리포트 생성 중... (1~2분)"}

    # 1. 메모리 캐시
    if _cache["daily"]["data"] and not _cache["daily"]["data"].get("error"):
        return _cache["daily"]["data"]

    # 2. 아카이브에서 최신 리포트 로드
    report_dir = LEGACY_DATA / "daily_reports"
    if report_dir.exists():
        files = sorted(report_dir.glob("*.json"), reverse=True)
        for fp in files[:5]:
            try:
                with open(fp) as f:
                    data = json.load(f)
                if not data.get("error"):
                    _cache["daily"]["date"] = fp.stem
                    _cache["daily"]["data"] = data
                    return data
            except Exception:
                continue

    return {"status": "empty", "message": "생성된 리포트가 없습니다. '리포트 생성' 버튼을 눌러주세요."}


@router.post("/daily-briefing/generate")
def generate_daily_briefing():
    """데일리 리포트 AI 생성 (수동 트리거) — 1일 1회 제한, 생성 후 아카이브 저장"""
    if _generating.get("daily"):
        return {"status": "generating", "message": "이미 생성 중입니다."}

    # 1일 1회 제한: 오늘 이미 성공적으로 생성된 리포트가 있으면 차단
    today = datetime.now().strftime("%Y-%m-%d")
    if _cache["daily"]["date"] == today and _cache["daily"]["data"] and not _cache["daily"]["data"].get("error"):
        return {"status": "already_generated", "message": f"오늘({today}) 리포트가 이미 생성되었습니다. 내일 다시 시도해주세요."}
    # 파일 아카이브도 확인
    today_file = LEGACY_DATA / "daily_reports" / f"{today}.json"
    if today_file.exists():
        try:
            with open(today_file) as _f:
                existing = json.load(_f)
            if not existing.get("error"):
                # 캐시에도 로드
                _cache["daily"]["date"] = today
                _cache["daily"]["data"] = existing
                return {"status": "already_generated", "message": f"오늘({today}) 리포트가 이미 생성되었습니다. 내일 다시 시도해주세요."}
        except Exception:
            pass

    _generating["daily"] = True
    threading.Thread(target=_generate_daily_sync, daemon=True).start()
    return {"status": "generating", "message": "리포트 생성 시작 (1~2분 소요)"}


@router.get("/daily-reports")
def list_daily_reports():
    """아카이브된 데일리 리포트 목록"""
    report_dir = LEGACY_DATA / "daily_reports"
    if not report_dir.exists():
        return {"reports": []}
    reports = []
    for fp in sorted(report_dir.glob("*.json"), reverse=True)[:30]:
        try:
            with open(fp) as f:
                data = json.load(f)
            reports.append({
                "date": fp.stem,
                "generated_at": data.get("generated_at", ""),
                "summary": data.get("executive_summary", data.get("summary", ""))[:100],
            })
        except Exception:
            continue
    return {"reports": reports}


def _build_daily_prompt(context: str, today_str: str, weekday_kr: str):
    prompt = f"""{context}

당신은 김경수 경남도지사 캠프의 전략 총 책임자입니다.
이것은 예측 리포트가 아닙니다. 진단 중심 전략 리포트입니다.

목적: 현재 정치 상황 진단 → 전략적 해석 → 전략 권고 → 실행 계획 → KPI/모니터링
예측(forecast)이나 확률 추정이 아닌, 캠프 의사결정을 위한 실행 문서입니다.

분석 레이어 (이 순서로 분석):
1. 이슈 상태 (무엇이 확산되고 있는가)
2. 반응 상태 (사람들이 어떻게 반응하는가) — 이슈 볼륨보다 중요
3. 세그먼트 반응 (어떤 세그먼트가 반응하는가)
4. 지역 반응 (어떤 지역이 반응하는가)
5. 조직 시그널 (동원 가능한 신호)
6. 전략적 판단 (공격 기회 / 방어 위험 / 관찰 항목)

아래 JSON 형식으로만 답변 (코드블록 없이 순수 JSON):
{{
  "executive_summary": "종합 요약 3줄 — 현재 국면 진단 + 핵심 위기·기회 + 오늘 반드시 해야 할 것. 차분하고 날카롭게.",

  "situation_diagnosis": {{
    "issue_state": [
      {{"rank": 1, "name": "이슈명", "count": 기사수, "side": "우리유리|상대유리|중립",
        "spreading": "확산 상태 — 확산 중|정체|소멸 중",
        "diagnosis": "무엇이 확산되고 있는가. 팩트만. 1줄"}}
    ],
    "reaction_state": [
      {{"rank": 1, "keyword": "키워드", "sentiment": "긍정|부정|혼합", "volume": "높음|보통|낮음",
        "stability": "안정|혼합|불안정",
        "reacting_segment": "주로 반응하는 세그먼트 (2030/4050/60+)",
        "reacting_region": "주로 반응하는 지역 (창원/김해/서부권/전체)",
        "strategic_meaning": "공격기회|방어위험|관찰항목"}}
    ],
    "our_candidate": "우리 후보 진단 — 강점·약점·기회·위협. 불확실한 시그널은 '시그널 약함' 또는 '혼합'으로 명시. 3줄",
    "opp_candidate": "상대 후보 진단 — 강점·약점 + 공략 가능한 틈. 3줄",
    "exposure_gap": {{
      "kim_articles": 김경수기사수, "park_articles": 박완수기사수,
      "insight": "노출 격차 해석 1줄"
    }}
  }},

  "decision_layer": {{
    "moment_type": "지금은 어떤 국면인가 (공격 국면|방어 국면|관찰 국면|전환 국면)",
    "must_protect": "반드시 지켜야 할 것 — 이탈 방지 대상·방어 필수 이슈",
    "can_push": "밀어볼 수 있는 것 — 공격 가능 이슈·확산 가능 메시지"
  }},

  "strategies": [
    {{
      "title": "전략 제목",
      "condition": "이 전략을 실행하는 조건 (if 이슈가 확산되고 반응이 긍정이면 → push)",
      "action": "구체적 실행 방안 2줄",
      "target": "타겟 세그먼트/지역",
      "intended_effect": "의도하는 효과 — 구체적이되 과도한 인과 주장 금지",
      "risk": "리스크 — 다른 세그먼트 역효과·기존 지지층 충돌 가능성",
      "timeline": "{today_str}({weekday_kr}) 즉시|오늘 오후|내일|이번 주"
    }}
  ],

  "daily_theme": {{
    "keyword": "오늘의 테마 키워드 1개 (예: 안정, 민생, 경제, 일자리, 안전, 청년, 균형발전, 방산, 결집)",
    "rationale": "왜 이 시점에 이 테마인가 — 오늘 이슈 상황 + 전략적 판단에 기반한 이유 2~3줄. 어떤 이슈가 이 테마를 요구하는지, 이 테마로 어떤 판세 효과를 기대하는지."
  }},

  "field_schedule": [
    {{
      "priority": 1,
      "when": "{today_str}({weekday_kr}) 오전|오후 또는 구체 날짜·시간",
      "theme": "이 방문의 테마 키워드 (daily_theme과 연결 — 안정, 민생, 경제, 일자리, 안전, 청년 등)",
      "theme_reason": "왜 이 장소에서 이 테마인가 — 이슈·전략과의 연결 1줄",
      "region": "방문 지역 (창원·김해·진주·양산·사천·거제 등 경남 시군)",
      "location": "구체 장소 (예: 창원 마산어시장, 김해 율하카페거리, 진주 경상국립대, 사천 항공우주산업단지)",
      "concept": "방문 컨셉 (예: 방산 일자리 현장 간담회, 청년 타운홀, 전통시장 민생 탐방)",
      "message": "현장에서 전달할 핵심 메시지 (20자 이내)",
      "sub_message": "메시지 근거 — 오늘 이슈·전략과의 연결 고리",
      "target_segment": "타겟 유권자 (4050 주부, 2030 청년, 60+ 어르신, 방산 종사자 등)",
      "media_plan": "언론 노출 계획 (보도자료·SNS 릴스·기자 동행·맘카페 후기 등)",
      "caution": "이 방문이 다른 세그먼트·지역에 미칠 역효과",
      "kpi": "성과 측정 (기사 건수·SNS 도달·현장 참석자·맘카페 반응 등)"
    }}
  ],

  "execution": [
    {{
      "when": "{today_str}({weekday_kr}) 즉시|오전|오후 또는 구체 날짜",
      "what": "할 일 (현장 방문 외 내부 실행 과제 — 보도자료·카드뉴스·방어 매뉴얼 등)",
      "who": "담당",
      "kpi": "측정 기준"
    }}
  ],

  "kpi_monitoring": [
    {{"metric": "모니터링 지표", "current": "현재 상태", "target": "목표", "check_timing": "확인 시점"}}
  ],

  "risk_management": [
    {{"risk": "위험 요소", "trigger": "이것이 발생하면", "response": "이렇게 대응", "owner": "담당"}}
  ],

  "beta_reference": {{
    "leading_index": 판세지수값,
    "note": "전략 판단 근거로 단독 사용 금지. 방향성 참고용. 안정화 중인 beta 지표."
  }}
}}

========================================
정당 구도 (절대 혼동 금지)
========================================
- 여당 = 더불어민주당 (이재명 대통령)
- 야당 = 국민의힘
- 우리 후보 = 김경수 (민주당, 여당)
- 상대 후보 = 박완수 (국민의힘, 야당, 현직 경남도지사)
국민의힘을 여당으로, 민주당을 야당으로 절대 표기하지 마세요.

========================================
작성 원칙
========================================
1. 진단(diagnosis)과 권고(recommendation)를 명확히 구분하라. 진단은 팩트, 권고는 판단.
2. 불확실한 시그널은 확정적으로 쓰지 마라 — "시그널 약함", "혼합", "추가 확인 필요" 명시.
3. 반응(reaction)이 이슈 볼륨보다 중요하다. 기사 100건이라도 민심 반응 없으면 아직 체감 전.
4. 전략은 조건 기반(condition-based)으로 작성 — "만약 ~이면 → ~한다" 형식.
5. 시그널이 좁으면 전체 캠페인 대응이 아닌 지역/세그먼트 한정 대응을 권고하라.
6. 상대 현직 성과 직접 부정 금지 → "더 잘할 수 있다" 확장 프레임.
7. 중앙당 이슈 편승 금지 → "경남만 보고 간다" 원칙.
8. **자체 지수(이슈지수·반응지수·판세지수) 수치와 감성 raw값을 본문에 직접 언급하지 마라.** 기사수, 여론조사, 투표율, 지지율 등 원천 데이터만 인용.
9. 톤: 차분하고 날카롭게. 내부용. 실행 지향. 학술적이거나 과장하지 않는다.
10. execution의 when은 구체 날짜 ({today_str} 기준)로 작성.

========================================
현장 방문 일정 작성 원칙 (field_schedule)
========================================
- 이슈 분석 → 대응 전략에서 도출된 핵심 의제를 현장 방문으로 연결하라.
- 경남 실제 지명·장소를 구체적으로 제안 (창원 마산어시장, 김해 율하카페거리, 진주 경상국립대, 사천 KAI 등).
- 방문 컨셉은 전략과 직결 — "방산 일자리 간담회", "청년 타운홀", "맘카페 주부 소통", "전통시장 민생 탐방" 등.
- 메시지는 현장에서 후보가 직접 말할 한 문장 — 짧고 임팩트 있게.
- 타겟 세그먼트를 명시 — 같은 지역이라도 4050 주부 vs 2030 청년 vs 60+ 어르신에 따라 장소·메시지가 달라야 한다.
- 하루 2~3개 현장 방문이 현실적. 오전·오후 배분.
- 서부권(진주·사천·고성)과 동부권(창원·김해·양산)의 균형을 고려하라.
- 미디어 플랜 필수 — 방문만으로는 효과 없다. 기자 동행, 보도자료, SNS 콘텐츠를 함께 설계.
- 각 방문의 역효과를 반드시 검토 (특정 지역 편중, 다른 세그먼트 소외 등).

========================================
진영 판단 원칙 (side 판정 필수 준수)
========================================
11. 현직 도지사(박완수)의 선거 직전 대규모 재정 지출(민생지원금·추경 등)은 "선심성 논란"이 동반되므로 무조건 상대유리가 아니다. 논란이 붙은 경우 → 상대불리 또는 양면 판정.
12. 국민의힘·보수 진영의 부정 이미지 이슈(재산 과다·내홍·커닝·비리 등)는 우리유리로 판정. 야당 부정 뉴스를 상대유리로 잘못 분류하지 마라.
13. 현직의 정책 발표라도 민심 반응에서 비판·논란이 감지되면 양면(우리유리+상대유리) 또는 상대불리로 판정해야 한다. 발표 자체가 아닌 민심 반응 톤을 기준으로 판단.
14. 대통령·여당 지도부의 경남 방문·지지 발언은 우리유리. 단, "중앙 의존" 비판이 동반되면 양면 판정.
15. 김경수 후보 관련 사법·도덕성 이슈는 상대유리. 단, 이미 해소된 과거 이슈의 재소환은 시그널 강도를 낮게 판정.
16. 판단이 애매한 경우 "중립"이 아닌, 양면 분석을 하라 — "우리에게는 ~한 측면이 유리하나, ~한 측면에서 상대에게도 활용 여지 있음" 식으로 서술.
17. 이재명 정부/여당 정책(분양·공급·예산 등)이 성과로 보도되면 → 우리유리. 동일 정책이 "선거 전 쏟아내기", "선심성", "포퓰리즘" 비판 프레임으로 보도되면 → 상대유리 (우리 정부 공격). 기사 톤을 반드시 확인하고 판단."""

    system_msg = """You are generating a Korean election campaign strategy report for internal campaign use.

This is NOT a forecasting report. This is a diagnosis-first strategy report.
Purpose: understand current political condition → interpret signals → recommend strategic actions.

IMPORTANT:
- Do NOT center the report around predictive polling or confidence bands.
- Do NOT overclaim causal certainty. When evidence is weak, say "시그널 약함" or "혼합".
- Leading Index (판세지수) is only a beta reference. It must NOT drive the report.

CORE ANALYTIC FRAME (use in order):
1. Issue state (무엇이 확산되고 있는가)
2. Reaction state (사람들이 어떻게 반응하는가) — MORE IMPORTANT than issue volume
3. Segment reaction (어떤 세그먼트가 반응하는가)
4. Regional reaction (어떤 지역이 반응하는가)
5. Organization signal (동원 가능한 신호)
6. Strategic judgment (공격 기회 / 방어 위험 / 관찰 항목)

MANDATORY DIAGNOSIS LOGIC — for each issue, explicitly answer:
- is the reaction stable, mixed, or unstable?
- is this an attack opportunity, defense risk, or watch item?
- which segment/region is most affected?

STRATEGY LOGIC — condition-based:
- if issue spreads but reaction is weak → monitor, avoid overreaction
- if reaction is expanding and sentiment is favorable → push
- if reaction is expanding and sentiment is unfavorable → counter or pivot
- if segment reaction is localized → region-specific action only
- Do NOT recommend broad campaign actions when signal is narrow.

REACTION DATA: 반응지수는 실제 블로그/카페/유튜브댓글/커뮤니티(디시/에펨/클리앙/더쿠/네이트판/82쿡/경남맘카페)/뉴스댓글에서 수집한 실데이터입니다. 반응 상세 데이터의 소스별 감성을 진단에 적극 활용하세요.

24시간 지수 흐름: 이슈지수·반응지수·판세지수의 24시간 변동 추이가 제공됩니다. 반드시 활용하세요:
- 각 지수의 최소~최대 범위를 언급
- 지수가 가장 높았던/낮았던 시점에 어떤 이슈가 있었는지 분석
- 지수 변동이 크면 원인 이슈를 특정하고, 안정적이면 "변동 없음"으로 진단
- executive_summary에 24시간 흐름 요약 포함

OUTPUT: Valid JSON only. No markdown, no code blocks. Start with { end with }. Write in Korean. Calm, sharp, execution-oriented tone."""
    return prompt, system_msg


@router.get("/daily-reports")
def daily_reports_list():
    """저장된 데일리 리포트 목록"""
    report_dir = LEGACY_DATA / "daily_reports"
    if not report_dir.exists():
        return {"reports": [], "total": 0}
    reports = []
    for fp in sorted(report_dir.glob("*.json"), reverse=True):
        try:
            with open(fp) as f:
                d = json.load(f)
            reports.append({
                "date": d.get("date", fp.stem),
                "d_day": d.get("d_day", "?"),
                "generated_at": d.get("generated_at", ""),
                "summary": d.get("executive_summary", "")[:100],
            })
        except Exception:
            pass
    return {"reports": reports[:30], "total": len(reports)}


def _load_week_dailies(week_key: str) -> list:
    """해당 주의 데일리 리포트 파일들을 로드. week_key: '2026-W13' 형식."""
    report_dir = LEGACY_DATA / "daily_reports"
    if not report_dir.exists():
        return []
    # week_key에서 해당 주의 월요일~일요일 날짜 범위 계산
    year, week_num = int(week_key[:4]), int(week_key.split("W")[1])
    from datetime import date
    # ISO week: 월요일 시작
    try:
        monday = date.fromisocalendar(year, week_num, 1)
        sunday = date.fromisocalendar(year, week_num, 7)
    except (ValueError, AttributeError):
        # Python 3.8 이하 폴백
        monday = date(year, 1, 4)  # ISO week 1 contains Jan 4
        monday -= timedelta(days=monday.weekday())
        monday += timedelta(weeks=week_num - 1)
        sunday = monday + timedelta(days=6)

    mon_str = monday.strftime("%Y-%m-%d")
    sun_str = sunday.strftime("%Y-%m-%d")

    dailies = []
    for fp in sorted(report_dir.glob("*.json")):
        date_str = fp.stem
        if mon_str <= date_str <= sun_str:
            try:
                with open(fp) as f:
                    d = json.load(f)
                if not d.get("error"):
                    dailies.append(d)
            except Exception:
                continue
    return dailies


def _build_weekly_context_from_dailies(dailies: list) -> str:
    """데일리 리포트들에서 위클리 컨텍스트 생성."""
    parts = []
    for i, d in enumerate(dailies, 1):
        date_str = d.get("date", f"Day {i}")
        summary = d.get("executive_summary", "없음")
        decision = d.get("decision_layer", {})
        theme = d.get("daily_theme", {})
        strategies = d.get("strategies", [])
        field = d.get("field_schedule", [])
        diagnosis = d.get("situation_diagnosis", {})

        strat_text = "\n".join(
            f"    - {s.get('title','')}: {s.get('action','')[:80]}"
            for s in strategies[:3]
        ) or "    없음"

        field_text = "\n".join(
            f"    - {f.get('region','')}: {f.get('concept','')}"
            for f in field[:2]
        ) or "    없음"

        # chart_data 요약
        chart = d.get("chart_data", {})
        chart_summary = ""
        if chart.get("summary"):
            cs = chart["summary"]
            chart_summary = f"\n  - 지수범위: 이슈 {cs.get('issue',{}).get('min','')}~{cs.get('issue',{}).get('max','')}, 반응 {cs.get('reaction',{}).get('min','')}~{cs.get('reaction',{}).get('max','')}, 판세 {cs.get('pandse',{}).get('min','')}~{cs.get('pandse',{}).get('max','')}"

        parts.append(f"""### [{date_str}] 데일리 리포트
  - 종합: {summary[:200]}
  - 국면: {decision.get('moment_type', '?')}
  - 테마: {theme.get('keyword', '?')} — {theme.get('rationale', '')[:100]}
  - 방어: {decision.get('must_protect', '?')[:100]}
  - 공격: {decision.get('can_push', '?')[:100]}{chart_summary}
  - 주요 전략:
{strat_text}
  - 현장일정:
{field_text}""")

    return "\n\n".join(parts)


@router.get("/weekly-briefing")
def weekly_briefing(force: bool = False):
    today = datetime.now().strftime("%Y-%m-%d")
    week_key = datetime.now().strftime("%Y-W%W")

    # 1. 메모리 캐시
    if not force and _cache["weekly"]["date"] == week_key and _cache["weekly"]["data"] and not _cache["weekly"]["data"].get("error"):
        return _cache["weekly"]["data"]

    # 2. 파일 캐시
    weekly_dir = LEGACY_DATA / "weekly_reports"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_fp = weekly_dir / f"{week_key}.json"
    if not force and weekly_fp.exists():
        try:
            with open(weekly_fp) as f:
                cached = json.load(f)
            if not cached.get("error"):
                _cache["weekly"]["date"] = week_key
                _cache["weekly"]["data"] = cached
                return cached
        except Exception:
            pass

    _ensure_env()

    # 데일리 기반 위클리 시도
    dailies = _load_week_dailies(week_key)
    use_dailies = len(dailies) >= 2

    if use_dailies:
        context = _build_weekly_context_from_dailies(dailies)
        context_header = f"## 주간 전략 종합 ({today}, {week_key}, 데일리 {len(dailies)}건 기반)\n\n{context}"
        source = "dailies"
    else:
        # 데일리 2개 미만 → 기존 raw 방식 폴백
        snap = _load_snap()
        history = _load_history()
        polls = _load_polls()
        corr = snap.get("turnout", {}).get("correction", {})

        week_data = history[-48:]
        first = week_data[0] if week_data else {}
        last = week_data[-1] if week_data else {}

        trend_text = "\n".join(
            f"  {h.get('date','')}: 이슈(김{h.get('issue_kim',0)}/박{h.get('issue_park',0)}) 반응(김{h.get('reaction_kim',0)}/박{h.get('reaction_park',0)}) 판세{h.get('pandse',50):.1f}"
            for h in week_data[::6]
        ) or "없음"

        polls_text = "\n".join(
            f"  - {p.get('label','')}: 김{p.get('kim',0)}% 박{p.get('park',0)}% ({p.get('date','')})"
            for p in polls[-5:]
        ) or "없음"

        context_header = f"""## 주간 성과 측정 데이터 ({today}, D-{corr.get('d_day','?')})

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
        source = "raw_fallback"

    try:
        import anthropic
        client = anthropic.Anthropic()

        prompt = f"""{context_header}

당신은 김경수 캠프 전략 총 책임자입니다. 한 주간 성과를 측정하는 위클리 리포트를 작성하세요.
{'이 위클리는 ' + str(len(dailies)) + '개 데일리 리포트를 종합한 것입니다. 각 데일리의 진단·전략·현장일정을 관통하는 주간 흐름과 성과를 분석하세요.' if use_dailies else ''}

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
            max_tokens=8000,
            system="You are a Korean election campaign strategist. Respond with valid JSON only. No markdown, no code blocks. Start with { end with }.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        data = _parse_json(text)
        data["generated_at"] = datetime.now().isoformat()
        data["week"] = week_key
        data["source"] = source
        data["dailies_count"] = len(dailies) if use_dailies else 0

        if not data.get("error"):
            _cache["weekly"]["date"] = week_key
            _cache["weekly"]["data"] = data
            with open(weekly_fp, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "generated_at": datetime.now().isoformat()}


@router.get("/training-data")
def training_data():
    """학습데이터 목록 반환 (최근 30일)"""
    training_dir = LEGACY_DATA / "training_data"
    if not training_dir.exists():
        return {"days": [], "total": 0}

    days = []
    for fp in sorted(training_dir.glob("*.json"), reverse=True):
        try:
            with open(fp) as f:
                d = json.load(f)
            days.append(d)
        except Exception:
            pass

    return {"days": days[:30], "total": len(days)}


@router.get("/side-corrections")
def get_side_corrections():
    """등록된 side 수정/규칙 목록"""
    corr_path = LEGACY_DATA / "side_corrections.json"
    if not corr_path.exists():
        return {"corrections": [], "rules": []}
    try:
        with open(corr_path) as f:
            return json.load(f)
    except Exception:
        return {"corrections": [], "rules": []}


@router.post("/side-corrections")
def add_side_correction(issue: str = "", side: str = "", reason: str = ""):
    """side 수정 추가 (프론트엔드용)"""
    if not issue or not side:
        return {"error": "issue와 side 필수"}
    corr_path = LEGACY_DATA / "side_corrections.json"
    data = {"corrections": [], "rules": []}
    if corr_path.exists():
        try:
            with open(corr_path) as f:
                data = json.load(f)
        except Exception:
            pass
    data["corrections"].append({
        "issue": issue, "side": side, "reason": reason,
        "timestamp": datetime.now().isoformat(),
    })
    data["corrections"] = data["corrections"][-50:]
    with open(corr_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "total_corrections": len(data["corrections"])}
