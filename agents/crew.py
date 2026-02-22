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
                f"Analyze {self.pair}. Use tools: calculate_indicators (1h only), "
                f"detect_chart_patterns, find_support_resistance, get_orderbook, get_funding_rate. "
                f"Output a SHORT JSON: bias (LONG/SHORT/NEUTRAL), confidence (0-100), "
                f"key support/resistance, entry zone, stop loss, take profit."
            ),
            expected_output=(
                "Short JSON: bias, confidence, support, resistance, entry, stop_loss, take_profit."
            ),
            agent=self.market_agent,
        )

        task_sentiment = Task(
            description=(
                f"Assess sentiment for {self.pair}. Use tools: get_fear_greed_index, "
                f"get_crypto_news, get_derivatives_positioning. Skip social_sentiment. "
                f"Output SHORT JSON: sentiment (BULL/BEAR/NEUTRAL), "
                f"aligns_with_technical (true/false), key_catalyst, squeeze_risk."
            ),
            expected_output=(
                "Short JSON: sentiment, aligns_with_technical, key_catalyst, squeeze_risk."
            ),
            agent=self.sentiment_agent,
        )

        task_trading_ops = Task(
            description=(
                f"Final decision for {self.pair}. Use tools: get_portfolio_state, estimate_slippage. "
                f"Only use calculate_kelly and calculate_var if APPROVING a trade. "
                f"REJECT if confidence < {settings.min_confidence} or RR < {settings.min_rr_ratio}. "
                f"Output JSON: decision, pair, direction, confidence, position_size_usd, "
                f"position_size_pct, entry (method+price), stop_loss (price+pct+type), "
                f"take_profit (array), risk_reward_ratio, reasoning."
            ),
            expected_output=(
                "JSON: decision, pair, direction, confidence, sizing, entry, SL, TP, RR, reasoning."
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
            embedder={
                "provider": "sentence-transformer",
                "config": {
                    "model_name": "all-MiniLM-L6-v2",
                    "device": "cpu",
                },
            },
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
