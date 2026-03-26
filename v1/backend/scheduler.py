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
_ROOT = str(Path(__file__).resolve().parent.parent.parent)  # election_engine/
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
    os.makedirs(os.path.dirname(ENRICHMENT_PATH), exist_ok=True)
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
    print(f"[{_now()}] _update_all() 시작", flush=True)
    # sys.path + .env
    while _ROOT in sys.path:
        sys.path.remove(_ROOT)
    sys.path.insert(0, _ROOT)
    _ensure_env()

    # 환경변수 확인
    naver_id = os.environ.get("NAVER_CLIENT_ID", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"[{_now()}] ENV 확인: NAVER_ID={'있음' if naver_id else '없음'}, ANTHROPIC={'있음' if anthropic_key else '없음'}", flush=True)

    try:
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG as cfg
        from collectors.naver_news import search_news, collect_issue_signals, _last_collection_meta
        from collectors.api_cache import wait_if_needed, record_call
        print(f"[{_now()}] import 성공", flush=True)

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
        # AI 한줄 해석 추출
        _ai_issue_summary = scored_clusters[0].pop("_issue_summary", "") if scored_clusters else ""
        _ai_reaction_summary = scored_clusters[0].pop("_reaction_summary", "") if scored_clusters else ""
        for c in scored_clusters:
            c.pop("_issue_summary", None)
            c.pop("_reaction_summary", None)
        snap["news_clusters"] = scored_clusters[:12]
        snap["news_clusters_timestamp"] = datetime.now().isoformat()
        snap["ai_issue_summary"] = _ai_issue_summary
        snap["ai_reaction_summary"] = _ai_reaction_summary
        src_ts["cluster_updated_at"] = datetime.now().isoformat()

        # ── 3.5 클러스터 기반 이슈지수 (가중지수: 기사수 × 감성강도) ──
        our_score, opp_score = 0.0, 0.0
        our_count, opp_count, neutral_count = 0, 0, 0
        for c in scored_clusters:
            cnt = c.get("count", 0)
            # 감성강도: 0~100 (절대값), 최소 10 보장 (건수만 있어도 반영)
            intensity = max(10, abs(c.get("sentiment", 0)))
            impact = cnt * intensity
            side = c.get("side", "")
            if "우리" in side:
                our_score += impact
                our_count += cnt
            elif "상대" in side:
                opp_score += impact
                opp_count += cnt
            else:
                neutral_count += cnt

        # 지수화: 50pt 기준 (our_score / total_score × 100), 데이터 없으면 50
        total_score = our_score + opp_score
        issue_index = round(our_score / total_score * 100, 1) if total_score > 0 else 50.0

        snap["cluster_issue"] = {
            "kim_count": our_count,
            "park_count": opp_count,
            "neutral_count": neutral_count,
            "total": our_count + opp_count + neutral_count,
            "kim_score": round(our_score),
            "park_score": round(opp_score),
            "issue_index": issue_index,  # 50=중립, >50 우리유리, <50 상대유리
            "updated_at": datetime.now().isoformat(),
        }

        # 반응지수: 클러스터 키워드 → 실데이터 수집 (블로그/카페/유튜브/커뮤니티/뉴스댓글)
        print(f"[{_now()}] 클러스터: {len(scored_clusters)}개 (TOP: {scored_clusters[0]['name'] if scored_clusters else '없음'}) | 우리{our_count} 상대{opp_count} 중립{neutral_count}", flush=True)

        try:
            reaction_data = _collect_cluster_reactions(scored_clusters)
            if reaction_data and reaction_data.get("total_mentions", 0) > 0:
                snap["cluster_reaction"] = reaction_data
                print(f"[{_now()}] 반응지수(실데이터): {reaction_data['reaction_index']:.1f}pt | {reaction_data['total_mentions']}건 수집", flush=True)
            else:
                # 폴백: AI 예측 기반 50pt 스케일
                snap["cluster_reaction"] = _ai_fallback_reaction(scored_clusters)
                print(f"[{_now()}] 반응지수(AI폴백): {snap['cluster_reaction'].get('reaction_index', 50):.1f}pt", flush=True)
        except Exception as e:
            print(f"[{_now()}] 반응수집 오류, AI폴백 사용: {e}", flush=True)
            snap["cluster_reaction"] = _ai_fallback_reaction(scored_clusters)

        # ── 4. 후보 버즈 수집 ──
        kw_path = LEGACY_DATA / "monitor_keywords.json"
        kw_data = {"keywords": []}
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
{{
  "clusters": [
    {{"name": "사건 한줄 요약 (20자 이내)", "count": 관련기사수, "side": "우리 유리|상대 유리|중립", "sentiment": 감성점수(-100~+100), "community_expected": "긍정|부정|중립", "tip": "캠프 대응 Tip 2줄 이내", "articles": ["대표 기사 제목1", "대표 기사 제목2"]}},
    ...
  ],
  "issue_summary": "이슈지수 한줄 해석 (오늘 미디어에서 어느 쪽이 유리한지 20자 요약)",
  "reaction_summary": "반응지수 한줄 해석 (시민 여론 감성이 어느 쪽에 유리한지 20자 요약)"
}}

