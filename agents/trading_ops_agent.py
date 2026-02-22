"""
Trading Operations Agent for CrewAI.

Risk & Execution Manager who validates risk, calculates position sizing,
and produces the final structured trade decision.
"""

from crewai import Agent

from tools.risk_tools import (
    get_portfolio_state,
    calculate_kelly_position_size,
    calculate_var,
    estimate_slippage,
)


def create_trading_ops_agent(llm: str) -> Agent:
    """
    Create the Trading Operations agent.

    This agent is the final decision-maker in the 3-agent pipeline:
    - Reads the Market Analysis and Sentiment reports from previous tasks
    - Validates whether a trade is warranted given current portfolio risk
    - Calculates optimal position size using Kelly Criterion
    - Assesses Value at Risk and correlation with existing positions
    - Checks market depth and expected slippage
    - Produces a structured TradeDecision: APPROVED or REJECTED

    The output MUST be a valid JSON conforming to the TradeDecision schema.

    Args:
        llm: LLM identifier string in LiteLLM format

    Returns:
        CrewAI Agent configured for risk management and execution planning
    """
    return Agent(
        role="Risk Manager",
        goal="Make FINAL APPROVED/REJECTED trade decision. Output valid TradeDecision JSON.",
        backstory="Strict risk manager. Uses Kelly sizing, VaR. Rejects unless criteria met.",
        llm=llm,
        tools=[
            get_portfolio_state,
            calculate_kelly_position_size,
            calculate_var,
            estimate_slippage,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
