"""
Election Engine — 텔레그램 전략 봇
선대위 전용 채널에서 AI 전략 에이전트를 제어합니다.

명령어:
  /start — 봇 시작 + 사용법
  /분석 [키워드] — AI 감성 분석 (하루 3회)
  /전략 — 오늘의 전략 브리핑
  /이슈 — 현재 이슈 스코어 요약
  /여론 — 여론조사 현황
  /상대 — 상대 후보 동향
  /도움 — 명령어 목록

  v5 학습 루프:
  /decisions — 오늘 추천 요약
  /approve N — N번 추천 실행 완료
  /override N 값 사유 — N번 추천 수정
  /skip N — N번 추천 건너뜀
  /evaluate — 평가 대기 목록
  /grade N 등급 — N번 결정 수동 평가
  /accuracy — 7일 정확도 리포트

실행:
  python3 -m telegram_bot.bot
"""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 허용된 채팅 ID (설정 안 하면 누구나 사용 가능)
ALLOWED_CHATS = os.getenv("TELEGRAM_ALLOWED_CHATS", "").split(",")
ALLOWED_CHATS = [c.strip() for c in ALLOWED_CHATS if c.strip()]


def _check_access(update: Update) -> bool:
    if not ALLOWED_CHATS:
        return True
    chat_id = str(update.effective_chat.id)
    return chat_id in ALLOWED_CHATS


def _get_db():
    from storage.database import ElectionDB
    return ElectionDB()


# ── 기본 타입 한글 매핑 ─────────────────────────────────────────
_TYPE_KO = {
    "issue_stance": "이슈입장",
    "campaign_mode": "캠페인모드",
    "region_priority": "지역우선순위",
    "opponent_action": "상대대응",
    "leading_index": "선행지수",
}

