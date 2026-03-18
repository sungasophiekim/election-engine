#!/usr/bin/env python3
"""
Election Engine Phase 1 — 통합 실데이터 테스트
네이버 뉴스 API + 정규화된 스코어링 + 이슈→지역 연동 + DB 저장

사용법:
  python3 -m scripts.test_real_data
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
from models.schemas import IssueScore, CrisisLevel
from engines.issue_scoring import calculate_issue_score
from engines.voter_and_opponent import (
    calculate_voter_priorities,
    analyze_opponents,
    _days_until_election,
)
from collectors.naver_news import (
    collect_issue_signals,
    collect_opponent_data,
)
from storage.database import ElectionDB


def main():
    config = SAMPLE_GYEONGNAM_CONFIG
    days_left = _days_until_election(config.election_date)

    print("╔" + "═" * 58 + "╗")
    print("║  Election Engine v2 — Phase 1 통합 테스트               ║")
    print("╚" + "═" * 58 + "╝")
    print(f"\n후보: {config.candidate_name} ({config.region} {config.election_type})")
    print(f"선거일: {config.election_date} (D-{days_left})")
    print(f"상대: {', '.join(config.opponents)}")

    # DB 초기화
    db = ElectionDB()
    print(f"DB: {db._db_path}")

    # ── Step 1: 이슈 수집 + 스코어링 ────────────────────────────
    print("\n" + "─" * 60)
    print(" Step 1: 이슈 수집 + 스코어링 (정규화 v2)")
    print("─" * 60)

    issue_keywords = [
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
    ]

    signals = collect_issue_signals(
        issue_keywords,
        candidate_name=config.candidate_name,
        opponents=config.opponents,
    )

    if not signals:
        print("\n  이슈 시그널 수집 실패. .env 네이버 API 키 확인 필요.")
        db.close()
        return

    issue_scores = []
    for sig in signals:
        score = calculate_issue_score(sig, config)
        issue_scores.append(score)

    issue_scores.sort(key=lambda x: x.score, reverse=True)

    # 저장
    db.save_issue_scores(issue_scores, signals)

    level_emoji = {
        CrisisLevel.NORMAL: "🟢", CrisisLevel.WATCH: "🟡",
        CrisisLevel.ALERT: "🟠", CrisisLevel.CRISIS: "🔴",
    }

    print(f"\n수집 {len(signals)}건 → 스코어링 완료\n")
    print(f"  {'이슈':<20} {'스코어':>6} {'레벨':<8} {'24h':>4} {'부정':>5} {'속도':>5} {'플래그'}")
    print(f"  {'─'*20} {'─'*6} {'─'*8} {'─'*4} {'─'*5} {'─'*5} {'─'*12}")

    for sc, sig in sorted(
        zip(issue_scores, signals),
        key=lambda x: x[0].score, reverse=True
    ):
        # match score to signal by keyword
        matched_sig = next((s for s in signals if s.keyword == sc.keyword), sig)
        emoji = level_emoji.get(sc.level, "⚪")
        flags = ""
        if matched_sig.candidate_linked: flags += "👤"
        if matched_sig.tv_reported: flags += "📺"
        if matched_sig.portal_trending: flags += "🔥"
        print(f"  {emoji} {sc.keyword:<18} {sc.score:>5.1f}  {sc.level.name:<8}"
              f" {matched_sig.mention_count:>3}건 {matched_sig.negative_ratio:>4.0%}"
              f"  {matched_sig.velocity:>4.1f}x {flags}")

    # ── Step 2: 지역 우선순위 (이슈 연동) ──────────────────────
    print("\n" + "─" * 60)
    print(" Step 2: 지역 우선순위 (이슈 데이터 연동)")
    print("─" * 60)

    # 이슈 없이 vs 이슈 연동 비교
    segments_without = calculate_voter_priorities(config)
    segments_with = calculate_voter_priorities(config, issue_scores)

    # 저장
    db.save_voter_priorities(segments_with)

    rank_without = {s.region: i for i, s in enumerate(segments_without, 1)}

    print(f"\n  {'지역':<6} {'우선순위':>7} {'이슈열기':>7} {'경합도':>5} {'순위변동':>7}")
    print(f"  {'─'*6} {'─'*7} {'─'*7} {'─'*5} {'─'*7}")

    for i, s in enumerate(segments_with, 1):
        old_rank = rank_without.get(s.region, i)
        change = old_rank - i
        if change > 0:
            arrow = f"↑{change}"
        elif change < 0:
            arrow = f"↓{abs(change)}"
        else:
            arrow = "─"
        bar = "█" * int(s.priority_score * 20)
        print(f"  {i}. {s.region:<5} {s.priority_score:.3f}  "
              f" {s.local_issue_heat:.2f}   {s.swing_index:.0%}    {arrow:>4}  {bar}")

    # ── Step 3: 상대 후보 분석 ──────────────────────────────────
    print("\n" + "─" * 60)
    print(" Step 3: 상대 후보 실시간 분석")
    print("─" * 60)

    opponent_data = collect_opponent_data(config.opponents, region=config.region)

    for opp in opponent_data:
        print(f"\n  {opp['name']}: 24h 뉴스 {opp['recent_mentions']}건")
        if opp.get("message_shift"):
            print(f"    메시지: {opp['message_shift']}")
        # 감성 분석 결과 표시
        if opp.get("sentiment"):
            sent = opp["sentiment"]
            net = sent.get("net_sentiment", 0)
            net_label = "긍정" if net > 0.1 else ("부정" if net < -0.1 else "중립")
            print(f"    감성: {net_label} ({net:+.2f})"
                  f"  | 부정뉴스 {sent.get('about_us_negative', 0)}건"
                  f"  긍정뉴스 {sent.get('about_us_positive', 0)}건")
        if opp.get("articles_sample"):
            print("    최근 기사:")
            for art in opp["articles_sample"][:3]:
                print(f"      · {art['title'][:55]}")

    # ── Step 4: 공격 확률 분석 ──────────────────────────────────
    print("\n" + "─" * 60)
    print(" Step 4: 72시간 공격 확률")
    print("─" * 60)

    opponent_signals = analyze_opponents(config, opponent_data, issue_scores)

    # 저장
    db.save_opponent_signals(opponent_signals)

    for sig in opponent_signals:
        prob_pct = sig.attack_prob_72h * 100
        bar = "█" * int(sig.attack_prob_72h * 20)
        if prob_pct >= 70:
            color = "🔴"
        elif prob_pct >= 40:
            color = "🟡"
        else:
            color = "🟢"
        print(f"\n  {color} {sig.opponent_name}")
        print(f"     공격 확률: {prob_pct:.0f}% {bar}")
        print(f"     24h 뉴스: {sig.recent_mentions}건")
        print(f"     메시지: {sig.message_shift}")
        print(f"     → {sig.recommended_action}")

    # ── 종합 판단 ───────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(" 선대위 보고 요약")
    print("═" * 60)

    # 최고 위험 이슈 (WATCH 이상만)
    real_issues = [s for s in issue_scores if s.level != CrisisLevel.NORMAL]
    if real_issues:
        print(f"\n  주의 이슈 {len(real_issues)}건:")
        for iss in real_issues[:3]:
            print(f"    {level_emoji[iss.level]} {iss.keyword}: {iss.score:.1f}점")
    else:
        print(f"\n  🟢 특이 이슈 없음")

    # 최우선 지역
    top3 = segments_with[:3]
    print(f"\n  오늘 유세 추천:")
    for i, s in enumerate(top3, 1):
        print(f"    {i}. {s.region} (우선순위 {s.priority_score:.3f},"
              f" 이슈열기 {s.local_issue_heat:.2f})")

    # 상대 후보
    high_risk = [s for s in opponent_signals if s.attack_prob_72h >= 0.4]
    if high_risk:
        print(f"\n  경계 후보:")
        for s in high_risk:
            print(f"    ⚠ {s.opponent_name}: 공격확률 {s.attack_prob_72h*100:.0f}%")
    else:
        print(f"\n  상대 후보 특이 동향 없음")

    # DB 이력 확인
    print(f"\n  [DB] 이슈 {len(issue_scores)}건, 지역 {len(segments_with)}건,"
          f" 상대 {len(opponent_signals)}건 저장 완료")

    db.close()
    print("\n" + "═" * 60)


if __name__ == "__main__":
    main()
