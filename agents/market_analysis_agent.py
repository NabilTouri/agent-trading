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
)
from tools.technical_analysis import (
    calculate_indicators,
    detect_chart_patterns,
    find_support_resistance,
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
        role="Market Analyst",
        goal="Analyze the trading pair technically. Output SHORT JSON with bias, confidence, key levels.",
        backstory="Senior quant analyst for crypto derivatives. Disciplined, data-driven, never forces trades.",
        llm=llm,
        tools=[
            get_orderbook,
            get_funding_rate,
            get_klines,
            calculate_indicators,
            detect_chart_patterns,
            find_support_resistance,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
