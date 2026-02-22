"""
Market Analysis Agent for CrewAI.

Senior Quantitative Market Analyst specializing in technical analysis,
market structure, and price action across multiple timeframes.
"""

from crewai import Agent

from tools.market_data import (
    get_orderbook,
    get_funding_rate,
    get_klines,
    get_current_price,
)
from tools.technical_analysis import (
    calculate_indicators,
    detect_chart_patterns,
    find_support_resistance,
    analyze_volume_profile,
)


def create_market_analysis_agent(llm: str) -> Agent:
    """
    Create the Market Analysis agent.

    This agent is responsible for comprehensive market analysis:
    - Multi-timeframe technical analysis (RSI, MACD, BB, EMAs, ADX)
    - Chart pattern detection (double tops/bottoms, engulfing, inside bars)
    - Support/resistance zone identification
    - Volume profile analysis (POC, Value Area)
    - Orderbook imbalance and funding rate analysis

    Args:
        llm: LLM identifier string in LiteLLM format (e.g., "anthropic/claude-sonnet-4-20250514")

    Returns:
        CrewAI Agent configured for market analysis
    """
    return Agent(
        role="Senior Quantitative Market Analyst",
        goal=(
            "Produce a complete quantitative market analysis for the given trading pair. "
            "Your analysis must include: 1) Market structure (trend direction, strength), "
            "2) Multi-timeframe technical indicators with clear signals, "
            "3) Key support/resistance zones, 4) Volume profile analysis, "
            "5) Orderbook and funding rate sentiment, "
            "6) A clear directional bias (LONG, SHORT, or NEUTRAL) with confidence level."
        ),
        backstory=(
            "You are a senior quantitative analyst with 15 years of experience in "
            "cryptocurrency derivatives markets. You combine on-chain data, orderbook "
            "analysis, and multi-timeframe technical analysis to build a unified "
            "quantitative view of the market. You are known for your disciplined "
            "approach: you never force a trade when the data is ambiguous, and you "
            "always clearly state your confidence level. Your analysis drives the "
            "first step of a 3-agent trading system."
        ),
        llm=llm,
        tools=[
            get_orderbook,
            get_funding_rate,
            get_klines,
            get_current_price,
            calculate_indicators,
            detect_chart_patterns,
            find_support_resistance,
            analyze_volume_profile,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=10,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
