from agents.base_agent import BaseAgent
from typing import Dict, Any
import json
import os
from core.config import settings


class MarketAnalysisAgent(BaseAgent):
    """Technical analysis agent using Claude Sonnet."""
    
    def __init__(self):
        super().__init__(name="MarketAnalysis", model=settings.market_analysis_model)
    
    def get_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "market_analysis.txt")
        with open(prompt_path, 'r') as f:
            return f.read()
    
    def format_input(self, market_data: Dict[str, Any]) -> str:
        """Format technical data for Claude."""
        candles_15m = market_data.get('candles_15m', [])
        indicators = market_data.get('indicators', {})
        
        return f"""
MARKET DATA for {market_data['pair']}:

CURRENT PRICE: ${market_data.get('current_price', 0):.2f}

RECENT CANDLES (15m, last 10):
{self._format_candles(candles_15m[:10])}

TECHNICAL INDICATORS (1h timeframe):
- RSI: {indicators.get('rsi', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')} (signal: {indicators.get('macd_signal', 'N/A')})
- Bollinger Bands: Upper {indicators.get('bb_upper', 'N/A')}, Lower {indicators.get('bb_lower', 'N/A')}
- ATR: {indicators.get('atr', 'N/A')}
- Volume 24h: {market_data.get('volume_24h', 'N/A')}

PRICE CHANGES:
- 1h: {market_data.get('change_1h', 0)}%
- 4h: {market_data.get('change_4h', 0)}%
- 24h: {market_data.get('change_24h', 0)}%

VOLATILITY: {market_data.get('volatility', 'UNKNOWN')}

Analyze and provide trading recommendation in JSON format.
"""
    
    def _format_candles(self, candles: list) -> str:
        """Format candles for display."""
        if not candles:
            return "  No candle data available"
        
        lines = []
        for c in candles:
            lines.append(
                f"  O:{c.get('open', 0):.2f} H:{c.get('high', 0):.2f} "
                f"L:{c.get('low', 0):.2f} C:{c.get('close', 0):.2f} V:{c.get('volume', 0):.0f}"
            )
        return "\n".join(lines)
    
    def parse_output(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from Claude."""
        try:
            # Remove any markdown formatting
            clean_response = response.strip()
            if clean_response.startswith("```"):
                lines = clean_response.split("\n")
                # Remove first and last lines (```json and ```)
                clean_response = "\n".join(lines[1:-1])
            
            result = json.loads(clean_response)
            
            # Validate required fields
            assert result.get('action') in ['BUY', 'SELL', 'HOLD']
            assert 0 <= result.get('confidence', 0) <= 100
            assert isinstance(result.get('reasoning', ''), str)
            
            return result
        
        except Exception as e:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reasoning': f"Parse error: {str(e)}. Raw: {response[:200]}",
                'key_levels': {'support': 0, 'resistance': 0},
                'market_regime': 'unknown',
                'error': True
            }
