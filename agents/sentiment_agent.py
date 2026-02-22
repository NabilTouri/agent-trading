"""
Sentiment Agent for CrewAI.

Market Sentiment Specialist who analyzes qualitative signals
from news, social media, derivatives positioning, and fear/greed metrics.
"""

from crewai import Agent

from tools.sentiment_tools import (
    get_fear_greed_index,
    get_crypto_news,
    get_derivatives_positioning,
)


def create_sentiment_agent(llm: str) -> Agent:
    """
    Create the Sentiment Analysis agent.

    This agent provides a qualitative counterweight to the Market Analysis Agent:
    - Crypto Fear & Greed Index with trend analysis
    - Latest news headlines with sentiment classification
    - Social media momentum (Reddit, Twitter)
    - Derivatives positioning (OI, long/short ratio, squeeze risk)

    The sentiment agent's conclusions help confirm or challenge
    the technical analysis, adding an independent signal dimension.

    Args:
        llm: LLM identifier string in LiteLLM format

    Returns:
        CrewAI Agent configured for sentiment analysis
    """
    return Agent(
        role="Sentiment Analyst",
        goal="Assess market sentiment via Fear/Greed, news, derivatives. Output SHORT JSON.",
        backstory="Sentiment specialist for crypto. Detects crowded positioning and contrarian signals.",
        llm=llm,
        tools=[
            get_fear_greed_index,
            get_crypto_news,
            get_derivatives_positioning,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=5,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
