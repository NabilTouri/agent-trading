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
    check_portfolio_correlation,
    estimate_slippage,
    analyze_market_depth,
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
        role="Risk & Execution Manager",
        goal=(
            "Based on the market analysis and sentiment reports from previous agents, "
            "make the FINAL trade decision. You must: "
            "1) Check portfolio state (balance, open positions, exposure, drawdown), "
            "2) Calculate optimal position size using Kelly Criterion, "
            "3) Assess Value at Risk for the proposed trade, "
            "4) Check correlation with existing positions, "
            "5) Verify market depth and expected slippage, "
            "6) Produce a FINAL decision: APPROVED or REJECTED. "
            "If APPROVED, include full entry plan, stop loss, take profit levels, "
            "and position sizing. If REJECTED, explain exactly why. "
            "Your output MUST be a valid JSON object matching the TradeDecision schema."
        ),
        backstory=(
            "You are a risk manager and execution specialist with extensive experience "
            "in crypto derivatives. You never let a bad trade through — your reputation "
            "depends on strict risk discipline. You use Kelly Criterion for sizing, "
            "Value at Risk for risk assessment, and always verify market depth before "
            "approving execution. You reject trades that don't meet minimum risk/reward "
            "requirements (R:R ≥ 2.0), have insufficient confidence, or would create "
            "excessive portfolio concentration. A REJECTED trade is always better than "
            "a reckless approval."
        ),
        llm=llm,
        tools=[
            get_portfolio_state,
            calculate_kelly_position_size,
            calculate_var,
            check_portfolio_correlation,
            estimate_slippage,
            analyze_market_depth,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=10,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
