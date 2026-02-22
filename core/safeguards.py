"""
Trading Safeguards — pre-trade validation engine.

All checks that must pass before a trade is executed. This module
centralizes the rules that were previously scattered across
execution_loop.py and strategy_loop.py.
"""

import json
from datetime import datetime, timedelta
from typing import Tuple, List
from loguru import logger

from core.config import settings
from core.models import TradeDecision, SafeguardResult, SafeguardReport


class TradingSafeguards:
    """
    Enforces all pre-trade validation rules.

    Each check returns a SafeguardResult. The validate_trade method
    runs all checks and returns a SafeguardReport.
    """

    def __init__(self) -> None:
        # Lazy imports to avoid circular dependencies
        self._db = None
        self._exchange = None

    @property
    def db(self):
        if self._db is None:
            from core.database import db
            self._db = db
        return self._db

    @property
    def exchange(self):
        if self._exchange is None:
            from core.exchange import exchange
            self._exchange = exchange
        return self._exchange

    def validate_trade(self, decision: TradeDecision) -> SafeguardReport:
        """
        Run all safeguard checks against a trade decision.

        Returns:
            SafeguardReport with approval status and individual check results.
        """
        checks: List[SafeguardResult] = [
            self._check_confidence(decision),
            self._check_rr_ratio(decision),
            self._check_sl_distance(decision),
            self._check_position_size(decision),
            self._check_max_positions(),
            self._check_portfolio_exposure(decision),
            self._check_drawdown(),
            self._check_daily_trade_limit(),
            self._check_position_spacing(decision.pair),
            self._check_consecutive_losses(),
        ]

        failures = [c for c in checks if not c.passed]
        approved = len(failures) == 0

        if not approved:
            blocked_reason = "; ".join(f.reason for f in failures)
            logger.warning(
                f"🚫 Trade REJECTED for {decision.pair}: {blocked_reason}"
            )
        else:
            logger.info(f"✅ All {len(checks)} safeguard checks passed for {decision.pair}")

        return SafeguardReport(
            approved=approved,
            checks=checks,
            blocked_reason=blocked_reason if not approved else None,
        )

    # ─── Individual Checks ─────────────────────────────────────────────

    def _check_confidence(self, decision: TradeDecision) -> SafeguardResult:
        """Minimum confidence threshold."""
        passed = decision.confidence >= settings.min_confidence
        return SafeguardResult(
            check_name="confidence",
            passed=passed,
            reason=(
                f"Confidence {decision.confidence}% meets minimum {settings.min_confidence}%"
                if passed
                else f"Confidence {decision.confidence}% below minimum {settings.min_confidence}%"
            ),
        )

    def _check_rr_ratio(self, decision: TradeDecision) -> SafeguardResult:
        """Minimum risk:reward ratio."""
        passed = decision.risk_reward_ratio >= settings.min_rr_ratio
        return SafeguardResult(
            check_name="risk_reward_ratio",
            passed=passed,
            reason=(
                f"R:R {decision.risk_reward_ratio:.2f} meets minimum {settings.min_rr_ratio}"
                if passed
                else f"R:R {decision.risk_reward_ratio:.2f} below minimum {settings.min_rr_ratio}"
            ),
        )

    def _check_sl_distance(self, decision: TradeDecision) -> SafeguardResult:
        """Stop loss distance within limits."""
        passed = decision.stop_loss.pct <= settings.max_sl_distance_pct
        return SafeguardResult(
            check_name="stop_loss_distance",
            passed=passed,
            reason=(
                f"SL distance {decision.stop_loss.pct:.2f}% within {settings.max_sl_distance_pct}% limit"
                if passed
                else f"SL distance {decision.stop_loss.pct:.2f}% exceeds {settings.max_sl_distance_pct}% limit"
            ),
        )

    def _check_position_size(self, decision: TradeDecision) -> SafeguardResult:
        """Position size within risk-per-trade limits."""
        max_size_pct = settings.risk_per_trade * 100
        passed = decision.position_size_pct <= max_size_pct
        return SafeguardResult(
            check_name="position_size",
            passed=passed,
            reason=(
                f"Position size {decision.position_size_pct:.2f}% within {max_size_pct}% limit"
                if passed
                else f"Position size {decision.position_size_pct:.2f}% exceeds {max_size_pct}% limit"
            ),
        )

    def _check_max_positions(self) -> SafeguardResult:
        """Available position slots."""
        open_count = len(self.db.get_all_open_positions())
        passed = open_count < settings.max_positions
        return SafeguardResult(
            check_name="max_positions",
            passed=passed,
            reason=(
                f"{open_count}/{settings.max_positions} positions open — slot available"
                if passed
                else f"{open_count}/{settings.max_positions} positions open — no slots"
            ),
        )

    def _check_portfolio_exposure(self, decision: TradeDecision) -> SafeguardResult:
        """Total portfolio exposure within limits."""
        try:
            balance = self.exchange.get_account_balance()
            positions = self.db.get_all_open_positions()
            current_exposure = sum(p.size for p in positions)
            new_exposure = current_exposure + decision.position_size_usd
            exposure_pct = (new_exposure / balance * 100) if balance > 0 else 100
            max_pct = settings.max_capital_in_positions_pct * 100

            passed = exposure_pct <= max_pct
            return SafeguardResult(
                check_name="portfolio_exposure",
                passed=passed,
                reason=(
                    f"Exposure {exposure_pct:.1f}% within {max_pct}% limit"
                    if passed
                    else f"Exposure {exposure_pct:.1f}% would exceed {max_pct}% limit"
                ),
            )
        except Exception as e:
            logger.error(f"Error checking exposure: {e}")
            return SafeguardResult(
                check_name="portfolio_exposure",
                passed=False,
                reason=f"Could not verify exposure: {e}",
            )

    def _check_drawdown(self) -> SafeguardResult:
        """Drawdown circuit breaker."""
        try:
            balance = self.exchange.get_account_balance()
            initial = self.db.get_initial_capital()

            if initial <= 0 or balance >= initial:
                return SafeguardResult(
                    check_name="drawdown",
                    passed=True,
                    reason="No drawdown detected",
                )

            drawdown_pct = ((initial - balance) / initial) * 100
            max_dd = settings.max_drawdown * 100

            passed = drawdown_pct < max_dd
            return SafeguardResult(
                check_name="drawdown",
                passed=passed,
                reason=(
                    f"Drawdown {drawdown_pct:.1f}% within {max_dd}% limit"
                    if passed
                    else f"🚨 Drawdown {drawdown_pct:.1f}% exceeds {max_dd}% limit"
                ),
            )
        except Exception as e:
            logger.error(f"Error checking drawdown: {e}")
            return SafeguardResult(
                check_name="drawdown",
                passed=False,
                reason=f"Could not verify drawdown: {e}",
            )

    def _check_daily_trade_limit(self) -> SafeguardResult:
        """Daily trade count limit."""
        try:
            today = datetime.now().date().isoformat()
            key = f"trades:daily_count:{today}"
            count = int(self.db.client.get(key) or 0)

            passed = count < settings.max_trades_per_day
            return SafeguardResult(
                check_name="daily_trade_limit",
                passed=passed,
                reason=(
                    f"{count}/{settings.max_trades_per_day} trades today"
                    if passed
                    else f"Daily limit reached: {count}/{settings.max_trades_per_day}"
                ),
            )
        except Exception as e:
            logger.error(f"Error checking daily limit: {e}")
            return SafeguardResult(
                check_name="daily_trade_limit",
                passed=True,  # Fail open on read error
                reason=f"Could not verify daily limit: {e}",
            )

    def _check_position_spacing(self, pair: str) -> SafeguardResult:
        """Minimum time between positions for the same pair."""
        try:
            positions = self.db.get_all_open_positions()
            pair_positions = [p for p in positions if p.pair == pair]

            if not pair_positions:
                return SafeguardResult(
                    check_name="position_spacing",
                    passed=True,
                    reason=f"No existing position for {pair}",
                )

            latest = max(pair_positions, key=lambda p: p.opened_at)
            elapsed = (datetime.now() - latest.opened_at).total_seconds() / 60
            min_spacing = settings.min_position_spacing_minutes

            passed = elapsed >= min_spacing
            return SafeguardResult(
                check_name="position_spacing",
                passed=passed,
                reason=(
                    f"{elapsed:.0f}min since last {pair} position (min: {min_spacing}min)"
                    if passed
                    else f"Only {elapsed:.0f}min since last {pair} position (min: {min_spacing}min)"
                ),
            )
        except Exception as e:
            return SafeguardResult(
                check_name="position_spacing",
                passed=True,
                reason=f"Could not verify spacing: {e}",
            )

    def _check_consecutive_losses(self) -> SafeguardResult:
        """Consecutive loss pause."""
        try:
            recent_trades = self.db.get_recent_trades(limit=settings.consecutive_loss_pause_count)
            consecutive_losses = 0

            for trade in recent_trades:
                if trade.pnl < 0:
                    consecutive_losses += 1
                else:
                    break

            passed = consecutive_losses < settings.consecutive_loss_pause_count
            return SafeguardResult(
                check_name="consecutive_losses",
                passed=passed,
                reason=(
                    f"{consecutive_losses} consecutive losses (limit: {settings.consecutive_loss_pause_count})"
                    if passed
                    else f"🛑 {consecutive_losses} consecutive losses — cooling period required"
                ),
            )
        except Exception as e:
            return SafeguardResult(
                check_name="consecutive_losses",
                passed=True,
                reason=f"Could not verify losses: {e}",
            )


# Singleton instance
safeguards = TradingSafeguards()
