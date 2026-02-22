"""
Test suite for CrewAI trading agents.
Validates agent creation via factory functions, tool assignment, and crew assembly.

NOTE: These tests mock crewai's LLM creation because crewai[anthropic] is not
installed in the test environment. The mocks allow Agent objects to be created
without actually connecting to an LLM provider.
"""

import pytest
from unittest.mock import patch, MagicMock

# LLM string used for testing - not actually called
_TEST_LLM = "anthropic/claude-sonnet-4-20250514"


@pytest.fixture(autouse=True)
def _mock_crewai_llm():
    """Mock crewai's LLM creation so Agent() doesn't require real provider."""
    with patch("crewai.agent.core.create_llm", return_value=MagicMock()):
        yield


class TestMarketAnalysisAgent:
    """Tests for the Market Analysis CrewAI Agent."""

    def test_agent_creation(self):
        """Agent should be created with correct role and goal."""
        from agents.market_analysis_agent import create_market_analysis_agent

        agent = create_market_analysis_agent(_TEST_LLM)
        assert agent.role is not None
        assert "market" in agent.role.lower() or "analyst" in agent.role.lower()

    def test_agent_has_tools(self):
        """Agent should have technical analysis and market data tools."""
        from agents.market_analysis_agent import create_market_analysis_agent

        agent = create_market_analysis_agent(_TEST_LLM)
        assert len(agent.tools) > 0
        tool_names = [t.name for t in agent.tools]
        assert "calculate_indicators" in tool_names
        assert "get_orderbook" in tool_names
        assert "get_current_price" in tool_names

    def test_agent_has_correct_tool_count(self):
        """Market Analysis Agent should have exactly 8 tools."""
        from agents.market_analysis_agent import create_market_analysis_agent

        agent = create_market_analysis_agent(_TEST_LLM)
        assert len(agent.tools) == 8


class TestSentimentAgent:
    """Tests for the Sentiment Analysis CrewAI Agent."""

    def test_agent_creation(self):
        """Agent should be created with correct role."""
        from agents.sentiment_agent import create_sentiment_agent

        agent = create_sentiment_agent(_TEST_LLM)
        assert agent.role is not None
        assert "sentiment" in agent.role.lower()

    def test_agent_has_tools(self):
        """Agent should have sentiment-focused tools."""
        from agents.sentiment_agent import create_sentiment_agent

        agent = create_sentiment_agent(_TEST_LLM)
        assert len(agent.tools) > 0
        tool_names = [t.name for t in agent.tools]
        assert "get_fear_greed_index" in tool_names
        assert "get_crypto_news" in tool_names

    def test_agent_has_correct_tool_count(self):
        """Sentiment Agent should have exactly 4 tools."""
        from agents.sentiment_agent import create_sentiment_agent

        agent = create_sentiment_agent(_TEST_LLM)
        assert len(agent.tools) == 4


class TestTradingOpsAgent:
    """Tests for the Trading Operations CrewAI Agent."""

    def test_agent_creation(self):
        """Agent should be created with correct role."""
        from agents.trading_ops_agent import create_trading_ops_agent

        agent = create_trading_ops_agent(_TEST_LLM)
        assert agent.role is not None

    def test_agent_has_tools(self):
        """Agent should have risk management tools."""
        from agents.trading_ops_agent import create_trading_ops_agent

        agent = create_trading_ops_agent(_TEST_LLM)
        assert len(agent.tools) > 0
        tool_names = [t.name for t in agent.tools]
        assert "get_portfolio_state" in tool_names
        assert "calculate_kelly_position_size" in tool_names

    def test_agent_has_correct_tool_count(self):
        """Trading Ops Agent should have exactly 6 tools."""
        from agents.trading_ops_agent import create_trading_ops_agent

        agent = create_trading_ops_agent(_TEST_LLM)
        assert len(agent.tools) == 6


class TestTradingCrew:
    """Tests for the TradingCrew assembly."""

    def test_crew_init(self):
        """TradingCrew should initialize with a pair."""
        from agents.crew import TradingCrew

        crew = TradingCrew("BTC/USDT")
        assert crew.pair == "BTC/USDT"

    def test_crew_builds_tasks(self):
        """TradingCrew should build 3 sequential tasks."""
        from agents.crew import TradingCrew

        crew = TradingCrew("ETH/USDT")
        tasks = crew._build_tasks()
        assert len(tasks) == 3

    def test_crew_agents(self):
        """TradingCrew should have 3 agents."""
        from agents.crew import TradingCrew

        crew = TradingCrew("BTC/USDT")
        agents = [crew.market_agent, crew.sentiment_agent, crew.trading_ops_agent]
        assert len(agents) == 3
        assert all(a is not None for a in agents)

    def test_get_usage_metrics_before_run(self):
        """Usage metrics should be empty dict before run."""
        from agents.crew import TradingCrew

        crew = TradingCrew("BTC/USDT")
        metrics = crew.get_usage_metrics()
        assert metrics == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
