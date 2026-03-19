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

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🗳 *Election Engine 전략 봇*\n\n"
        f"캠프 전략 AI 에이전트입니다.\n"
        f"채팅 ID: `{chat_id}`\n\n"
        f"*명령어:*\n"
        f"/분석 키워드 — AI 감성 분석\n"
        f"/전략 — 오늘의 전략 브리핑\n"
        f"/이슈 — 이슈 스코어 요약\n"
        f"/여론 — 여론조사 현황\n"
        f"/상대 — 상대 후보 동향\n"
        f"/도움 — 명령어 목록",
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
        from storage.database import ElectionDB
        db = ElectionDB()
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

        from storage.database import ElectionDB
        db = ElectionDB()
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
        from storage.database import ElectionDB
        db = ElectionDB()
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
        from storage.database import ElectionDB
        db = ElectionDB()
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


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 미설정")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("도움", cmd_help))
    app.add_handler(CommandHandler("분석", cmd_analyze))
    app.add_handler(CommandHandler("전략", cmd_strategy))
    app.add_handler(CommandHandler("이슈", cmd_issues))
    app.add_handler(CommandHandler("여론", cmd_polling))
    app.add_handler(CommandHandler("상대", cmd_opponent))

    print("🤖 텔레그램 전략 봇 시작...")
    print(f"   명령어: /start /분석 /전략 /이슈 /여론 /상대")
    app.run_polling()


if __name__ == "__main__":
    main()
