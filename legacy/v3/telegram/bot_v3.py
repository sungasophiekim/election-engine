"""
Telegram Bot V3 — Strategy Director Interface
텔레그램을 통한 내부 시그널 입력 + AI 제안 승인/거부/수정
"""
from __future__ import annotations


import json
import logging
import os
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters,
)

from v3.storage import V3Storage
from v3.telegram.command_parser import CommandParser, ApprovalParser
from v3.models.signals import SignalType, InternalSignal
from v3.models.proposals import ProposalStatus

logger = logging.getLogger(__name__)


class StrategyBot:
    """전략실장 텔레그램 봇."""

    def __init__(self, storage: V3Storage, ai_classifier=None):
        self.storage = storage
        self.cmd_parser = CommandParser()
        self.approval_parser = ApprovalParser()
        self.ai_classifier = ai_classifier  # 자연어 분류기 (Optional)

        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_chats = set()
        allowed = os.getenv("TELEGRAM_ALLOWED_CHATS", "")
        if allowed:
            self.allowed_chats = {int(c.strip()) for c in allowed.split(",") if c.strip()}

    def _check_access(self, chat_id: int) -> bool:
        if not self.allowed_chats:
            return True
        return chat_id in self.allowed_chats

    # ──────────────────────────────────────────────────────────────────
    # Command Handlers
    # ──────────────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            f"🎯 전략 OS V3 활성화\n"
            f"Chat ID: {chat_id}\n\n"
            f"사용 가능 명령어:\n"
            f"/report — 현장 보고\n"
            f"/order — 전략 지시\n"
            f"/hypo — 전략 가설\n"
            f"/block — 금지어 등록\n"
            f"/narrative — 서사 설정\n"
            f"/override — AI 판단 덮어쓰기\n"
            f"/status — 시스템 상태\n"
            f"/queue — 대기 중 제안\n"
            f"/approve — 제안 승인\n"
            f"/reject — 제안 거부\n"
            f"/edit — 제안 수정\n"
            f"/signals — 내부 시그널 목록\n"
            f"/memory — 전략 메모리 조회"
        )

    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/report")

    async def cmd_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/order")

    async def cmd_hypo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/hypo")

    async def cmd_block(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/block")

    async def cmd_narrative(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/narrative")

    async def cmd_override(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._handle_structured_input(update, "/override")

    async def _handle_structured_input(self, update: Update, command_prefix: str):
        """구조화 명령어 처리 공통 로직."""
        chat_id = update.effective_chat.id
        if not self._check_access(chat_id):
            await update.message.reply_text("⛔ 접근 권한 없음")
            return

        text = update.message.text
        signal = self.cmd_parser.parse(
            text, chat_id=chat_id, message_id=update.message.message_id,
        )

        if not signal:
            # 명령어만 입력한 경우 (본문 없음) → 사용법 안내
            usage = self._get_usage(command_prefix)
            await update.message.reply_text(usage)
            return

        # 저장
        signal_id = self.storage.save_signal(signal)

        # block이면 blocked_terms 테이블에도 추가
        if signal.signal_type == SignalType.BLOCK:
            meta = signal.metadata
            self.storage.save_block(
                term=meta.get("term", ""),
                reason=meta.get("reason", ""),
                scope=meta.get("scope", "all"),
                expiry=signal.expiry,
            )

        # narrative이면 active_narratives 테이블에도 추가
        if signal.signal_type == SignalType.NARRATIVE:
            meta = signal.metadata
            self.storage.save_narrative(
                priority=meta.get("priority_rank", 1),
                frame=meta.get("frame", signal.content),
                keywords=meta.get("keywords", []),
                expiry=signal.expiry,
            )

        await update.message.reply_text(
            f"✅ 시그널 등록 완료\n{signal.to_telegram_display()}"
        )
        logger.info("signal_saved", extra={"id": signal_id, "type": signal.signal_type.value})

    def _get_usage(self, command: str) -> str:
        usages = {
            "/report": (
                "📡 현장 보고 형식:\n\n"
                "/report\n"
                "region: 김해\n"
                "issue: 생활지원금\n"
                "content: 현장반응 냉담\n"
                "confidence: high\n"
                "expiry: 24h"
            ),
            "/order": (
                "⚡ 전략 지시 형식:\n\n"
                "/order\n"
                "issue: 강남발언\n"
                "instruction: 후보 직접 대응 금지\n"
                "expiry: today 18:00\n"
                "priority: urgent"
            ),
            "/hypo": (
                "🔬 전략 가설 형식:\n\n"
                "/hypo\n"
                "issue: 조선업\n"
                "hypothesis: 양산보다 창원에서 더 효과적\n"
                "content: 3일 내 여론 확인"
            ),
            "/block": (
                "🚫 금지어 등록 형식:\n\n"
                "/block\n"
                "term: 퍼주기\n"
                "reason: 역프레이밍 위험\n"
                "scope: all"
            ),
            "/narrative": (
                "📖 서사 설정 형식:\n\n"
                "/narrative\n"
                "priority: 1\n"
                "frame: 구조적 경제회복\n"
                "keywords: 조선,방산,경제\n"
                "expiry: 7d"
            ),
            "/override": (
                "⚠️ AI 판단 덮어쓰기 형식:\n\n"
                "/override\n"
                "issue: 강남발언\n"
                "ai_stance: counter\n"
                "my_stance: avoid\n"
                "reason: 팩트 미확인\n"
                "expiry: today 18:00"
            ),
        }
        return usages.get(command, "알 수 없는 명령어")

    # ──────────────────────────────────────────────────────────────────
    # Approval Commands
    # ──────────────────────────────────────────────────────────────────

    async def cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        result = self.approval_parser.parse_approve(update.message.text)
        if not result:
            await update.message.reply_text("사용법: /approve P-0042 [담당자]")
            return

        proposal = self.storage.get_proposal(result["proposal_id"])
        if not proposal:
            await update.message.reply_text(f"❌ {result['proposal_id']} 없음")
            return
        if not proposal.is_pending:
            await update.message.reply_text(f"⚠️ 이미 처리됨: {proposal.status.value}")
            return

        self.storage.update_proposal_status(
            result["proposal_id"],
            ProposalStatus.APPROVED,
            assigned_owner=result.get("assigned_owner"),
        )
        await update.message.reply_text(
            f"✅ 승인 완료: {result['proposal_id']}\n"
            f"최종: {proposal.ai_recommendation}\n"
            f"담당: {result.get('assigned_owner', '미지정')}"
        )

    async def cmd_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        result = self.approval_parser.parse_reject(update.message.text)
        if not result:
            await update.message.reply_text("사용법: /reject P-0042 [사유]")
            return

        proposal = self.storage.get_proposal(result["proposal_id"])
        if not proposal or not proposal.is_pending:
            await update.message.reply_text(f"❌ 처리 불가")
            return

        self.storage.update_proposal_status(
            result["proposal_id"],
            ProposalStatus.REJECTED,
            rejection_reason=result["reason"],
        )
        await update.message.reply_text(f"❌ 거부: {result['proposal_id']}\n사유: {result['reason']}")

    async def cmd_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        result = self.approval_parser.parse_edit(update.message.text)
        if not result:
            await update.message.reply_text("사용법: /edit P-0042 stance=avoid, owner=전략팀")
            return

        proposal = self.storage.get_proposal(result["proposal_id"])
        if not proposal or not proposal.is_pending:
            await update.message.reply_text(f"❌ 처리 불가")
            return

        self.storage.update_proposal_status(
            result["proposal_id"],
            ProposalStatus.EDITED,
            human_version=result["human_version"],
        )
        await update.message.reply_text(
            f"✏️ 수정 승인: {result['proposal_id']}\n"
            f"원본: {proposal.ai_recommendation}\n"
            f"수정: {result['human_version']}"
        )

    # ──────────────────────────────────────────────────────────────────
    # Status / Query Commands
    # ──────────────────────────────────────────────────────────────────

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        status = self.storage.get_dashboard_status()
        overrides = self.storage.get_active_overrides()
        narratives = self.storage.get_active_narratives()
        blocks = self.storage.get_active_blocks()

        lines = [
            "━━ 전략 OS 상태 ━━",
            f"📋 대기 제안: {status['pending_proposals']}건",
            f"⚠️ 활성 override: {status['active_overrides']}건",
            f"📡 활성 시그널: {status['active_signals']}건",
            f"🚫 차단어: {len(blocks)}건",
            f"📖 활성 서사: {len(narratives)}건",
        ]

        if overrides:
            lines.append("\n── 활성 Override ──")
            for ov in overrides[:5]:
                meta = ov.metadata
                lines.append(
                    f"• {ov.issue_id}: AI={meta.get('ai_stance','?')} → "
                    f"실장={meta.get('my_stance','?')}"
                    f" (~{ov.expiry.strftime('%H:%M') if ov.expiry else '무기한'})"
                )

        await update.message.reply_text("\n".join(lines))

    async def cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        proposals = self.storage.get_pending_proposals()
        if not proposals:
            await update.message.reply_text("📋 대기 중 제안 없음")
            return

        lines = ["━━ 대기 중 제안 ━━"]
        for p in proposals[:10]:
            urgency_icon = {"immediate": "🔴", "today": "🟠", "48h": "🟡", "monitoring": "🟢"}.get(p.urgency.value, "⚪")
            lines.append(
                f"{urgency_icon} {p.id} │ {p.issue_id or '전체'} │ {p.ai_recommendation[:30]}"
            )
        lines.append(f"\n/approve /reject /edit 로 처리")
        await update.message.reply_text("\n".join(lines))

    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        signals = self.storage.get_all_signals(limit=10)
        if not signals:
            await update.message.reply_text("📡 시그널 없음")
            return

        lines = ["━━ 최근 시그널 ━━"]
        for s in signals:
            ts = s.timestamp.strftime("%m/%d %H:%M")
            lines.append(f"{ts} │ {s.signal_type.value} │ {s.issue_id or '-'} │ {s.content[:30]}")
        await update.message.reply_text("\n".join(lines))

    async def cmd_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_access(update.effective_chat.id):
            return
        all_mem = self.storage.get_all_memory()
        if not all_mem:
            await update.message.reply_text("🧠 메모리 비어있음")
            return

        lines = ["━━ 전략 메모리 ━━"]
        for mem_type, memories in all_mem.items():
            lines.append(f"\n📁 {mem_type}")
            for m in memories[:5]:
                val_preview = str(m.value)[:50]
                lines.append(f"  • {m.memory_key}: {val_preview}")
        await update.message.reply_text("\n".join(lines))

    # ──────────────────────────────────────────────────────────────────
    # Natural Language Fallback
    # ──────────────────────────────────────────────────────────────────

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """구조화 명령어가 아닌 일반 텍스트 → AI 자동 분류."""
        if not self._check_access(update.effective_chat.id):
            return

        text = update.message.text
        if not text or text.startswith("/"):
            return

        if self.ai_classifier:
            signal = await self.ai_classifier.classify(
                text,
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )
            if signal:
                self.storage.save_signal(signal)
                await update.message.reply_text(
                    f"🤖 자동 분류 완료:\n{signal.to_telegram_display()}"
                )
                return

        # AI 분류기 없으면 field_report로 기본 저장
        signal = InternalSignal(
            signal_type=SignalType.FIELD_REPORT,
            content=text,
            source="strategy_director",
            telegram_chat_id=update.effective_chat.id,
            telegram_message_id=update.message.message_id,
        )
        self.storage.save_signal(signal)
        await update.message.reply_text(
            f"📡 현장보고로 저장됨:\n{text[:100]}"
        )

    # ──────────────────────────────────────────────────────────────────
    # Notification (AI → Director)
    # ──────────────────────────────────────────────────────────────────

    async def notify_proposal(self, app: Application, proposal):
        """AI가 생성한 제안을 전략실장에게 알림."""
        if not self.allowed_chats:
            return
        text = proposal.to_telegram_notification()
        for chat_id in self.allowed_chats:
            try:
                await app.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logger.error(f"notification_failed: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Bot Setup
    # ──────────────────────────────────────────────────────────────────

    def build_application(self) -> Application:
        """python-telegram-bot Application 생성."""
        app = Application.builder().token(self.token).build()

        # Structured commands
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("report", self.cmd_report))
        app.add_handler(CommandHandler("order", self.cmd_order))
        app.add_handler(CommandHandler("hypo", self.cmd_hypo))
        app.add_handler(CommandHandler("block", self.cmd_block))
        app.add_handler(CommandHandler("narrative", self.cmd_narrative))
        app.add_handler(CommandHandler("override", self.cmd_override))

        # Approval commands
        app.add_handler(CommandHandler("approve", self.cmd_approve))
        app.add_handler(CommandHandler("reject", self.cmd_reject))
        app.add_handler(CommandHandler("edit", self.cmd_edit))

        # Status commands
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("queue", self.cmd_queue))
        app.add_handler(CommandHandler("signals", self.cmd_signals))
        app.add_handler(CommandHandler("memory", self.cmd_memory))

        # Natural language fallback
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        return app
