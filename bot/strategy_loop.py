import asyncio
from loguru import logger
from datetime import datetime
from core.config import settings
from core.database import db
from core.exchange import exchange
from core.models import Signal, ActionType
from core.cost_tracker import cost_tracker
from core.safeguards import safeguards
from agents.crew import TradingCrew
from services.telegram_bot import telegram_notifier


class StrategyLoop:
    """Strategy loop: runs CrewAI crew for each trading pair on interval."""

    def __init__(self):
        self.interval = settings.strategy_interval_minutes * 60  # to seconds

        logger.info(
            f"StrategyLoop initialized (CrewAI mode) — "
            f"Model: {settings.crew_model}, "
            f"Interval: {settings.strategy_interval_minutes}min, "
            f"Pairs: {settings.pairs_list}"
        )

    async def run(self):
        """Main loop."""
        # Initial delay to let system stabilize
        await asyncio.sleep(5)

        while True:
            try:
                logger.info("=" * 50)
                logger.info(f"STRATEGY CYCLE START - {datetime.now()}")

                for pair in settings.pairs_list:
                    await self.analyze_pair(pair)

                logger.info(f"STRATEGY CYCLE END - sleeping {self.interval}s")
                logger.info("=" * 50)

            except Exception as e:
                logger.error(f"Strategy loop error: {e}")

            await asyncio.sleep(self.interval)

    async def analyze_pair(self, pair: str):
        """Run CrewAI analysis pipeline for a single pair."""
        logger.info(f"Analyzing {pair}...")

        try:
            # 1. Check cost budget before running crew
            if not cost_tracker.check_budget():
                logger.warning(f"💰 Budget limit reached — skipping {pair}")
                return

            # 2. Run CrewAI crew (blocking call wrapped in thread)
            crew = TradingCrew(pair)
            decision = await asyncio.to_thread(crew.run)

            if decision is None:
                logger.warning(f"Crew returned no decision for {pair}")
                return

            # 3. Log token usage
            usage = crew.get_usage_metrics()
            if usage:
                cost_tracker.log_usage(usage, pair=pair)

            # 4. Run through safeguards (only if APPROVED by crew)
            if decision.decision == "APPROVED":
                report = safeguards.validate_trade(decision)
                approved = report.approved
                reasoning_suffix = ""
                if not approved:
                    reasoning_suffix = f" [BLOCKED: {report.blocked_reason}]"
            else:
                approved = False
                reasoning_suffix = " [Crew: REJECTED]"

            # 5. Create signal from decision
            action = ActionType.HOLD
            if approved:
                action = ActionType.BUY if decision.direction == "LONG" else ActionType.SELL

            signal = Signal(
                pair=pair,
                action=action,
                confidence=decision.confidence,
                reasoning=decision.reasoning + reasoning_suffix,
                agent_votes={
                    "market_analysis": decision.market_analysis_summary[:100] if decision.market_analysis_summary else "N/A",
                    "sentiment": decision.sentiment_summary[:100] if decision.sentiment_summary else "N/A",
                    "trading_ops": decision.decision,
                },
                market_data={
                    "price": decision.entry.price if decision.entry else 0,
                    "stop_loss": decision.stop_loss.price if decision.stop_loss else 0,
                    "take_profit": decision.take_profit[0].price if decision.take_profit else 0,
                    "position_size": decision.position_size_usd,
                    "direction": decision.direction,
                    "risk_reward_ratio": decision.risk_reward_ratio,
                },
            )

            # 6. Save signal
            db.save_signal(signal)

            logger.info(
                f"Signal for {pair}: {signal.action} "
                f"(confidence: {signal.confidence}%, "
                f"direction: {decision.direction}, "
                f"R:R: {decision.risk_reward_ratio:.2f})"
            )

            # 7. Notify if approved and high confidence
            if approved and decision.confidence >= settings.full_size_confidence:
                await self._notify_signal(signal, decision)

        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            import traceback
            traceback.print_exc()

    async def _notify_signal(self, signal: Signal, decision):
        """Send Telegram notification for approved signal."""
        emoji = "🟢" if signal.action == ActionType.BUY else "🔴"
        direction = "LONG" if signal.action == ActionType.BUY else "SHORT"

        # Format take profit levels
        tp_lines = ""
        for tp in decision.take_profit:
            tp_lines += f"  TP{tp.level}: ${tp.price:.2f} ({tp.size_pct}%)\n"

        message = f"""
{emoji} <b>SIGNAL: {direction} {signal.pair}</b>

Confidence: {signal.confidence}%
Entry: ${decision.entry.price:.2f} ({decision.entry.method})
Size: ${decision.position_size_usd:.2f} ({decision.position_size_pct:.1f}%)
R:R: {decision.risk_reward_ratio:.2f}

Stop Loss: ${decision.stop_loss.price:.2f} ({decision.stop_loss.pct:.1f}%)
Take Profit:
{tp_lines}
<i>{signal.reasoning[:200]}...</i>

⏳ <i>Execution loop will attempt this trade shortly.</i>
"""

        await telegram_notifier.send_message(message)
