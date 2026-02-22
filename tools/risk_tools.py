"""
Risk management tools for CrewAI agents.

These tools provide portfolio state, Kelly criterion sizing,
Value at Risk, Monte Carlo simulation, correlation analysis,
slippage estimation, and market depth analysis.
"""

import json
import math
from typing import Dict, List, Optional
import numpy as np
from crewai.tools import tool
from loguru import logger


def _get_exchange():
    from core.exchange import exchange
    return exchange


def _get_db():
    from core.database import db
    return db


def _get_settings():
    from core.config import settings
    return settings


@tool("get_portfolio_state")
def get_portfolio_state() -> str:
    """
    Get the current portfolio state including balance, open positions,
    total exposure, drawdown, and recent performance metrics.
    Use this to understand current risk exposure before making trade decisions.
    """
    try:
        ex = _get_exchange()
        db = _get_db()
        s = _get_settings()

        balance = ex.get_account_balance()
        positions = db.get_all_open_positions()
        metrics = db.calculate_metrics()
        initial_capital = db.get_initial_capital()

        # Calculate total exposure
        total_exposure = sum(p.size for p in positions)
        exposure_pct = (total_exposure / balance * 100) if balance > 0 else 0

        # Calculate drawdown
        drawdown = 0.0
        if initial_capital > 0 and balance < initial_capital:
            drawdown = ((initial_capital - balance) / initial_capital) * 100

        result = {
            "balance_usd": round(balance, 2),
            "initial_capital": round(initial_capital, 2),
            "open_positions": len(positions),
            "max_positions": s.max_positions,
            "positions_detail": [
                {
                    "pair": p.pair,
                    "side": p.side,
                    "size_usd": round(p.size, 2),
                    "entry_price": round(p.entry_price, 2),
                    "stop_loss": round(p.stop_loss, 2),
                }
                for p in positions
            ],
            "total_exposure_usd": round(total_exposure, 2),
            "exposure_pct": round(exposure_pct, 2),
            "max_exposure_pct": s.max_capital_in_positions_pct * 100,
            "drawdown_pct": round(drawdown, 2),
            "max_drawdown_pct": s.max_drawdown * 100,
            "performance": {
                "total_trades": metrics["total_trades"],
                "win_rate": metrics["win_rate"],
                "avg_profit": metrics["avg_profit"],
                "avg_loss": metrics["avg_loss"],
                "profit_factor": metrics["profit_factor"],
                "total_pnl": metrics["total_pnl"],
            },
            "risk_per_trade_pct": s.risk_per_trade * 100,
            "can_open_new_position": len(positions) < s.max_positions,
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching portfolio state: {e}")
        return json.dumps({"error": str(e)})


@tool("calculate_kelly_position_size")
def calculate_kelly_position_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    balance: float,
) -> str:
    """
    Calculate optimal position size using the Kelly Criterion.
    
    Args:
        win_rate: Historical win rate as decimal (e.g., 0.55 for 55%)
        avg_win: Average winning trade amount in USD
        avg_loss: Average losing trade amount in USD (positive number)
        balance: Current account balance in USD
    
    Returns the full Kelly and half-Kelly recommended position sizes.
    Half-Kelly is generally recommended for real trading.
    """
    try:
        s = _get_settings()

        if avg_loss <= 0 or balance <= 0:
            return json.dumps({"error": "avg_loss and balance must be positive"})

        # Kelly formula: f* = (bp - q) / b
        # b = avg_win / avg_loss (win/loss ratio)
        # p = win probability
        # q = loss probability (1 - p)
        b = avg_win / avg_loss
        p = min(max(win_rate, 0.0), 1.0)
        q = 1 - p

        kelly_fraction = (b * p - q) / b if b > 0 else 0
        kelly_fraction = max(0, kelly_fraction)  # Can't be negative

        # Half-Kelly (more conservative, recommended)
        half_kelly = kelly_fraction / 2

        # Apply position size caps
        max_pct = s.risk_per_trade  # e.g., 0.025 for 2.5%
        effective_pct = min(half_kelly, max_pct)

        full_kelly_usd = balance * kelly_fraction
        half_kelly_usd = balance * half_kelly
        capped_usd = balance * effective_pct

        result = {
            "win_rate": round(p, 4),
            "win_loss_ratio": round(b, 4),
            "full_kelly_fraction": round(kelly_fraction, 4),
            "full_kelly_usd": round(full_kelly_usd, 2),
            "half_kelly_fraction": round(half_kelly, 4),
            "half_kelly_usd": round(half_kelly_usd, 2),
            "capped_fraction": round(effective_pct, 4),
            "capped_usd": round(capped_usd, 2),
            "max_allowed_pct": round(max_pct * 100, 2),
            "recommendation": f"Use ${capped_usd:.2f} ({effective_pct*100:.2f}% of balance)",
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error calculating Kelly: {e}")
        return json.dumps({"error": str(e)})


@tool("calculate_var")
def calculate_var(pair: str, position_size: float, confidence: float = 0.95) -> str:
    """
    Calculate Value at Risk (VaR) for a proposed position using historical simulation.
    
    Args:
        pair: Trading pair (e.g., BTC/USDT)
        position_size: Proposed position size in USD
        confidence: Confidence level (default 95%)
    
    Returns the maximum expected loss at the given confidence level
    over a 1-day holding period.
    """
    try:
        ex = _get_exchange()
        candles = ex.get_klines(pair, "1h", 200)

        if len(candles) < 50:
            return json.dumps({"error": "Insufficient historical data for VaR"})

        # Calculate hourly returns
        closes = np.array([c["close"] for c in candles])
        returns = np.diff(closes) / closes[:-1]

        # Scale to daily returns (assuming 24h)
        daily_returns = returns[-24:] if len(returns) >= 24 else returns
        daily_return = np.sum(daily_returns)  # Approximate daily return from hourly

        # Historical VaR
        all_daily_returns = []
        for i in range(0, len(returns) - 23, 24):
            day_ret = np.sum(returns[i:i+24])
            all_daily_returns.append(day_ret)

        if len(all_daily_returns) < 5:
            # Fall back to hourly returns scaled
            var_return = np.percentile(returns, (1 - confidence) * 100) * math.sqrt(24)
        else:
            var_return = np.percentile(all_daily_returns, (1 - confidence) * 100)

        var_usd = abs(var_return) * position_size
        var_pct = abs(var_return) * 100

        # Expected Shortfall (CVaR) - average of losses beyond VaR
        if len(all_daily_returns) >= 5:
            sorted_returns = np.sort(all_daily_returns)
            cutoff = int(len(sorted_returns) * (1 - confidence))
            cvar_return = np.mean(sorted_returns[:max(cutoff, 1)])
        else:
            sorted_returns = np.sort(returns)
            cutoff = int(len(sorted_returns) * (1 - confidence))
            cvar_return = np.mean(sorted_returns[:max(cutoff, 1)]) * math.sqrt(24)

        cvar_usd = abs(cvar_return) * position_size

        result = {
            "pair": pair,
            "position_size_usd": round(position_size, 2),
            "confidence_level": confidence,
            "var_1day_usd": round(var_usd, 2),
            "var_1day_pct": round(var_pct, 2),
            "cvar_1day_usd": round(cvar_usd, 2),
            "interpretation": (
                f"At {confidence*100:.0f}% confidence, the maximum expected 1-day loss "
                f"is ${var_usd:.2f} ({var_pct:.2f}%). "
                f"Average loss in worst scenarios: ${cvar_usd:.2f}."
            ),
            "risk_rating": (
                "HIGH" if var_pct > 5
                else "MODERATE" if var_pct > 2
                else "LOW"
            ),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error calculating VaR for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("check_portfolio_correlation")
def check_portfolio_correlation(pair: str) -> str:
    """
    Check correlation between a proposed pair and existing open positions.
    High correlation increases concentration risk. Ideally new trades
    should have low correlation with existing positions.
    """
    try:
        ex = _get_exchange()
        db = _get_db()

        positions = db.get_all_open_positions()
        if not positions:
            return json.dumps({
                "pair": pair,
                "correlation_risk": "NONE",
                "message": "No open positions — no correlation risk",
                "correlations": [],
            })

        # Get returns for proposed pair
        candles = ex.get_klines(pair, "1h", 50)
        if len(candles) < 20:
            return json.dumps({"error": "Insufficient data"})

        proposed_returns = np.diff([c["close"] for c in candles]) / np.array([c["close"] for c in candles[:-1]])

        correlations = []
        for pos in positions:
            pos_candles = ex.get_klines(pos.pair, "1h", 50)
            if len(pos_candles) < 20:
                continue

            pos_returns = np.diff([c["close"] for c in pos_candles]) / np.array([c["close"] for c in pos_candles[:-1]])

            # Align lengths
            min_len = min(len(proposed_returns), len(pos_returns))
            corr = float(np.corrcoef(proposed_returns[:min_len], pos_returns[:min_len])[0, 1])

            correlations.append({
                "existing_pair": pos.pair,
                "correlation": round(corr, 4),
                "risk": (
                    "HIGH" if abs(corr) > 0.7
                    else "MODERATE" if abs(corr) > 0.4
                    else "LOW"
                ),
            })

        max_corr = max(abs(c["correlation"]) for c in correlations) if correlations else 0

        result = {
            "pair": pair,
            "correlations": correlations,
            "max_absolute_correlation": round(max_corr, 4),
            "correlation_risk": (
                "HIGH — consider reducing size" if max_corr > 0.7
                else "MODERATE" if max_corr > 0.4
                else "LOW — good diversification"
            ),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error checking correlation for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("estimate_slippage")
def estimate_slippage(pair: str, order_size_usd: float) -> str:
    """
    Estimate expected slippage based on orderbook depth for a given order size.
    
    Args:
        pair: Trading pair
        order_size_usd: Order size in USD
    
    Returns estimated slippage in basis points and USD.
    """
    try:
        ex = _get_exchange()
        symbol = pair.replace("/", "")
        current_price = ex.get_current_price(pair)

        orderbook = ex.client.futures_order_book(symbol=symbol, limit=50)

        # Calculate how deep we'd need to go to fill the order
        order_qty = order_size_usd / current_price if current_price > 0 else 0

        # Simulate market buy (walk through asks)
        filled_qty = 0.0
        total_cost = 0.0
        for ask in orderbook["asks"]:
            price = float(ask[0])
            qty = float(ask[1])
            fill_amt = min(qty, order_qty - filled_qty)
            total_cost += fill_amt * price
            filled_qty += fill_amt
            if filled_qty >= order_qty:
                break

        avg_fill_price = total_cost / filled_qty if filled_qty > 0 else current_price
        slippage_pct = ((avg_fill_price - current_price) / current_price) * 100
        slippage_bps = slippage_pct * 100
        slippage_usd = order_size_usd * (slippage_pct / 100)

        # Calculate spread
        best_bid = float(orderbook["bids"][0][0]) if orderbook["bids"] else current_price
        best_ask = float(orderbook["asks"][0][0]) if orderbook["asks"] else current_price
        spread_bps = ((best_ask - best_bid) / best_bid) * 10000 if best_bid > 0 else 0

        s = _get_settings()

        result = {
            "pair": pair,
            "order_size_usd": round(order_size_usd, 2),
            "current_price": round(current_price, 2),
            "estimated_fill_price": round(avg_fill_price, 2),
            "slippage_pct": round(slippage_pct, 4),
            "slippage_bps": round(slippage_bps, 2),
            "slippage_usd": round(slippage_usd, 4),
            "spread_bps": round(spread_bps, 2),
            "spread_ok": spread_bps < s.max_spread_bps,
            "slippage_ok": slippage_pct < s.max_slippage_pct,
            "execution_quality": (
                "EXCELLENT" if slippage_bps < 2
                else "GOOD" if slippage_bps < 5
                else "FAIR" if slippage_bps < 10
                else "POOR"
            ),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error estimating slippage for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("analyze_market_depth")
def analyze_market_depth(pair: str) -> str:
    """
    Analyze market depth and overall liquidity around the current price.
    Checks if there's sufficient liquidity for safe trade execution.
    Returns bid/ask depth at various price levels (0.5%, 1%, 2% from mid).
    """
    try:
        ex = _get_exchange()
        symbol = pair.replace("/", "")
        current_price = ex.get_current_price(pair)

        orderbook = ex.client.futures_order_book(symbol=symbol, limit=100)

        bids = [(float(b[0]), float(b[1])) for b in orderbook["bids"]]
        asks = [(float(a[0]), float(a[1])) for a in orderbook["asks"]]

        # Calculate depth at various levels
        levels = [0.5, 1.0, 2.0]
        depth_analysis = {}

        for level in levels:
            upper = current_price * (1 + level / 100)
            lower = current_price * (1 - level / 100)

            bid_depth = sum(p * q for p, q in bids if p >= lower)
            ask_depth = sum(p * q for p, q in asks if p <= upper)

            depth_analysis[f"{level}pct"] = {
                "bid_depth_usd": round(bid_depth, 2),
                "ask_depth_usd": round(ask_depth, 2),
                "total_depth_usd": round(bid_depth + ask_depth, 2),
            }

        total_bid = sum(p * q for p, q in bids)
        total_ask = sum(p * q for p, q in asks)

        result = {
            "pair": pair,
            "current_price": round(current_price, 2),
            "depth_by_level": depth_analysis,
            "total_bid_depth_usd": round(total_bid, 2),
            "total_ask_depth_usd": round(total_ask, 2),
            "bid_ask_ratio": round(total_bid / total_ask, 4) if total_ask > 0 else 0,
            "liquidity_assessment": (
                "HIGH" if total_bid + total_ask > 1_000_000
                else "MODERATE" if total_bid + total_ask > 100_000
                else "LOW"
            ),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error analyzing market depth for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})
