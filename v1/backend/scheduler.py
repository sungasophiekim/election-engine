"""자동 갱신 스케줄러 v2 — 광역 뉴스 수집 + AI 분류 + 이슈 강도"""
import sys
import os
import json
import threading
import time
import re
from pathlib import Path
from datetime import datetime

# 경로 설정
_ROOT = "/Users/sunga/Desktop/election_engine"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_V1 = str(Path(__file__).resolve().parent)
if _V1 not in sys.path:
    sys.path.append(_V1)

from v1config.settings import ENRICHMENT_PATH, LEGACY_DATA, INDEX_HISTORY_DIR


def _now():
    return datetime.now().strftime("%H:%M:%S")


def _ensure_env():
    """프로젝트 루트 .env 로드"""
    env_path = os.path.join(_ROOT, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _load_snap() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_snap(snap: dict):
    snap["timestamp"] = datetime.now().isoformat()
    with open(ENRICHMENT_PATH, "w") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════
# 광역 뉴스 수집 쿼리
# ═══════════════════════════════════════════════════════════════
BROAD_QUERIES = [
    "경남 선거", "경남도지사", "경상남도",
    "김경수", "박완수",
    "사천 KAI", "창원 선거", "김해 경남",
    "경남 청년", "부울경", "경남 산업",
]

# 이슈 분류 규칙
ISSUE_CATEGORIES = {
    "KF-21/방산": ["KF-21", "전투기", "KAI", "방산", "보라매", "양산 1호기", "국방", "무기"],
    "대통령/정부": ["이재명 대통령", "대통령 방문", "출고식", "정부", "청와대", "국무"],
    "행정통합/메가시티": ["부울경", "메가시티", "행정통합", "광역", "통합"],
    "도정/예산": ["추경", "도정", "생활지원금", "예산", "도청", "도비"],
    "SOC/교통": ["컨벤션", "화목", "공항", "KTX", "철도", "BRT", "고속도로", "항만"],
    "선거/공천": ["공천", "단수", "후보", "출마", "경선", "지방선거", "D-"],
    "정당/정치": ["국민의힘", "민주당", "정청래", "국힘", "여당", "야당", "진보당"],
    "산업/경제": ["산업", "일자리", "경제", "투자", "스마트", "AI", "로봇", "조선", "항공"],
    "청년/복지": ["청년", "복지", "돌봄", "인구", "교육", "출산", "노인"],
    "사법/스캔들": ["드루킹", "재판", "수사", "기소", "전과", "사법", "검찰"],
}


def _classify_article(title: str) -> str:
    """키워드 기반 1차 분류"""
    for cat, keywords in ISSUE_CATEGORIES.items():
        if any(kw in title for kw in keywords):
            return cat
    return ""


def _update_all():
    """전체 갱신: 광역 뉴스 수집 → 분류 → 클러스터링 → 후보 버즈 → 판세"""
    # sys.path + .env
    while _ROOT in sys.path:
        sys.path.remove(_ROOT)
    sys.path.insert(0, _ROOT)
    _ensure_env()

    try:
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG as cfg
        from collectors.naver_news import search_news, collect_issue_signals, _last_collection_meta
        from collectors.api_cache import wait_if_needed, record_call

        snap = _load_snap()
        src_ts = snap.get("source_timestamps", {})

        # ── 1. 광역 뉴스 수집 ──
        all_articles = []
        seen = set()
        for q in BROAD_QUERIES:
            try:
                wait_if_needed("naver_news")
                arts = search_news(q, display=30, sort="date")
                record_call("naver_news", success=True)
                for a in arts:
                    t = a.get("title", "")
                    if t not in seen:
                        seen.add(t)
                        a["query"] = q
                        a["category"] = _classify_article(t)
                        a["kim_linked"] = 1 if "김경수" in t else 0
                        a["park_linked"] = 1 if "박완수" in t else 0
                        all_articles.append(a)
                time.sleep(0.3)
            except Exception:
                pass

        src_ts["news_updated_at"] = datetime.now().isoformat()

        # ── 1.5 광역 수집 기반 이슈지수 (중복 없는 정확한 집계) ──
        seen_kim_titles = set()
        seen_park_titles = set()
        kim_articles = []
        park_articles = []
        for a in all_articles:
            title = a.get("title", "")
            if "김경수" in title and title not in seen_kim_titles:
                seen_kim_titles.add(title)
                kim_articles.append(a)
            if "박완수" in title and title not in seen_park_titles:
                seen_park_titles.add(title)
                park_articles.append(a)
        snap["broad_issue"] = {
            "kim_count": len(kim_articles),
            "park_count": len(park_articles),
            "total": len(all_articles),
            "updated_at": datetime.now().isoformat(),
        }
        print(f"[{_now()}] 광역 수집: {len(all_articles)}건 ({len(BROAD_QUERIES)}쿼리) | 김{len(kim_articles)} 박{len(park_articles)}", flush=True)

        # ── 2. AI 분류 (미분류만 — Haiku) ──
        unclassified = [a for a in all_articles if not a["category"]]
        if unclassified:
            try:
                classified_count = _ai_classify_batch(unclassified)
                print(f"[{_now()}] AI 분류: {classified_count}/{len(unclassified)}건", flush=True)
            except Exception as e:
                print(f"[{_now()}] AI 분류 스킵: {e}", flush=True)

        # ── 3. 이슈 클러스터링 + 강도 점수 ──
        clusters = {}
        for a in all_articles:
            cat = a.get("category", "기타") or "기타"
            if cat not in clusters:
                clusters[cat] = {"name": cat, "count": 0, "articles": [], "kim": 0, "park": 0, "side": "중립"}
            clusters[cat]["count"] += 1
            clusters[cat]["kim"] += a.get("kim_linked", 0)
            clusters[cat]["park"] += a.get("park_linked", 0)
            if len(clusters[cat]["articles"]) < 3:
                clusters[cat]["articles"].append({"title": a.get("title", ""), "source": a.get("source", "")})

        # AI 사건별 클러스터링 — 제목 기반
        scored_clusters = _ai_cluster_events(all_articles)
        snap["news_clusters"] = scored_clusters[:12]
        snap["news_clusters_timestamp"] = datetime.now().isoformat()
        src_ts["cluster_updated_at"] = datetime.now().isoformat()

        # ── 3.5 클러스터 기반 이슈/반응지수 (통합) ──
        our_count = sum(c.get("count", 0) for c in scored_clusters if "우리" in c.get("side", ""))
        opp_count = sum(c.get("count", 0) for c in scored_clusters if "상대" in c.get("side", ""))
        neutral_count = sum(c.get("count", 0) for c in scored_clusters if "중립" in c.get("side", ""))
        snap["cluster_issue"] = {
            "kim_count": our_count,
            "park_count": opp_count,
            "neutral_count": neutral_count,
            "total": our_count + opp_count + neutral_count,
            "updated_at": datetime.now().isoformat(),
        }

        print(f"[{_now()}] 클러스터: {len(scored_clusters)}개 (TOP: {scored_clusters[0]['name'] if scored_clusters else '없음'}) | 우리{our_count} 상대{opp_count} 중립{neutral_count}", flush=True)

        # ── 4. 후보 버즈 수집 ──
        kw_path = LEGACY_DATA / "monitor_keywords.json"
        try:
            with open(kw_path) as f:
                kw_data = json.load(f)
            cand_kws = [k["keyword"] for k in kw_data.get("keywords", []) if k.get("type", "").startswith("candidate")]
        except Exception:
            cand_kws = ["김경수 경남", "박완수 경남"]

        if cand_kws:
            cand_signals = collect_issue_signals(cand_kws, candidate_name=cfg.candidate_name, opponents=cfg.opponents)
            cand_titles_map = {}
            for cs in cand_signals:
                meta = _last_collection_meta.get(cs.keyword, {})
                cand_titles_map[cs.keyword] = [a.get("title", "") for a in meta.get("raw_articles", [])[:15]]

            cand_ai = {}
            try:
                _ensure_env()  # API 키 확인
                from engines.ai_sentiment import analyze_candidate_buzz_batch, _candidate_cache
                _candidate_cache.clear()  # 이전 빈 캐시 제거
                cand_ai = analyze_candidate_buzz_batch(
                    keyword_titles=cand_titles_map,
                    candidate_name=cfg.candidate_name, opponents=cfg.opponents,
                )
                print(f"[{_now()}] AI 감성: {len(cand_ai)}개 분석", flush=True)
            except Exception as e:
                print(f"[{_now()}] AI 감성 경고: {e}", flush=True)

            buzz = {}
            for cs in cand_signals:
                ai_s = cand_ai.get(cs.keyword, {})
                mc = getattr(cs, "mention_count", 0) or getattr(cs, "total_mentions", 0) or 0
                buzz[cs.keyword] = {
                    "mention_count": mc,
                    "velocity": round(mc / 10, 1),
                    "ai_sentiment": ai_s.to_dict() if hasattr(ai_s, "to_dict") else (ai_s if isinstance(ai_s, dict) else {}),
                }
            snap["candidate_buzz"] = buzz
            src_ts["sentiment_updated_at"] = datetime.now().isoformat()
            print(f"[{_now()}] 후보 버즈: {len(buzz)}개", flush=True)

        # ── 4.5 이슈/반응 인덱스 (커뮤니티+소셜+유튜브 포함) ──
        try:
            from engines.issue_scoring import calculate_issue_score
            from engines.issue_index import compute_issue_index
            from engines.reaction_index import compute_reaction_index

            # 이슈 키워드로 뉴스 수집 + 스코어링
            issue_kws_list = [k["keyword"] for k in kw_data.get("keywords", []) if k.get("type") == "issue" and k.get("priority") in ("high", "medium")][:10]
            if issue_kws_list:
                issue_signals = collect_issue_signals(issue_kws_list, candidate_name=cfg.candidate_name, opponents=cfg.opponents)
                issue_scores = sorted([calculate_issue_score(sig, cfg) for sig in issue_signals], key=lambda x: x.score, reverse=True)
                sig_map = {s.keyword: s for s in issue_signals}

                # 소셜/커뮤니티/유튜브 수집 (상위 5개)
                from collectors.community_collector import scan_all_communities
                from collectors.social_collector import search_blogs, search_cafes
                community_data = {}
                social_data = {}
                for kw in issue_kws_list[:5]:
                    try:
                        community_data[kw] = scan_all_communities(kw)  # CommunityReport 객체 그대로 저장
                    except Exception:
                        community_data[kw] = None
                    try:
                        b = search_blogs(kw, display=10)
                        c = search_cafes(kw, display=10)
                        social_data[kw] = {
                            "blogs": b if isinstance(b, list) else getattr(b, 'items', []) if b else [],
                            "cafes": c if isinstance(c, list) else getattr(c, 'items', []) if c else [],
                        }
                    except Exception:
                        social_data[kw] = {"blogs": [], "cafes": []}
                    time.sleep(0.3)

                ii_map = {}
                ri_map = {}
                for iss in issue_scores:
                    sig = sig_map.get(iss.keyword)
                    if not sig:
                        continue
                    kw = iss.keyword
                    soc = social_data.get(kw, {})
                    comm = community_data.get(kw, [])
                    # SocialSignal 객체에서 추출
                    soc_blogs = soc.get("blogs") if isinstance(soc, dict) else None
                    soc_cafes = soc.get("cafes") if isinstance(soc, dict) else None
                    blog_c = getattr(soc_blogs, 'total_count', 0) if soc_blogs else 0
                    cafe_c = getattr(soc_cafes, 'total_count', 0) if soc_cafes else 0
                    # CommunityReport 객체에서 추출
                    comm_mentions = getattr(comm, 'total_mentions', 0) if comm else 0
                    comm_viral = getattr(comm, 'has_any_viral', False) if comm else False
                    comm_resonance = getattr(comm, 'community_resonance', 0) if comm else 0

                    try:
                        ii = compute_issue_index(
                            keyword=kw, mention_count=sig.mention_count,
                            media_tier=sig.media_tier, velocity=sig.velocity,
                            candidate_linked=sig.candidate_linked,
                            blog_count=blog_c, cafe_count=cafe_c,
                            community_mentions=comm_mentions,
                        )
                        ii_map[kw] = ii
                    except Exception:
                        pass
                    # CommunitySignal 객체 리스트 직접 전달
                    comm_signals = comm.signals[:8] if comm and hasattr(comm, 'signals') else []
                    try:
                        ri = compute_reaction_index(
                            keyword=kw,
                            community_signals=comm_signals,
                            community_resonance=comm_resonance if comm_resonance else (min(25, comm_mentions * 0.01) if comm_mentions else 0),
                            community_has_viral=comm_viral,
                            community_dominant_tone=getattr(comm, 'dominant_tone', '') if comm else '',
                            blog_count=blog_c, cafe_count=cafe_c,
                            negative_ratio=sig.negative_ratio,
                            candidate_linked=sig.candidate_linked,
                            candidate_name=cfg.candidate_name,
                            opponents=cfg.opponents,
                        )
                        ri_map[kw] = ri
                    except Exception:
                        pass

                if ii_map:
                    snap["issue_indices"] = {kw: v.to_dict() for kw, v in ii_map.items()}
                if ri_map:
                    snap["reaction_indices"] = {kw: v.to_dict() for kw, v in ri_map.items()}
                _now_iso = datetime.now().isoformat()
                src_ts["community_updated_at"] = _now_iso
                src_ts["blog_updated_at"] = _now_iso
                src_ts["cafe_updated_at"] = _now_iso
                src_ts["youtube_updated_at"] = _now_iso
                src_ts["trends_updated_at"] = _now_iso
                print(f"[{_now()}] 이슈/반응 인덱스: {len(ii_map)}/{len(ri_map)}개", flush=True)
        except Exception as e:
            print(f"[{_now()}] 인덱스 경고: {e}", flush=True)

        # ── 5. 갤럽 대통령 지지율 자동 갱신 ──
        try:
            from collectors.national_poll_collector import get_latest_national_poll
            np = get_latest_national_poll()
            if np:
                snap["national_poll"] = np.to_dict() if hasattr(np, "to_dict") else np
                src_ts["national_poll_updated_at"] = datetime.now().isoformat()
                print(f"[{_now()}] 갤럽: 대통령 {snap['national_poll'].get('president_approval')}% 민주 {snap['national_poll'].get('dem_support')}% 국힘 {snap['national_poll'].get('ppp_support')}%", flush=True)
        except Exception as e:
            print(f"[{_now()}] 갤럽 경고: {e}", flush=True)

        # ── 6. 판세지수 + 변동 Alert ──
        # 판세 계산 전에 snap 저장 → predict_turnout()이 최신 데이터를 읽도록
        _save_snap(snap)

        try:
            from engines.turnout_predictor import predict_turnout
            # 모듈 캐시 클리어 → 최신 snap 강제 재로드
            import importlib
            import engines.turnout_predictor as _tp
            importlib.reload(_tp)
            predict_turnout = _tp.predict_turnout

            prev_pandse = snap.get("turnout", {}).get("correction", {}).get("pandse_index", 50)
            result = predict_turnout()
            snap["turnout"] = result.to_dict()
            corr = result.to_dict().get("correction", {})
            new_pandse = corr.get("pandse_index", 50)
            delta = round(new_pandse - prev_pandse, 1)
            src_ts["pandse_updated_at"] = datetime.now().isoformat()
            print(f"[{_now()}] 판세: {new_pandse}pt (변동 {delta:+.1f})", flush=True)

            # 1pt 이상 변동 시 Alert + AI 원인분석
            if abs(delta) >= 1.0:
                alert = _ai_pandse_alert(prev_pandse, new_pandse, delta, corr.get("factors", []))
                snap["pandse_alert"] = alert
                print(f"[{_now()}] 판세 ALERT: {delta:+.1f}pt — {alert.get('memo','')[:50]}", flush=True)
            else:
                snap.pop("pandse_alert", None)
        except Exception as e:
            print(f"[{_now()}] 판세 경고: {e}", flush=True)

        snap["source_timestamps"] = src_ts
        _save_snap(snap)

        # ── 6. 후보별 지표 히스토리 저장 ──
        try:
            _save_indices_history(snap)
        except Exception:
            pass

        print(f"[{_now()}] === 전체 갱신 완료 ===", flush=True)

    except Exception as e:
        print(f"[{_now()}] 전체 갱신 오류: {e}", flush=True)
        import traceback
        traceback.print_exc()


def _ai_cluster_events(articles: list) -> list:
    """AI로 기사 제목들을 사건별로 묶고 한줄 제목 생성"""
    if not articles:
        return []
    try:
        _ensure_env()
        import anthropic
        client = anthropic.Anthropic()

        # 상위 100건 제목만 전달 (토큰 절약)
        titles = [a.get("title", "") for a in articles[:100]]
        titles_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

        prompt = f"""다음은 경남 지역 뉴스 제목 {len(titles)}건입니다. 같은 사건/이슈를 묶어서 TOP 10을 만들어주세요.

{titles_text}

다음 JSON 형식으로 답변 (코드블록 없이 순수 JSON만):
[
  {{"name": "사건 한줄 요약 (20자 이내)", "count": 관련기사수, "side": "우리 유리|상대 유리|중립", "tip": "캠프 대응 Tip 2줄 이내", "articles": ["대표 기사 제목1", "대표 기사 제목2"]}},
  ...
]

판단 기준 (side) — 중립은 최소화, 적극적으로 판단:
- "우리 유리": 김경수/민주당에 긍정적, 박완수/국민의힘을 비판, 이재명 대통령 행사/방문/성과, 정부 정책 성과, 야당 내부 갈등
- "상대 유리": 박완수/국민의힘에 긍정적, 김경수/민주당을 비판/공격, 현직 도정 성과 발표, 드루킹/사법리스크, 여당 비리/스캔들
- "중립": 선거와 완전히 무관하거나, 양쪽에 동일하게 적용되는 경우만

필수 규칙:
- 이재명 대통령 경남 방문/행사(KF-21 출고식 등) → 반드시 "우리 유리"
- 박완수 도정 예산/추경/성과 발표 → 반드시 "상대 유리"
- 김경수/민주당 네거티브 공격 기사 → 반드시 "상대 유리"
- 국민의힘 내부 갈등/컷오프 논란 → 반드시 "우리 유리"
- 현직 도정 관련 사건·사고·관리부실(안전사고, 시설관리 등) → 반드시 "우리 유리" (현직 책임)
- 조금이라도 한쪽에 유리하면 중립 대신 해당 진영으로 판단
- 경남 선거와 무관한 뉴스는 제외
- 기사 수 많은 순
- tip: 김경수 캠프 전략팀 관점, 구체적 행동 2줄 이내, 짧은 단어 위주"""

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()

        # JSON 파싱
        # 코드블록 제거
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        clusters = json.loads(text)

        result = []
        for c in clusters[:12]:
            result.append({
                "name": c.get("name", ""),
                "count": c.get("count", 0),
                "side": c.get("side", "중립"),
                "tip": c.get("tip", ""),
                "articles": [{"title": t, "source": ""} for t in c.get("articles", [])[:3]],
            })

        print(f"[{_now()}] AI 클러스터링 성공: {len(result)}개 사건", flush=True)
        return result

    except Exception as e:
        print(f"[{_now()}] AI 클러스터링 실패: {e}", flush=True)
        # 폴백: 카테고리 기반
        cats = {}
        for a in articles:
            cat = a.get("category", "기타") or "기타"
            if cat not in cats:
                cats[cat] = {"name": cat, "count": 0, "articles": [], "kim": 0, "park": 0}
            cats[cat]["count"] += 1
            cats[cat]["kim"] += a.get("kim_linked", 0)
            cats[cat]["park"] += a.get("park_linked", 0)
            if len(cats[cat]["articles"]) < 3:
                cats[cat]["articles"].append({"title": a.get("title", ""), "source": ""})

        result = []
        for cat, c in sorted(cats.items(), key=lambda x: -x[1]["count"]):
            side = "우리 측" if c["kim"] > c["park"] * 2 else "상대 측 (현직)" if c["park"] > c["kim"] * 2 else "중립"
            result.append({
                "name": cat, "count": c["count"], "articles": c["articles"],
                "side": side, "urgency": "즉시" if c["count"] >= 10 else "오늘 내" if c["count"] >= 5 else "모니터링",
                "our_impact": 1 if "우리" in side else -1 if "상대" in side else 0,
                "opp_impact": -1 if "우리" in side else 1 if "상대" in side else 0,
                "score": min(100, c["count"] * 5),
            })
        return result[:12]


def _ai_classify_batch(articles: list) -> int:
    """미분류 기사를 Claude Haiku로 배치 분류"""
    try:
        import anthropic
        client = anthropic.Anthropic()
        categories_str = ", ".join(ISSUE_CATEGORIES.keys())
        classified = 0

        # 10건씩 배치
        for i in range(0, len(articles), 10):
            batch = articles[i:i+10]
            titles = "\n".join(f"{j+1}. {a['title']}" for j, a in enumerate(batch))
            prompt = f"""다음 뉴스 제목을 카테고리로 분류해주세요.
카테고리: {categories_str}, 기타

제목:
{titles}

각 번호에 대해 카테고리만 답변 (예: "1. 선거/공천\n2. KF-21/방산")"""

            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            for line in text.strip().split("\n"):
                m = re.match(r"(\d+)\.\s*(.+)", line.strip())
                if m:
                    idx = int(m.group(1)) - 1
                    cat = m.group(2).strip()
                    if 0 <= idx < len(batch) and cat in ISSUE_CATEGORIES:
                        batch[idx]["category"] = cat
                        classified += 1
            time.sleep(0.5)

        return classified
    except Exception as e:
        print(f"[{_now()}] AI 분류 오류: {e}", flush=True)
        return 0


def _save_indices_history(snap: dict):
    """후보별 지표 히스토리 저장 (indices_history.json에 append)"""
    hist_path = LEGACY_DATA / "indices_history.json"
    history = []
    try:
        with open(hist_path) as f:
            history = json.load(f)
    except Exception:
        pass

    buzz = snap.get("candidate_buzz", {})
    broad = snap.get("broad_issue", {})
    kim_m = broad.get("kim_count", 0) or sum(v.get("mention_count", 0) for k, v in buzz.items() if "김경수" in k)
    park_m = broad.get("park_count", 0) or sum(v.get("mention_count", 0) for k, v in buzz.items() if "박완수" in k)
    kim_sents = [v.get("ai_sentiment", {}).get("net_sentiment", 0) for k, v in buzz.items() if "김경수" in k]
    park_sents = [v.get("ai_sentiment", {}).get("net_sentiment", 0) for k, v in buzz.items() if "박완수" in k]
    kim_sent = round(sum(kim_sents) / max(len(kim_sents), 1) * 100)
    park_sent = round(sum(park_sents) / max(len(park_sents), 1) * 100)
    pandse = snap.get("turnout", {}).get("correction", {}).get("pandse_index", 50)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%m.%d %H:%M"),
        "issue_kim": kim_m,
        "issue_park": park_m,
        "reaction_kim": kim_sent,
        "reaction_park": park_sent,
        "pandse": pandse,
    }

    # 최근 100개만 유지
    history.append(entry)
    history = history[-100:]

    with open(hist_path, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _ai_pandse_alert(prev: float, now: float, delta: float, factors: list) -> dict:
    """판세지수 1pt 이상 변동 시 AI 원인분석"""
    try:
        _ensure_env()
        import anthropic
        client = anthropic.Anthropic()

        factors_text = "\n".join(f"  {f['name']}: {f['value']:+.1f} ({f.get('reason','')})" for f in factors)
        direction = "상승 (김경수 유리)" if delta > 0 else "하락 (박완수 유리)"

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": f"""판세지수가 {prev:.1f}pt → {now:.1f}pt로 {delta:+.1f}pt {direction}했습니다.

9개 팩터 현재 값:
{factors_text}

변동 원인을 2줄 이내, 짧은 단어 위주로 설명. 예시: "대통령 지지율 상승 → 대통령효과 팩터 +0.5 상승이 주요인"."""}],
        )
        memo = resp.content[0].text.strip()
    except Exception:
        memo = f"판세지수 {delta:+.1f}pt 변동 감지. 팩터 상세 확인 필요."

    return {
        "prev": prev,
        "now": now,
        "delta": delta,
        "direction": "up" if delta > 0 else "down",
        "memo": memo,
        "timestamp": datetime.now().isoformat(),
    }


def _daily_snapshot():
    """일일 스냅샷 (08:00)"""
    try:
        snap = _load_snap()
        today = datetime.now().strftime("%Y-%m-%d")
        ii = snap.get("issue_indices", {})
        ri = snap.get("reaction_indices", {})
        corr = snap.get("turnout", {}).get("correction", {})

        snapshot = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "leading_index": corr.get("pandse_index", 50),
            "leading_direction": "stable",
            "issue_index_avg": round(sum(v.get("index", 0) for v in ii.values()) / max(len(ii), 1), 1) if ii else 0,
            "reaction_index_avg": round(sum(v.get("final_score", 0) for v in ri.values()) / max(len(ri), 1), 1) if ri else 0,
            "opp_issue_avg": 45.0,
            "opp_reaction_avg": 31.5,
            "poll_actual_kim": 44.0,
            "poll_actual_park": 33.4,
            "poll_source": "여론조사꽃 2026-03-19",
            "actions_count": 0,
            "data_quality": "auto",
        }

        INDEX_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        fp = INDEX_HISTORY_DIR / f"snapshot_{today}.json"
        with open(fp, "w") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"[{_now()}] 스냅샷: {fp.name}", flush=True)
    except Exception as e:
        print(f"[{_now()}] 스냅샷 오류: {e}", flush=True)


def _scheduler_loop():
    """메인 루프"""
    print(f"[{_now()}] === 스케줄러 v2 시작 (광역수집 + AI분류) ===", flush=True)

    # 시작 시 즉시 실행
    _update_all()

    tick = 0
    while True:
        time.sleep(60)
        tick += 1

        # 10분마다 전체 갱신
        if tick % 10 == 0:
            _update_all()

        # 매일 08:00 스냅샷
        now = datetime.now()
        if now.hour == 8 and now.minute == 0:
            _daily_snapshot()


def start_scheduler():
    t = threading.Thread(target=_scheduler_loop, daemon=True)
    t.start()
    print(f"[{_now()}] 스케줄러 v2 스레드 시작", flush=True)
    return t