판단 기준 (side) — 중립은 최소화, 적극적으로 판단:
- "우리 유리": 김경수/민주당에 긍정적, 박완수/국민의힘을 비판, 이재명 대통령 행사/방문/성과, 정부 정책 성과, 야당 내부 갈등
- "상대 유리": 박완수/국민의힘에 긍정적, 김경수/민주당을 비판/공격, 현직 도정 성과 발표, 드루킹/사법리스크, 여당 비리/스캔들
- "중립": 선거와 완전히 무관하거나, 양쪽에 동일하게 적용되는 경우만

필수 규칙:
- 이재명 대통령 경남 방문/행사(KF-21 출고식 등) → 반드시 "우리 유리"
- 박완수 도정 예산/추경/성과 발표 → 기본 "상대 유리". 단, 선심성 논란/비판이 동반되면 "우리 유리"로 전환
- 김경수/민주당 네거티브 공격 기사 → 반드시 "상대 유리"
- 국민의힘 내부 갈등/컷오프 논란 → 반드시 "우리 유리"
- 국민의힘/보수 진영 부정 이미지 이슈(재산 과다, 비리, 커닝, 도덕성) → 반드시 "우리 유리". 야당 부정 뉴스를 상대유리로 분류하지 마라
- 현직 도정 관련 사건·사고·관리부실(안전사고, 시설관리 등) → 반드시 "우리 유리" (현직 책임)
- 선거 직전 현직의 대규모 재정 지출(민생지원금·추경 등)에 "선심성", "표 매수", "돈 뿌리기" 등 비판 톤이 기사에 포함되면 → "우리 유리"
- 광역단체장/국회의원 재산공개에서 국민의힘 인사가 상위권 → "우리 유리" (부자 정당 프레임)
- 이재명 정부/여당 정책(분양·공급·예산 등)이 성과로 보도되면 → "우리 유리". 동일 정책이 "선거 전 쏟아내기", "선심성", "포퓰리즘" 등 비판 프레임으로 보도되면 → "상대 유리" (우리 정부 공격). 기사 톤을 반드시 확인하고 판단
- 조금이라도 한쪽에 유리하면 중립 대신 해당 진영으로 판단
- 경남 선거와 무관한 뉴스는 제외
- 기사 수 많은 순
- tip: 김경수 캠프 전략팀 관점, 구체적 행동 2줄 이내, 짧은 단어 위주
- sentiment: 김경수에게 긍정이면 +, 부정이면 - (-100~+100)
- community_expected: 일반 시민 커뮤니티에서 예상되는 반응 (긍정/부정/중립)

