"""
Trading Crew — CrewAI assembly for multi-agent trading analysis.

Orchestrates 3 agents in a sequential pipeline:
1. Market Analysis Agent → technical analysis and market structure
2. Sentiment Agent → qualitative sentiment signals
3. Trading Operations Agent → risk validation and final decision

Each agent's output feeds into the next via CrewAI's sequential process.
The final output is a validated TradeDecision (APPROVED / REJECTED).
"""

from typing import Optional, Dict, Any
from crewai import Crew, Task, Process
from loguru import logger

from core.config import settings
from core.models import TradeDecision
from agents.market_analysis_agent import create_market_analysis_agent
from agents.sentiment_agent import create_sentiment_agent
from agents.trading_ops_agent import create_trading_ops_agent


class TradingCrew:
    """
    Assembles and runs the 3-agent trading crew for a given pair.

    Usage:
        crew = TradingCrew("BTC/USDT")
        decision = crew.run()
        if decision and decision.decision == "APPROVED":
            # Execute trade
    """

    def __init__(self, pair: str) -> None:
        self.pair = pair
        self.llm = settings.crew_llm_string
        self._usage_metrics: Dict[str, Any] = {}

        # Create agents
        self.market_agent = create_market_analysis_agent(self.llm)
        self.sentiment_agent = create_sentiment_agent(self.llm)
        self.trading_ops_agent = create_trading_ops_agent(self.llm)

        logger.info(f"TradingCrew initialized for {pair} with LLM: {self.llm}")

    def _build_tasks(self) -> list[Task]:
        """Build the sequential task chain for the crew."""

        task_market_analysis = Task(
            description=(
                f"Perform a comprehensive market analysis for {self.pair}.\n\n"
                f"Execute these steps IN ORDER:\n"
                f"1. Fetch current price for {self.pair}\n"
                f"2. Calculate technical indicators on the 1h timeframe\n"
                f"3. Calculate technical indicators on the 4h timeframe\n"
                f"4. Detect chart patterns\n"
                f"5. Find key support and resistance zones\n"
                f"6. Analyze volume profile\n"
                f"7. Check orderbook for buy/sell pressure\n"
                f"8. Check funding rate for positioning\n\n"
                f"Based on ALL the data gathered, produce a detailed analysis with:\n"
                f"- Overall trend direction and strength\n"
                f"- Key technical signals (bullish/bearish)\n"
                f"- Important support/resistance levels\n"
                f"- Volume and orderbook confirmation\n"
                f"- Your directional bias: LONG, SHORT, or NEUTRAL\n"
                f"- Confidence level (0-100)\n"
                f"- Suggested entry zone, stop loss level, and take profit targets"
            ),
            expected_output=(
                "A detailed market analysis report in JSON format containing: "
                "trend direction, key indicator values and signals, "
                "support/resistance levels, volume analysis, "
                "directional bias (LONG/SHORT/NEUTRAL), confidence (0-100), "
                "and suggested entry/exit levels."
            ),
            agent=self.market_agent,
        )

        task_sentiment = Task(
            description=(
                f"Assess the market sentiment for {self.pair}.\n\n"
                f"Execute these steps:\n"
                f"1. Check the Crypto Fear & Greed Index\n"
                f"2. Fetch and analyze recent crypto news for {self.pair}\n"
                f"3. Check social media sentiment and momentum\n"
                f"4. Analyze derivatives positioning (OI, long/short ratio)\n\n"
                f"Your previous colleague (Market Analysis Agent) has provided "
                f"a technical analysis. Consider whether sentiment ALIGNS with "
                f"or DIVERGES from the technical bias.\n\n"
                f"Produce a sentiment report with:\n"
                f"- Overall sentiment score and direction\n"
                f"- Key catalysts (positive or negative)\n"
                f"- Derivatives positioning and squeeze risk\n"
                f"- Alignment/divergence with technical analysis\n"
                f"- Sentiment-adjusted confidence modifier"
            ),
            expected_output=(
                "A sentiment analysis report in JSON format containing: "
                "overall sentiment (BULLISH/BEARISH/NEUTRAL), "
                "fear & greed reading, news sentiment summary, "
                "derivatives positioning, squeeze risk, "
                "and alignment with technical analysis."
            ),
            agent=self.sentiment_agent,
        )

        task_trading_ops = Task(
            description=(
                f"Make the FINAL trade decision for {self.pair}.\n\n"
                f"You have received reports from:\n"
                f"- Market Analysis Agent (technical analysis, entry/exit levels)\n"
                f"- Sentiment Agent (sentiment alignment, positioning)\n\n"
                f"Execute these steps:\n"
                f"1. Check current portfolio state (balance, positions, exposure)\n"
                f"2. If both agents suggest a directional trade, calculate position size "
                f"using Kelly Criterion based on historical performance\n"
                f"3. Calculate Value at Risk for the proposed position\n"
                f"4. Check correlation with any existing positions\n"
                f"5. Estimate expected slippage\n"
                f"6. Analyze market depth for execution feasibility\n\n"
                f"APPROVAL CRITERIA — ALL must be met:\n"
                f"- Confidence ≥ {settings.min_confidence}\n"
                f"- Risk:Reward ≥ {settings.min_rr_ratio}\n"
                f"- Stop loss distance ≤ {settings.max_sl_distance_pct}%\n"
                f"- Spread ≤ {settings.max_spread_bps} bps\n"
                f"- Slippage ≤ {settings.max_slippage_pct}%\n"
                f"- Available position slots\n"
                f"- Portfolio exposure within limits\n\n"
                f"Output a JSON object with this exact structure:\n"
                f'{{"decision": "APPROVED" or "REJECTED", '
                f'"pair": "{self.pair}", '
                f'"direction": "LONG" or "SHORT", '
                f'"confidence": <0-100>, '
                f'"position_size_usd": <amount>, '
                f'"position_size_pct": <percentage of balance>, '
                f'"entry": {{"method": "MARKET" or "LIMIT", "price": <price>, '
                f'"orders": [{{"price": <p>, "size": <s>}}]}}, '
                f'"stop_loss": {{"price": <p>, "pct": <distance%>, '
                f'"type": "STOP_LIMIT" or "STOP_MARKET"}}, '
                f'"take_profit": [{{"level": 1, "price": <p>, "size_pct": <50>}}, '
                f'{{"level": 2, "price": <p>, "size_pct": <50>}}], '
                f'"risk_reward_ratio": <ratio>, '
                f'"reasoning": "<explanation>", '
                f'"market_analysis_summary": "<brief summary>", '
                f'"sentiment_summary": "<brief summary>"}}'
            ),
            expected_output=(
                "A JSON object conforming to the TradeDecision schema with "
                "decision (APPROVED/REJECTED), pair, direction, confidence, "
                "position sizing, entry plan, stop loss, take profit levels, "
                "risk/reward ratio, and reasoning."
            ),
            agent=self.trading_ops_agent,
            output_json=TradeDecision,
        )

        return [task_market_analysis, task_sentiment, task_trading_ops]

    def _build_crew(self) -> Crew:
        """Build the CrewAI crew with memory enabled."""
        tasks = self._build_tasks()

        return Crew(
            agents=[self.market_agent, self.sentiment_agent, self.trading_ops_agent],
            tasks=tasks,
            process=Process.sequential,
            memory=True,
            verbose=settings.crew_verbose,
        )

    def run(self) -> Optional[TradeDecision]:
        """
        Run the full crew analysis pipeline.

        Returns:
            TradeDecision if successful, None if an error occurs.
        """
        try:
            logger.info(f"🚀 Starting crew analysis for {self.pair}")
            crew = self._build_crew()
            result = crew.kickoff(inputs={"pair": self.pair})

            # Store usage metrics for cost tracking
            self._usage_metrics = getattr(result, "token_usage", {})

            # Parse the structured output
            if hasattr(result, "pydantic") and result.pydantic:
                decision = result.pydantic
            elif hasattr(result, "json_dict") and result.json_dict:
                decision = TradeDecision(**result.json_dict)
            else:
                # Try to parse from raw output
                import json
                raw = str(result)
                # Find JSON in the output
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(raw[start:end])
                    decision = TradeDecision(**data)
                else:
                    logger.error(f"Could not parse crew output for {self.pair}")
                    return None

            logger.info(
                f"✅ Crew decision for {self.pair}: {decision.decision} "
                f"(direction={decision.direction}, confidence={decision.confidence})"
            )
            return decision

        except Exception as e:
            logger.error(f"❌ Crew analysis failed for {self.pair}: {e}")
            return None

    def get_usage_metrics(self) -> Dict[str, Any]:
        """Get token usage metrics from the last run."""
        return self._usage_metrics
