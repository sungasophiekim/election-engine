"""Enrichment API — 뉴스 클러스터, 이슈/리액션 레이더"""
import json
from fastapi import APIRouter
from v1config.settings import ENRICHMENT_PATH

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


def _load() -> dict:
    try:
        with open(ENRICHMENT_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


@router.get("/news-clusters")
def news_clusters():
    snap = _load()
    return {
        "clusters": snap.get("news_clusters", []),
        "timestamp": snap.get("news_clusters_timestamp", ""),
    }


@router.get("/issue-radar")
def issue_radar():
    snap = _load()
    ii = snap.get("issue_indices", {})
    items = sorted(
        [{"keyword": k, **v} for k, v in ii.items()],
        key=lambda x: x.get("index", 0),
        reverse=True,
    )
    return {"items": items[:15], "total": len(ii)}


@router.get("/reaction-radar")
def reaction_radar():
    """클러스터 기반 민심 반응 레이더 — 이슈별 댓글·감성·세그먼트(커뮤니티 실데이터)"""
    snap = _load()
    clusters = snap.get("news_clusters", [])
    cr_details = {d["keyword"]: d for d in snap.get("cluster_reaction", {}).get("details", [])}

    # demographic → 세그먼트 매핑
    DEMO_TO_SEG = {
        "2030 남성": "2030", "2030 여성": "2030", "2030": "2030",
        "3040 남성": "3040", "3040 남성, 진보 성향": "3040", "3040 중도": "3040", "3040 여성": "3040",
        "3040 여성 (창원/함안)": "3040", "3040 여성 (김해)": "3040",
        "3040 여성 (진주/서부경남)": "3040", "3040 여성 (양산 물금/사송)": "3040",
        "3040 여성 (사천/삼천포)": "3040",
        "3050 (클리앙 이주민, 진보 결집지)": "3050",
        "2040 여성": "2040",
        "전 연령 남성 중심": "전체", "전 연령": "전체",
    }
    # 커뮤니티 ID → 지역 매핑 (맘카페 기반)
    COMM_TO_REGION = {
        "momcafe_changwon": "창원", "momcafe_gimhae": "김해",
        "momcafe_jinju": "서부권(진주)", "momcafe_yangsan": "양산",
        "momcafe_sacheon": "서부권(사천)",
    }

    items = []
    for c in clusters[:10]:
        count = c.get("count", 0)
        comments = c.get("comments", 0)
        sentiment = c.get("sentiment", 0)
        reaction_score = count + (comments * 3)

        # 실데이터 기반 세그먼트: cluster_reaction에서 커뮤니티 breakdown 추출
        name = c.get("name", "")
        cr = cr_details.get(name, {})
        comm_breakdown = cr.get("sources", {}).get("community", {}).get("breakdown", [])

        segments = []
        seg_merged = {}  # 연령 세그먼트별 합산
        region_merged = {}  # 지역 세그먼트별 합산

        for cb in comm_breakdown:
            demo = cb.get("demographic", "전체")
            seg_label = DEMO_TO_SEG.get(demo, demo)
            mentions = cb.get("mentions", 0)
            sent = cb.get("sentiment", 0)
            cid = cb.get("id", "")
            cname = cb.get("name", "")

            # 연령 세그먼트
            if seg_label not in seg_merged:
                seg_merged[seg_label] = {"mentions": 0, "sent_sum": 0.0, "count": 0, "communities": []}
            seg_merged[seg_label]["mentions"] += mentions
            seg_merged[seg_label]["sent_sum"] += sent
            seg_merged[seg_label]["count"] += 1
            seg_merged[seg_label]["communities"].append(cname)

            # 지역 세그먼트 (맘카페 기반)
            region = COMM_TO_REGION.get(cid)
            if region and mentions > 0:
                if region not in region_merged:
                    region_merged[region] = {"mentions": 0, "sent_sum": 0.0, "count": 0, "communities": []}
                region_merged[region]["mentions"] += mentions
                region_merged[region]["sent_sum"] += sent
                region_merged[region]["count"] += 1
                region_merged[region]["communities"].append(cname)

        # 연령 세그먼트 추가
        for seg_label, v in sorted(seg_merged.items(), key=lambda x: -x[1]["mentions"]):
            avg_sent = v["sent_sum"] / v["count"] if v["count"] > 0 else 0
            tone = "긍정" if avg_sent > 0.1 else "부정" if avg_sent < -0.1 else "혼합"
            reaction = "높음" if v["mentions"] >= 10 else "보통" if v["mentions"] >= 3 else "낮음"
            segments.append({
                "label": seg_label, "type": "연령",
                "reaction": reaction, "tone": tone,
                "mentions": v["mentions"], "communities": v["communities"][:3],
            })

        # 지역 세그먼트 추가 (맘카페 실데이터)
        for region, v in sorted(region_merged.items(), key=lambda x: -x[1]["mentions"]):
            avg_sent = v["sent_sum"] / v["count"] if v["count"] > 0 else 0
            tone = "긍정" if avg_sent > 0.1 else "부정" if avg_sent < -0.1 else "혼합"
            reaction = "높음" if v["mentions"] >= 5 else "보통" if v["mentions"] >= 2 else "낮음"
            segments.append({
                "label": region, "type": "지역",
                "reaction": reaction, "tone": tone,
                "mentions": v["mentions"], "communities": v["communities"][:2],
            })

        # 커뮤니티 데이터가 없으면 이슈명 키워드 + 감성 기반 폴백
        if not segments:
            name_lower = name.lower()
            tone_fb = "긍정" if sentiment > 20 else "부정" if sentiment < -20 else "혼합"

            matched = False
            if any(kw in name_lower for kw in ["청년", "취업", "대학", "mz", "20대", "30대", "인구유출", "sns", "캠퍼스", "등록금"]):
                segments.append({"label": "2030", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["경제", "산업", "민생", "공약", "일자리", "부동산", "분양", "추경", "예산", "지원금", "교육"]):
                segments.append({"label": "4050", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["복지", "안전", "의료", "노인", "경로", "도정", "성과", "축제"]):
                segments.append({"label": "60+", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["방산", "kf-21", "kf21", "조선", "항공", "로봇", "한화"]):
                segments.append({"label": "방산종사자", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["창원", "마산", "진해"]):
                segments.append({"label": "창원", "type": "지역", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["김해"]):
                segments.append({"label": "김해", "type": "지역", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["진주", "사천", "고성", "서부"]):
                segments.append({"label": "서부권", "type": "지역", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["공천", "당내", "국힘", "민주당", "정당", "내홍"]):
                segments.append({"label": "정치관심층", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})
                matched = True
            if any(kw in name_lower for kw in ["성추행", "비리", "부패", "논란", "의혹"]):
                segments.append({"label": "전체", "type": "연령", "reaction": "추정", "tone": "부정", "mentions": 0, "communities": []})
                matched = True
            if not matched:
                segments.append({"label": "전체", "type": "연령", "reaction": "추정", "tone": tone_fb, "mentions": 0, "communities": []})

        # AI 시민 의견 (본문 분석 결과)
        ai_opinions = cr.get("sources", {}).get("community", {}).get("ai_opinions", [])

        items.append({
            "name": name,
            "count": count,
            "comments": comments,
            "reaction_score": reaction_score,
            "side": c.get("side", "중립"),
            "sentiment": sentiment,
            "community_expected": c.get("community_expected", "중립"),
            "tip": c.get("tip", ""),
            "segments": segments,
            "opinions": ai_opinions[:3],
        })

    # 커스텀 키워드 반응 추가 (cluster_reaction.details에서)
    cluster_names = {c.get("name", "") for c in clusters[:10]}
    for det in snap.get("cluster_reaction", {}).get("details", []):
        kw = det.get("keyword", "")
        if kw in cluster_names:
            continue  # 이미 클러스터로 포함됨
        if det.get("side") == "커스텀":
            sources = det.get("sources", {})
            comm = sources.get("community", {})
            total_mentions = (sources.get("blog", {}).get("count", 0) +
                            sources.get("cafe", {}).get("count", 0) +
                            comm.get("mentions", 0))
            avg_sent = sum(s.get("net_sentiment", 0) for s in sources.values() if isinstance(s, dict)) / max(len(sources), 1)

            segments = []
            for cb in comm.get("breakdown", []):
                demo = cb.get("demographic", "전체")
                segments.append({
                    "label": demo, "type": "연령",
                    "reaction": "높음" if cb.get("mentions", 0) >= 10 else "보통" if cb.get("mentions", 0) >= 3 else "낮음",
                    "tone": "긍정" if cb.get("sentiment", 0) > 0.1 else "부정" if cb.get("sentiment", 0) < -0.1 else "혼합",
                    "mentions": cb.get("mentions", 0),
                    "communities": [cb.get("name", "")],
                })
            if not segments:
                segments.append({"label": "전체", "reaction": "추정", "tone": "혼합", "mentions": 0, "communities": []})

            items.append({
                "name": kw,
                "count": 0,
                "comments": 0,
                "reaction_score": total_mentions,
                "side": "커스텀",
                "sentiment": round(avg_sent * 100),
                "community_expected": "혼합",
                "tip": "",
                "segments": segments,
                "is_custom": True,
            })

    items.sort(key=lambda x: x["reaction_score"], reverse=True)

    return {
        "items": items,
        "total": len(items),
        "total_comments": sum(i["comments"] for i in items),
        "total_articles": sum(i["count"] for i in items),
    }