_GRADE_EMOJI = {
    "correct": "🟢 적중",
    "partially_correct": "🟡 부분적중",
    "wrong": "🔴 오류",
    "inconclusive": "⚪ 판단불가",
}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🗳 *Election Engine 전략 봇*\n\n"
        f"캠프 전략 AI 에이전트입니다.\n"
        f"채팅 ID: `{chat_id}`\n\n"
        f"*기본 명령어:*\n"
        f"/analyze 키워드 — AI 감성 분석 (하루 3회)\n"
        f"/strategy — 오늘의 전략 브리핑\n"
        f"/issues — 이슈 스코어 요약\n"
        f"/poll — 여론조사 현황\n"
        f"/opponent — 상대 후보 동향\n\n"
        f"*학습 루프:*\n"
        f"/decisions — 오늘 추천 목록\n"
        f"/approve N — N번 실행 완료\n"
        f"/override N 값 사유 — N번 수정\n"
        f"/skip N — N번 건너뜀\n"
        f"/evaluate — 평가 대기 목록\n"
        f"/grade N 등급 — N번 수동 평가\n"
        f"/accuracy — 정확도 리포트\n\n"
        f"단축: /a /s /i /p /o /d /acc",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    keyword = " ".join(context.args) if context.args else ""
    if not keyword:
        await update.message.reply_text("사용법: /분석 경남도지사")
        return

    await update.message.reply_text(f"🤖 '{keyword}' 분석 중...")

    try:
        db = _get_db()
        today_count = db.count_ai_today()
        if today_count >= 3:
            db.close()
            await update.message.reply_text(f"⚠ 오늘 분석 3회 한도 초과 (사용: {today_count}회)")
            return

        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from collectors.naver_news import search_news
        config = SAMPLE_GYEONGNAM_CONFIG

        articles = search_news(keyword, display=100)
        titles = [a["title"] for a in articles[:15]]

        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        prompt = f"""당신은 '{config.candidate_name}' 후보 캠프의 수석 전략 참모입니다.
슬로건: {config.slogan}
상대: {', '.join(config.opponents)}

"{keyword}" 최근 뉴스:
{chr(10).join(f'{i+1}. {t}' for i,t in enumerate(titles))}

캠프 전략가 관점에서 분석하세요. JSON으로만 응답:
{{"sentiment":"긍정/부정/중립/혼재","score":-1.0~1.0,"summary":"2문장 요약","risk":"위험요소","opportunity":"기회","action":"지금 해야 할 것"}}"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        result = json.loads(raw)

        db.save_ai_analysis("telegram_sentiment", keyword,
                           json.dumps({"titles": titles}, ensure_ascii=False),
                           json.dumps(result, ensure_ascii=False),
                           "telegram")
        remaining = 3 - today_count - 1
        db.close()

        score = result.get("score", 0)
        emoji = "🟢" if score > 0.2 else ("🔴" if score < -0.2 else "🟡")

        msg = (
            f"{emoji} *{keyword}* — {result.get('sentiment', '')} ({score:+.2f})\n\n"
            f"📋 {result.get('summary', '')}\n\n"
            f"⚠ 위험: {result.get('risk', '')}\n"
            f"✅ 기회: {result.get('opportunity', '')}\n"
            f"➡ 행동: {result.get('action', '')}\n\n"
            f"_남은 분석 횟수: {remaining}/3_"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ 분석 실패: {str(e)[:100]}")


async def cmd_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    try:
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from engines.polling_tracker import PollingTracker
        from engines.voter_and_opponent import _days_until_election
        config = SAMPLE_GYEONGNAM_CONFIG

        days = _days_until_election(config.election_date)
        polling = PollingTracker(config)
        wp = polling.calculate_win_probability()
        trend = polling.calculate_trend()

        db = _get_db()
        scores = db.get_latest_scores()
        db.close()

        crisis = sum(1 for s in scores if (s.get("crisis_level") or "").upper() == "CRISIS")
        alert = sum(1 for s in scores if (s.get("crisis_level") or "").upper() == "ALERT")

        gap = wp.get("gap", 0)
        if gap < -2:
            mode = "🔴 공격"
        elif gap > 3:
            mode = "🟢 수비"
        else:
            mode = "🟡 선점"

        msg = (
            f"📊 *{config.candidate_name} 전략 브리핑*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📅 D-{days} | 모드: {mode}\n\n"
            f"*승률:* {wp.get('win_prob', 0)*100:.1f}% ({gap:+.1f}%p)\n"
            f"*추세:* {trend.get('momentum', '-')} ({trend.get('our_trend', 0):+.2f}%p/일)\n"
            f"*평가:* {wp.get('assessment', '')}\n\n"
            f"*이슈:* 위기 {crisis}건 / 경계 {alert}건\n"
            f"*슬로건:* {config.slogan}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    try:
        db = _get_db()
        scores = db.get_latest_scores()
        db.close()

        if not scores:
            await update.message.reply_text("데이터 없음 — 대시보드에서 전략 갱신을 먼저 하세요")
            return

        level_emoji = {"CRISIS": "🔴", "ALERT": "🟠", "WATCH": "🟡", "NORMAL": "🟢"}
        msg = "📰 *이슈 스코어*\n━━━━━━━━━━━━━━━\n"
        for s in scores[:10]:
            lv = (s.get("crisis_level") or "NORMAL").upper()
            emoji = level_emoji.get(lv, "⚪")
            msg += f"{emoji} {s.get('score', 0):.1f} | {s.get('keyword', '')}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_polling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    try:
        from config.tenant_config import SAMPLE_GYEONGNAM_CONFIG
        from engines.polling_tracker import PollingTracker
        config = SAMPLE_GYEONGNAM_CONFIG

        pt = PollingTracker(config)
        wp = pt.calculate_win_probability()

        msg = "📈 *여론조사 현황*\n━━━━━━━━━━━━━━━\n"
        for p in pt.polls[-5:]:
            opp = list(p.opponent_support.values())[0] if p.opponent_support else 0
            msg += f"`{p.poll_date[5:]}` {p.pollster[:8]:8s} {p.our_support:.1f}% vs {opp:.1f}%\n"

        msg += f"\n*승률:* {wp.get('win_prob', 0)*100:.1f}% (격차 {wp.get('gap', 0):+.1f}%p)"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    try:
        db = _get_db()
        rows = db._conn.execute(
            "SELECT * FROM opponent_signals ORDER BY recorded_at DESC LIMIT 5"
        ).fetchall()
        db.close()

        if not rows:
            await update.message.reply_text("상대 후보 데이터 없음 — 전략 갱신 필요")
            return

        msg = "👥 *상대 후보 동향*\n━━━━━━━━━━━━━━━\n"
        for r in rows:
            r = dict(r)
            prob = r.get("attack_prob", 0) * 100
            emoji = "🔴" if prob >= 70 else ("🟡" if prob >= 40 else "🟢")
            msg += f"{emoji} *{r.get('opponent_name', '')}* 공격확률 {prob:.0f}%\n"
            if r.get("message_shift"):
                msg += f"   _{r['message_shift']}_\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


# ══════════════════════════════════════════════════════════════════
# V5 학습 루프 명령어
# ══════════════════════════════════════════════════════════════════

async def cmd_decisions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """오늘의 추천 목록 — 인라인 버튼 포함"""
    if not _check_access(update):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    try:
        db = _get_db()
        rows = db._conn.execute(
            """SELECT * FROM decision_log
               WHERE created_at >= datetime('now', '-24 hours')
               ORDER BY created_at DESC""",
        ).fetchall()
        db.close()

        if not rows:
            await update.message.reply_text("📋 오늘 추천 기록이 없습니다. 대시보드에서 전략 갱신을 먼저 하세요.")
            return

        msg = "🧠 *오늘의 추천 목록*\n━━━━━━━━━━━━━━━\n"
        for idx, r in enumerate(rows):
            r = dict(r)
            type_ko = _TYPE_KO.get(r.get("decision_type", ""), r.get("decision_type", ""))
            kw = r.get("keyword") or r.get("region") or ""
            val = r.get("recommended_value", "")
            override = r.get("override_value")
            executed = r.get("was_executed")

            # 상태 이모지
            if override:
                status = "✏️"
            elif executed is not None and executed:
                status = "✅"
            elif executed is not None and not executed:
                status = "⏭"
            else:
                status = "⏳"

            line = f"{status} `{idx+1}` *{type_ko}*"
            if kw:
                line += f" [{kw}]"
            line += f": `{val}`"
            if override:
                line += f" → `{override}`"
            msg += line + "\n"

        msg += (
            f"\n_총 {len(rows)}건_\n\n"
            f"*액션:*\n"
            f"`/approve N` — 실행 완료\n"
            f"`/skip N` — 건너뜀\n"
            f"`/override N 값 사유` — 수정"
        )

        # 인라인 버튼 (상위 3건에 대해)
        buttons = []
        for idx, r in enumerate(rows[:3]):
            r = dict(r)
            if r.get("was_executed") is None and not r.get("override_value"):
                did = r["decision_id"]
                buttons.append([
                    InlineKeyboardButton(f"✅ {idx+1}번 실행", callback_data=f"lrn_approve:{did}"),
                    InlineKeyboardButton(f"⏭ {idx+1}번 스킵", callback_data=f"lrn_skip:{did}"),
                ])

        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """N번 추천 실행 완료"""
    if not _check_access(update):
        return
    await _execute_by_index(update, context, was_executed=True)


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """N번 추천 건너뜀"""
    if not _check_access(update):
        return
    await _execute_by_index(update, context, was_executed=False)


async def _execute_by_index(update: Update, context: ContextTypes.DEFAULT_TYPE, was_executed: bool):
    if not context.args:
        await update.message.reply_text("사용법: /approve 1 또는 /skip 1")
        return

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("번호를 입력해주세요: /approve 1")
        return

    try:
        db = _get_db()
        rows = db._conn.execute(
            """SELECT decision_id FROM decision_log
               WHERE created_at >= datetime('now', '-24 hours')
               ORDER BY created_at DESC""",
        ).fetchall()

        if idx < 0 or idx >= len(rows):
            db.close()
            await update.message.reply_text(f"⚠ {idx+1}번 추천이 없습니다. (총 {len(rows)}건)")
            return

        decision_id = rows[idx]["decision_id"]
        from engines.decision_logger import log_execution
        exec_rec = log_execution(decision_id, was_executed, "텔레그램")
        db.save_execution(exec_rec)
        db.close()

        emoji = "✅" if was_executed else "⏭"
        action = "실행 완료" if was_executed else "건너뜀"
        await update.message.reply_text(f"{emoji} {idx+1}번 추천: {action}")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_override(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """N번 추천 수정: /override 1 counter 부정여론급등"""
    if not _check_access(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text("사용법: /override 1 counter 사유(선택)")
        return

    try:
        idx = int(context.args[0]) - 1
        new_value = context.args[1]
        reason = " ".join(context.args[2:]) if len(context.args) > 2 else "텔레그램 수정"
    except ValueError:
        await update.message.reply_text("사용법: /override 1 counter 사유")
        return

    try:
        db = _get_db()
        rows = db._conn.execute(
            """SELECT decision_id, recommended_value FROM decision_log
               WHERE created_at >= datetime('now', '-24 hours')
               ORDER BY created_at DESC""",
        ).fetchall()

        if idx < 0 or idx >= len(rows):
            db.close()
            await update.message.reply_text(f"⚠ {idx+1}번 추천이 없습니다.")
            return

        row = dict(rows[idx])
        from engines.decision_logger import log_override
        override = log_override(
            row["decision_id"],
            row["recommended_value"],
            new_value,
            reason,
            "텔레그램",
        )
        db.save_override(override)
        db.close()

        await update.message.reply_text(
            f"✏️ {idx+1}번 수정: `{row['recommended_value']}` → `{new_value}`\n"
            f"사유: {reason}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_evaluate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """평가 대기 목록"""
    if not _check_access(update):
        return

    try:
        db = _get_db()
        pending = db.get_pending_decisions(hours_ago=24)
        db.close()

        if not pending:
            await update.message.reply_text("📋 평가 대기 건이 없습니다.")
            return

        msg = "📊 *평가 대기 목록*\n━━━━━━━━━━━━━━━\n"
        buttons = []
        for idx, d in enumerate(pending[:10]):
            type_ko = _TYPE_KO.get(d.get("decision_type", ""), d.get("decision_type", ""))
            kw = d.get("keyword") or ""
            val = d.get("recommended_value", "")
            override = d.get("override_value")

            line = f"`{idx+1}` *{type_ko}*"
            if kw:
                line += f" [{kw}]"
            line += f": `{val}`"
            if override:
                line += f" → `{override}`"
            msg += line + "\n"

            # 상위 3건에 인라인 버튼
            if idx < 3:
                did = d["decision_id"]
                buttons.append([
                    InlineKeyboardButton("🟢적중", callback_data=f"lrn_grade:{did}:correct"),
                    InlineKeyboardButton("🟡부분", callback_data=f"lrn_grade:{did}:partially_correct"),
                    InlineKeyboardButton("🔴오류", callback_data=f"lrn_grade:{did}:wrong"),
                    InlineKeyboardButton("⚪불가", callback_data=f"lrn_grade:{did}:inconclusive"),
                ])

        msg += f"\n_총 {len(pending)}건_\n`/grade N 등급` (correct/wrong/partial)"

        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """수동 평가: /grade 1 correct"""
    if not _check_access(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "사용법: /grade 1 correct\n"
            "등급: correct, partial, wrong, inconclusive"
        )
        return

    try:
        idx = int(context.args[0]) - 1
        grade_input = context.args[1].lower()
    except ValueError:
        await update.message.reply_text("사용법: /grade 1 correct")
        return

    # 약칭 매핑
    grade_map = {
        "correct": "correct", "c": "correct",
        "partial": "partially_correct", "p": "partially_correct",
        "wrong": "wrong", "w": "wrong",
        "inconclusive": "inconclusive", "i": "inconclusive",
    }
    grade = grade_map.get(grade_input)
    if not grade:
        await update.message.reply_text(f"⚠ 알 수 없는 등급: {grade_input}\n사용: correct, partial, wrong, inconclusive")
        return

    try:
        db = _get_db()
        pending = db.get_pending_decisions(hours_ago=24)

        if idx < 0 or idx >= len(pending):
            db.close()
            await update.message.reply_text(f"⚠ {idx+1}번이 없습니다. (총 {len(pending)}건)")
            return

        d = pending[idx]
        from engines.outcome_evaluator import OutcomeRecord
        outcome = OutcomeRecord(
            decision_id=d["decision_id"],
            decision_type=d.get("decision_type", ""),
            keyword=d.get("keyword", ""),
            recommended_value=d.get("recommended_value", ""),
            actual_outcome="텔레그램 수동 평가",
            outcome_grade=grade,
        )
        db.save_outcomes([outcome])
        db.close()

        emoji = _GRADE_EMOJI.get(grade, grade)
        await update.message.reply_text(f"{emoji} {idx+1}번 평가 완료")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


async def cmd_accuracy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """7일 정확도 리포트"""
    if not _check_access(update):
        return

    try:
        db = _get_db()
        summary = db.get_accuracy_summary(days=7)
        override_stats = db.get_override_stats(days=7)
        db.close()

        if not summary:
            await update.message.reply_text("📊 아직 평가된 결정이 없습니다.")
            return

        # 전체 집계
        total = sum(r.get("total", 0) for r in summary)
        correct = sum(r.get("correct", 0) for r in summary)
        partial = sum(r.get("partial", 0) for r in summary)
        wrong = sum(r.get("wrong", 0) for r in summary)
        overall_rate = (correct + partial * 0.5) / total if total > 0 else 0

        gauge = "🟢" if overall_rate >= 0.7 else ("🟡" if overall_rate >= 0.4 else "🔴")

        msg = (
            f"📊 *엔진 정확도 리포트 (7일)*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{gauge} *전체: {overall_rate*100:.0f}%*\n"
            f"  적중 {correct} | 부분 {partial} | 오류 {wrong} | 총 {total}\n\n"
        )

        # 유형별
        for r in summary:
            type_ko = _TYPE_KO.get(r["decision_type"], r["decision_type"])
            rate = r.get("accuracy_rate", 0) if "accuracy_rate" in r else (
                (r.get("correct", 0) + r.get("partial", 0) * 0.5) / r.get("total", 1)
            )
            bar_len = int(rate * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            msg += f"  {type_ko}: `{bar}` {rate*100:.0f}%\n"

        # 오버라이드
        if override_stats:
            msg += "\n*오버라이드 패턴:*\n"
            for dtype, data in override_stats.items():
                type_ko = _TYPE_KO.get(dtype, dtype)
                rate = data.get("override_rate", 0) if "override_rate" in data else (
                    data.get("overridden", 0) / data.get("total", 1)
                )
                if rate > 0:
                    msg += f"  ⚠ {type_ko}: {data['overridden']}/{data['total']}건 수정 ({rate*100:.0f}%)\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 오류: {str(e)[:100]}")


# ── 인라인 버튼 콜백 핸들러 ─────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """인라인 버튼 클릭 처리"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data:
        return

    try:
        if data.startswith("lrn_approve:"):
            decision_id = data.split(":")[1]
            db = _get_db()
            from engines.decision_logger import log_execution
            db.save_execution(log_execution(decision_id, True, "텔레그램 버튼"))
            db.close()
            await query.edit_message_text(
                query.message.text + f"\n\n✅ 실행 완료 처리됨",
                parse_mode="Markdown",
            )

        elif data.startswith("lrn_skip:"):
            decision_id = data.split(":")[1]
            db = _get_db()
            from engines.decision_logger import log_execution
            db.save_execution(log_execution(decision_id, False, "텔레그램 버튼"))
            db.close()
            await query.edit_message_text(
                query.message.text + f"\n\n⏭ 건너뜀 처리됨",
                parse_mode="Markdown",
            )

        elif data.startswith("lrn_grade:"):
            parts = data.split(":")
            decision_id = parts[1]
            grade = parts[2]
            db = _get_db()
            row = db._conn.execute(
                "SELECT * FROM decision_log WHERE decision_id=?", (decision_id,)
            ).fetchone()
            if row:
                from engines.outcome_evaluator import OutcomeRecord
                outcome = OutcomeRecord(
                    decision_id=decision_id,
                    decision_type=dict(row).get("decision_type", ""),
                    keyword=dict(row).get("keyword", ""),
                    recommended_value=dict(row).get("recommended_value", ""),
                    actual_outcome="텔레그램 버튼 평가",
                    outcome_grade=grade,
                )
                db.save_outcomes([outcome])
            db.close()
            emoji = _GRADE_EMOJI.get(grade, grade)
            await query.edit_message_text(
                query.message.text + f"\n\n{emoji} 평가 완료",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.edit_message_text(
            query.message.text + f"\n\n❌ 오류: {str(e)[:80]}",
            parse_mode="Markdown",
        )


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 미설정")
        return

    app = Application.builder().token(TOKEN).build()

    # 기본 명령어
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("a", cmd_analyze))
    app.add_handler(CommandHandler("strategy", cmd_strategy))
    app.add_handler(CommandHandler("s", cmd_strategy))
    app.add_handler(CommandHandler("issues", cmd_issues))
    app.add_handler(CommandHandler("i", cmd_issues))
    app.add_handler(CommandHandler("poll", cmd_polling))
    app.add_handler(CommandHandler("p", cmd_polling))
    app.add_handler(CommandHandler("opponent", cmd_opponent))
    app.add_handler(CommandHandler("o", cmd_opponent))

    # v5 학습 루프 명령어
    app.add_handler(CommandHandler("decisions", cmd_decisions))
    app.add_handler(CommandHandler("d", cmd_decisions))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("override", cmd_override))
    app.add_handler(CommandHandler("evaluate", cmd_evaluate))
    app.add_handler(CommandHandler("grade", cmd_grade))
    app.add_handler(CommandHandler("accuracy", cmd_accuracy))
    app.add_handler(CommandHandler("acc", cmd_accuracy))

    # 인라인 버튼 콜백
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 텔레그램 전략 봇 시작...")
    print(f"   기본: /start /analyze /strategy /issues /poll /opponent")
    print(f"   학습: /decisions /approve /skip /override /evaluate /grade /accuracy")
    app.run_polling()


if __name__ == "__main__":
    main()
