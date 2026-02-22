"""
Sentiment Agent for CrewAI.

Market Sentiment Specialist who analyzes qualitative signals
from news, social media, derivatives positioning, and fear/greed metrics.
"""

from crewai import Agent

from tools.sentiment_tools import (
    get_fear_greed_index,
    get_crypto_news,
    get_social_sentiment,
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
        role="Market Sentiment Specialist",
        goal=(
            "Capture the directional sentiment and institutional positioning for the "
            "given trading pair. Your report must include: 1) Overall market sentiment "
            "(Fear & Greed trend), 2) News sentiment summary with key catalysts, "
            "3) Social media momentum and community activity, "
            "4) Derivatives positioning and squeeze risk assessment, "
            "5) Whether sentiment ALIGNS with or DIVERGES from any technical bias. "
            "State clearly if sentiment supports or contradicts a long/short thesis."
        ),
        backstory=(
            "You specialize in reading market sentiment from news, social media, "
            "and derivatives data. You have a talent for detecting when crowd "
            "positioning has become extreme (contrarian opportunities) and when "
            "positive news is already priced in. You provide an independent "
            "qualitative counterweight to the quantitative technical analysis. "
            "Your role is to prevent the team from taking trades that go against "
            "strong sentiment headwinds."
        ),
        llm=llm,
        tools=[
            get_fear_greed_index,
            get_crypto_news,
            get_social_sentiment,
            get_derivatives_positioning,
        ],
        verbose=False,
        allow_delegation=False,
        max_iter=8,
        max_retry_limit=2,
        respect_context_window=True,
        use_system_prompt=True,
    )
