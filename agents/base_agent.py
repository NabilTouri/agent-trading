from abc import ABC, abstractmethod
from typing import Dict, Any
from anthropic import Anthropic
from loguru import logger
from core.config import settings
import time


class BaseAgent(ABC):
    """Base class for all trading agents."""
    
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
    
    def call_claude(
        self,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> str:
        """Call Claude API with retry logic."""
        system_prompt = self.get_system_prompt()
        
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