issue_summary와 reaction_summary는 반드시 포함 (clusters 배열 밖 최상위 필드)"""

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

        parsed = json.loads(text)

        # 래퍼 객체 형식: {"clusters": [...], "issue_summary": "...", "reaction_summary": "..."}
        # 또는 배열 형식: [...]  (폴백)
        if isinstance(parsed, dict) and "clusters" in parsed:
            cluster_list = parsed["clusters"]
            issue_summary = parsed.get("issue_summary", "")
            reaction_summary = parsed.get("reaction_summary", "")
        elif isinstance(parsed, list):
            cluster_list = parsed
            issue_summary = ""
            reaction_summary = ""
            # 배열 마지막에 summary 객체가 있을 수 있음
            for c in cluster_list:
                if "issue_summary" in c:
                    issue_summary = c["issue_summary"]
                    reaction_summary = c.get("reaction_summary", "")
        else:
            cluster_list = []
            issue_summary = ""
            reaction_summary = ""

        result = []
        for c in cluster_list[:12]:
            if "issue_summary" in c:
                continue
            result.append({
                "name": c.get("name", ""),
                "count": c.get("count", 0),
                "side": c.get("side", "중립"),
                "sentiment": c.get("sentiment", 0),
                "community_expected": c.get("community_expected", "중립"),
                "tip": c.get("tip", ""),
                "articles": [{"title": t, "source": ""} for t in c.get("articles", [])[:3]],
            })

        # summary를 첫 번째 클러스터에 메타로 첨부 (snap 저장용)
        if result:
            result[0]["_issue_summary"] = issue_summary
            result[0]["_reaction_summary"] = reaction_summary

        print(f"[{_now()}] AI 클러스터링 성공: {len(result)}개 사건 | 해석: {bool(issue_summary)}", flush=True)
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
            # 진영 판정: 카테고리 + 언급비율 기반
            cat_lower = cat.lower() if cat else ""
            if any(kw in cat_lower for kw in ["사법", "스캔들", "드루킹"]):
                side = "상대 유리"
            elif any(kw in cat_lower for kw in ["정당/정치"]) and c["park"] > c["kim"]:
                side = "우리 유리"  # 국민의힘 부정 뉴스
            elif c["kim"] > c["park"] * 2:
                side = "우리 유리"
            elif c["park"] > c["kim"] * 2:
                side = "상대 유리"
            else:
                side = "중립"
            result.append({
                "name": cat, "count": c["count"], "articles": c["articles"],
                "side": side, "urgency": "즉시" if c["count"] >= 10 else "오늘 내" if c["count"] >= 5 else "모니터링",
                "our_impact": 1 if "우리" in side else -1 if "상대" in side else 0,
                "opp_impact": -1 if "우리" in side else 1 if "상대" in side else 0,
                "score": min(100, c["count"] * 5),
            })
        return result[:12]


def _ai_fallback_reaction(clusters: list) -> dict:
    """AI 클러스터 감성으로 반응지수 50pt 폴백 계산"""
    our_score, opp_score = 0.0, 0.0
    for c in clusters:
        cnt = c.get("count", 0)
        sent = c.get("sentiment", 0)
        impact = cnt * abs(sent) / 100  # 정규화
        if "우리" in c.get("side", ""):
            if sent > 0:
                our_score += impact
            else:
                opp_score += impact
        elif "상대" in c.get("side", ""):
            if sent < 0:
                our_score += impact  # 상대에 부정 = 우리에 유리
            else:
                opp_score += impact
    total = our_score + opp_score
    idx = round(our_score / total * 100, 1) if total > 0 else 50.0
    return {"reaction_index": idx, "updated_at": datetime.now().isoformat()}


def _collect_cluster_reactions(clusters: list) -> dict:
    """클러스터 키워드 → 블로그/카페/유튜브댓글/커뮤니티/뉴스댓글 수집 → AI 감성 종합"""
    if not clusters:
        return {}

    _ensure_env()
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 상위 10개 클러스터 키워드 추출
    keywords = []
    for c in clusters[:10]:
        name = c.get("name", "")
        if name:
            # 짧은 핵심 키워드로 변환 (20자 이내 → 그대로 사용)
            keywords.append({"keyword": name, "side": c.get("side", "중립")})

    if not keywords:
        return {}

    print(f"[{_now()}] 반응수집 시작: {len(keywords)}개 키워드", flush=True)

    # 소스별 수집 결과
    all_reactions = []

    def _collect_one(kw_info):
        """단일 키워드에 대해 4개 소스 수집"""
        kw = kw_info["keyword"]
        side = kw_info["side"]
        result = {"keyword": kw, "side": side, "sources": {}}

        # 1. 블로그 + 카페
        try:
            from collectors.social_collector import search_blogs, search_cafes
            blog = search_blogs(kw, display=30)
            result["sources"]["blog"] = {
                "count": blog.recent_24h,
                "total": blog.total_count,
                "net_sentiment": blog.net_sentiment,
                "titles": [item.get("title", "") for item in blog.top_items[:3]],
            }
        except Exception as e:
            print(f"[{_now()}] 블로그 수집 실패({kw[:10]}): {e}", flush=True)

        try:
            from collectors.social_collector import search_cafes
            cafe = search_cafes(kw, display=30)
            result["sources"]["cafe"] = {
                "count": cafe.recent_24h,
                "total": cafe.total_count,
                "net_sentiment": cafe.net_sentiment,
                "titles": [item.get("title", "") for item in cafe.top_items[:3]],
            }
        except Exception as e:
            print(f"[{_now()}] 카페 수집 실패({kw[:10]}): {e}", flush=True)

        # 2. 유튜브 댓글
        try:
            from collectors.youtube_collector import fetch_keyword_comments as yt_comments
            yt = yt_comments(kw, top_n_videos=2, max_comments_per_video=20)
            result["sources"]["youtube"] = {
                "videos": yt.videos_analyzed,
                "comments": yt.total_comments,
                "net_sentiment": yt.net_sentiment,
                "positive_ratio": yt.positive_ratio,
                "negative_ratio": yt.negative_ratio,
            }
        except Exception as e:
            print(f"[{_now()}] 유튜브 수집 실패({kw[:10]}): {e}", flush=True)

        # 3. 커뮤니티 (주요 5개만 — 디시, 에펨, 클리앙, 더쿠, 네이트판)
        try:
            from collectors.community_collector import search_community
            comm_total = 0
            comm_sent_sum = 0.0
            comm_count = 0
            comm_titles = []
            for cid in ["dcinside", "fmkorea", "clien", "theqoo", "natepann", "82cook", "momcafe_changwon", "momcafe_gimhae", "momcafe_jinju", "momcafe_yangsan"]:
                try:
                    sig = search_community(kw, cid)
                    if sig.result_count > 0:
                        comm_total += sig.result_count
                        sent = sig.positive_ratio - sig.negative_ratio
                        comm_sent_sum += sent
                        comm_count += 1
                        comm_titles.extend(sig.recent_titles[:2])
                except Exception:
                    pass
            result["sources"]["community"] = {
                "mentions": comm_total,
                "net_sentiment": round(comm_sent_sum / comm_count, 3) if comm_count > 0 else 0,
                "sites_active": comm_count,
                "titles": comm_titles[:5],
            }
        except Exception as e:
            print(f"[{_now()}] 커뮤니티 수집 실패({kw[:10]}): {e}", flush=True)

        # 4. 뉴스 댓글
        try:
            from collectors.news_comment_collector import fetch_keyword_comments as news_comments
            nc = news_comments(kw, max_articles=3, max_comments_per_article=15)
            result["sources"]["news_comments"] = {
                "articles": nc.articles_analyzed,
                "comments": nc.total_comments,
                "net_sentiment": nc.net_sentiment,
                "likes": nc.total_likes,
                "dislikes": nc.total_dislikes,
                "reaction_grade": nc.reaction_grade,
            }
        except Exception as e:
            print(f"[{_now()}] 뉴스댓글 수집 실패({kw[:10]}): {e}", flush=True)

        return result

    # 병렬 수집 (3 workers — API rate limit 고려)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_collect_one, kw): kw for kw in keywords}
        for fut in as_completed(futures):
            try:
                all_reactions.append(fut.result())
            except Exception:
                pass

    # ── 종합: 우리/상대별 실제 반응 감성 집계 ──
    our_sentiments = []
    opp_sentiments = []
    total_mentions = 0
    source_details = []

    for rx in all_reactions:
        side = rx["side"]
        sources = rx["sources"]
        kw_sent_values = []

        for src_name, src_data in sources.items():
            sent = src_data.get("net_sentiment", 0)
            count = src_data.get("count", 0) or src_data.get("comments", 0) or src_data.get("mentions", 0)
            total_mentions += count
            if sent != 0:
                kw_sent_values.append(sent)

        if kw_sent_values:
            avg_sent = sum(kw_sent_values) / len(kw_sent_values)
            if "우리" in side:
                our_sentiments.append(avg_sent)
            elif "상대" in side:
                opp_sentiments.append(avg_sent)

        source_details.append(rx)

    # 50pt 스케일 지수화
    # side 방향을 반영: 우리유리 이슈의 시민 반응 강도 vs 상대유리 이슈의 시민 반응 강도
    # 핵심: 반응의 "방향"이 아닌 "강도"를 비교 — 어느 쪽 이슈에 시민이 더 반응하는가
    our_intensity = sum(abs(s) for s in our_sentiments) / len(our_sentiments) if our_sentiments else 0
    opp_intensity = sum(abs(s) for s in opp_sentiments) / len(opp_sentiments) if opp_sentiments else 0

    # 우리유리 이슈 건수 가중
    our_weight = our_intensity * len(our_sentiments)
    opp_weight = opp_intensity * len(opp_sentiments)
    total_weight = our_weight + opp_weight

    # 50pt 기준: 우리유리 이슈에 반응이 더 크면 >50
    reaction_index = round(our_weight / total_weight * 100, 1) if total_weight > 0 else 50.0

    collected_sources = set()
    for rx in all_reactions:
        collected_sources.update(rx.get("sources", {}).keys())

    print(f"[{_now()}] 반응수집 완료: {len(all_reactions)}개 키워드 × {len(collected_sources)}개 소스 | 총 {total_mentions}건 | 반응지수 {reaction_index:.1f}pt", flush=True)

    return {
        "reaction_index": reaction_index,  # 50pt 기준
        "kim_sentiment": round(our_intensity * 100),
        "park_sentiment": round(opp_intensity * 100),
        "total_mentions": total_mentions,
        "sources_collected": list(collected_sources),
        "keywords_analyzed": len(all_reactions),
        "details": source_details,
        "updated_at": datetime.now().isoformat(),
    }


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
    """3개 지수 히스토리 저장 (indices_history.json에 append) — 1시간마다"""
    hist_path = LEGACY_DATA / "indices_history.json"
    history = []
    try:
        with open(hist_path) as f:
            history = json.load(f)
    except Exception:
        pass

    ci = snap.get("cluster_issue", {})
    cr = snap.get("cluster_reaction", {})
    pandse = snap.get("turnout", {}).get("correction", {}).get("pandse_index", 50)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%m.%d %H:%M"),
        "issue_index": ci.get("issue_index", 50),
        "reaction_index": cr.get("reaction_index", 50),
        "pandse": pandse,
        # 하위 호환: 차트에서 사용
        "issue_kim": ci.get("kim_count", 0),
        "issue_park": ci.get("park_count", 0),
        "reaction_kim": cr.get("kim_sentiment", 0),
        "reaction_park": cr.get("park_sentiment", 0),
    }

    # 최근 168개 유지 (7일 × 24시간)
    history.append(entry)
    history = history[-168:]

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
    """일일 학습데이터 스냅샷 (08:00) — 3개 지수 + 이슈 클러스터 + 반응 상세 + 여론조사"""
    try:
        snap = _load_snap()
        today = datetime.now().strftime("%Y-%m-%d")

        ci = snap.get("cluster_issue", {})
        cr = snap.get("cluster_reaction", {})
        corr = snap.get("turnout", {}).get("correction", {})
        np_data = snap.get("national_poll", {})
        clusters = snap.get("news_clusters", [])

        # ── 1. 일일 스냅샷 (기존 호환) ──
        INDEX_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "issue_index": ci.get("issue_index", 50),
            "reaction_index": cr.get("reaction_index", 50),
            "leading_index": corr.get("pandse_index", 50),
            "issue_index_avg": ci.get("issue_index", 50),
            "reaction_index_avg": cr.get("reaction_index", 50),
            "data_quality": "auto",
        }
        fp = INDEX_HISTORY_DIR / f"snapshot_{today}.json"
        with open(fp, "w") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        # ── 2. 학습데이터 (일별 전체 컨텍스트 저장) ──
        TRAINING_DIR = LEGACY_DATA / "training_data"
        TRAINING_DIR.mkdir(parents=True, exist_ok=True)

        training = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "d_day": corr.get("d_day", 0),

            # 3개 지수
            "indices": {
                "issue_index": ci.get("issue_index", 50),
                "reaction_index": cr.get("reaction_index", 50),
                "pandse_index": corr.get("pandse_index", 50),
            },

            # 이슈 상세
            "issue_detail": {
                "kim_count": ci.get("kim_count", 0),
                "park_count": ci.get("park_count", 0),
                "kim_score": ci.get("kim_score", 0),
                "park_score": ci.get("park_score", 0),
            },

            # 반응 상세
            "reaction_detail": {
                "total_mentions": cr.get("total_mentions", 0),
                "sources_collected": cr.get("sources_collected", []),
                "kim_sentiment": cr.get("kim_sentiment", 0),
                "park_sentiment": cr.get("park_sentiment", 0),
            },

            # 판세 팩터
            "pandse_factors": corr.get("factors", []),

            # 뉴스 클러스터 TOP 10
            "top_issues": [
                {
                    "name": c.get("name", ""),
                    "count": c.get("count", 0),
                    "side": c.get("side", ""),
                    "sentiment": c.get("sentiment", 0),
                    "community_expected": c.get("community_expected", ""),
                    "tip": c.get("tip", ""),
                }
                for c in clusters[:10]
            ],

            # AI 해석
            "ai_summary": {
                "issue": snap.get("ai_issue_summary", ""),
                "reaction": snap.get("ai_reaction_summary", ""),
            },

            # 여론조사
            "poll": {
                "president_approval": np_data.get("president_approval", 0),
                "dem_support": np_data.get("dem_support", 0),
                "ppp_support": np_data.get("ppp_support", 0),
                "party_gap": np_data.get("party_gap", 0),
            },

            # 반응 수집 키워드별 상세 (학습용)
            "reaction_by_keyword": cr.get("details", []),
        }

        tp = TRAINING_DIR / f"{today}.json"
        with open(tp, "w") as f:
            json.dump(training, f, ensure_ascii=False, indent=2)

        print(f"[{_now()}] 일일 스냅샷 + 학습데이터 저장: {fp.name}, {tp.name}", flush=True)
    except Exception as e:
        print(f"[{_now()}] 스냅샷 오류: {e}", flush=True)


def _scheduler_loop():
    """메인 루프"""
    print(f"[{_now()}] === 스케줄러 v2 시작 (광역수집 + AI분류) ===", flush=True)

    # 시작 시 즉시 전체 갱신 실행
    try:
        _update_all()
    except Exception as e:
        print(f"[{_now()}] _scheduler_loop 내 _update_all 크래시: {e}", flush=True)
        import traceback
        traceback.print_exc()

    tick = 0
    while True:
        time.sleep(60)
        tick += 1

        # 60분마다 전체 갱신 (이슈수집 → 반응수집 포함)
        if tick % 60 == 0:
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
