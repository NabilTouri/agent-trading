from abc import ABC, abstractmethod
from anthropic import Anthropic
from typing import Dict, Any
from loguru import logger
from core.config import settings
import time
import threading
from collections import deque


class BaseAgent(ABC):
    """Base class for all trading agents."""

    # Class-level rate limiter (shared across all agents)
    _api_calls: deque = deque(maxlen=100)
    _rate_lock = threading.Lock()
    _MAX_CALLS_PER_MINUTE = 50

    def __init__(self, name: str, model: str = "claude-sonnet-4-20250514"):
        self.name = name
        self.model = model
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        logger.info(f"Agent '{name}' initialized with model {model}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return agent-specific system prompt."""
        pass

    @abstractmethod
    def format_input(self, market_data: Dict[str, Any]) -> str:
        """Format input data for the agent."""
        pass

    @abstractmethod
    def parse_output(self, response: str) -> Dict[str, Any]:
        """Parse Claude response into structured format."""
        pass

    def _wait_for_rate_limit(self):
        """Check and wait if approaching rate limit."""
        with self._rate_lock:
            now = time.time()
            # Count calls in the last 60 seconds
            recent_calls = [t for t in self._api_calls if now - t < 60]

            if len(recent_calls) >= self._MAX_CALLS_PER_MINUTE:
                wait_time = 60 - (now - recent_calls[0])
                if wait_time > 0:
                    logger.warning(
                        f"⏳ {self.name}: Rate limit approaching "
                        f"({len(recent_calls)}/{self._MAX_CALLS_PER_MINUTE} calls/min), "
                        f"waiting {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)

            self._api_calls.append(time.time())

    def call_claude(
        self,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        """Call Claude API with retry logic and rate limiting."""
        system_prompt = self.get_system_prompt()

        # Rate limit check before calling
        self._wait_for_rate_limit()

        for attempt in range(3):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )

                return response.content[0].text

            except Exception as e:
                logger.error(f"{self.name} API error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main method: analyze data and return decision."""
        try:
            # Format input
            user_message = self.format_input(market_data)

            # Call Claude
            logger.info(f"{self.name} analyzing...")
            response = self.call_claude(user_message)

            # Parse output
            result = self.parse_output(response)
            result['agent'] = self.name
            result['raw_response'] = response

            logger.info(f"{self.name} decision: action={result.get('action', 'N/A')}, confidence={result.get('confidence', 0)}")
            return result

        except Exception as e:
            logger.error(f"{self.name} analysis failed: {e}")
            return {
                'agent': self.name,
                'action': 'HOLD',
                'confidence': 0,
                'reasoning': f"Error: {str(e)}",
                'error': True
            }