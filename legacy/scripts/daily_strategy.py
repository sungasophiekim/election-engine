#!/usr/bin/env python3
"""
Election Engine — 일일 전략 산출
전체 엔진 통합 실행: 데이터 수집 → 분석 → 전략 산출 → DB 저장

사용법:
  python3 -m scripts.daily_strategy
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
from engines.issue_scoring import calculate_issue_score
from engines.voter_and_opponent import (
    calculate_voter_priorities,
    analyze_opponents,
    _days_until_election,
)
from engines.polling_tracker import PollingTracker
from engines.pledge_comparator import PledgeComparator
from engines.strategy_synthesizer import StrategySynthesizer
from collectors.naver_news import collect_issue_signals, collect_opponent_data
from storage.database import ElectionDB


def main():
    config = SAMPLE_GYEONGNAM_CONFIG
    days_left = _days_until_election(config.election_date)

    print("╔" + "═" * 58 + "╗")
    print("║  Election Engine — 일일 전략 브리핑                      ║")
    print("╚" + "═" * 58 + "╝")
    print(f"  {config.candidate_name} | {config.region} {config.election_type} | D-{days_left}")
    print()

    # ── 1. 데이터 수집 ──────────────────────────────────────────
    print("  [1/6] 네이버 뉴스 수집 중...")

    issue_keywords = [
        "경남도지사 선거", "경남도지사 공약",
        f"{config.candidate_name} 경남", "김경수 경남",
        "경남 조선업 일자리", "경남 교통 BRT",
        "경남 청년 정책", "부울경 행정통합",
        "경남 우주항공", "창원 특례시",
    ]

    signals = collect_issue_signals(
        issue_keywords,
        candidate_name=config.candidate_name,
        opponents=config.opponents,
    )

    if not signals:
        print("  ⚠ 뉴스 수집 실패. API 키를 확인하세요.")
        return

    # ── 2. Engine 1: 이슈 스코어링 ──────────────────────────────
    print(f"  [2/6] 이슈 스코어링... ({len(signals)}건)")

    issue_scores = []
    for sig in signals:
        score = calculate_issue_score(sig, config)
        issue_scores.append(score)
    issue_scores.sort(key=lambda x: x.score, reverse=True)

    # ── 3. Engine 3+4: 지역 + 상대 분석 ────────────────────────
    print("  [3/6] 지역 우선순위 + 상대 후보 분석...")

    voter_segments = calculate_voter_priorities(config, issue_scores)

    opponent_data = collect_opponent_data(config.opponents, region=config.region)
    opponent_signals = analyze_opponents(config, opponent_data, issue_scores)

    # ── 4. Engine 5: 여론조사 ───────────────────────────────────
    print("  [4/6] 여론조사 분석...")

    polling = PollingTracker(config)
    polling_result = polling.calculate_win_probability()
    polling_trend = polling.calculate_trend()

    # ── 5. Engine 6: 공약 대비 ──────────────────────────────────
    print("  [5/6] 공약 대비표 생성...")

    comparator = PledgeComparator(config)
    attack_points = comparator.find_attack_points("김경수")
    defense_points = comparator.find_defense_points()

    # ── 6. Engine 7: 전략 종합 ──────────────────────────────────
    print("  [6/6] 전략 종합...")

    synthesizer = StrategySynthesizer(config)
    strategy = synthesizer.synthesize(
        issue_scores=issue_scores,
        opponent_signals=opponent_signals,
        voter_segments=voter_segments,
        polling_data=polling_result,
        attack_points=attack_points,
        defense_points=defense_points,
    )

    # ── DB 저장 ─────────────────────────────────────────────────
    db = ElectionDB()
    db.save_issue_scores(issue_scores, signals)
    db.save_voter_priorities(voter_segments)
    db.save_opponent_signals(opponent_signals)
    db.close()

    # ── 출력 ────────────────────────────────────────────────────
    print("\n")
    print(synthesizer.format_strategy_report(strategy))

    # ── 부록: 여론조사 요약 ─────────────────────────────────────
    print("\n" + "─" * 60)
    print(" 부록 A: 여론조사 현황")
    print("─" * 60)
    print(f"  승률: {polling_result['win_prob']*100:.1f}%"
          f"  (우리 {polling_result['our_avg']:.1f}%"
          f" vs 김경수 {polling_result['opponent_avg'].get('김경수', 0):.1f}%)")
    print(f"  추세: {polling_trend['momentum']}"
          f"  ({polling_trend['our_trend']:+.2f}%p/일)")
    print(f"  판단: {polling_result['assessment']}")

    # ── 부록: 이슈 상세 ────────────────────────────────────────
    print("\n" + "─" * 60)
    print(" 부록 B: 이슈 스코어 상세")
    print("─" * 60)
    from models.schemas import CrisisLevel
    level_emoji = {
        CrisisLevel.NORMAL: "🟢", CrisisLevel.WATCH: "🟡",
        CrisisLevel.ALERT: "🟠", CrisisLevel.CRISIS: "🔴",
    }
    for sc in issue_scores:
        sig = next((s for s in signals if s.keyword == sc.keyword), None)
        emoji = level_emoji.get(sc.level, "⚪")
        mc = sig.mention_count if sig else 0
        print(f"  {emoji} {sc.score:5.1f} | {sc.keyword:<20} | 24h {mc:>3}건"
              f" | {sc.level.name}")

    # ── 부록: 공격 포인트 ──────────────────────────────────────
    print("\n" + "─" * 60)
    print(" 부록 C: 김경수 공격 포인트")
    print("─" * 60)
    for ap in attack_points[:5]:
        sev = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(ap["severity"], "⚪")
        print(f"  {sev} [{ap['attack_angle']}] {ap['pledge']}")
        print(f"     → {ap['talking_point']}")

    print("\n  [전체 데이터 DB 저장 완료]")


if __name__ == "__main__":
    main()
