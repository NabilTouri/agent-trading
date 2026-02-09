from agents.base_agent import BaseAgent
from typing import Dict, Any
import json
import os


class RiskManagementAgent(BaseAgent):
    """Risk management agent using Claude Sonnet."""
    
    def __init__(self):
        super().__init__(name="RiskManagement", model="claude-sonnet-4-20250514")
    
    def get_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "risk_management.txt")
        with open(prompt_path, 'r') as f:
            return f.read()
    
    def format_input(self, market_data: Dict[str, Any]) -> str:
        """Format risk data for Claude."""
        return f"""
RISK ASSESSMENT REQUEST for {market_data['pair']}:

ACCOUNT STATUS:
- Current Balance: ${market_data.get('account_balance', 0):.2f}
- Risk per Trade: {market_data.get('risk_per_trade', 0.02) * 100}%
- Open Positions: {market_data.get('open_positions_count', 0)}
- Current Drawdown: {market_data.get('drawdown', 0):.1f}%

PROPOSED TRADE:
- Direction: {market_data.get('proposed_action', 'N/A')}
- Entry Price: ${market_data.get('entry_price', 0):.2f}
- Market Analysis Confidence: {market_data.get('analysis_confidence', 0)}%

MARKET CONDITIONS:
- ATR (14): {market_data.get('atr', 0)}
- Volatility: {market_data.get('volatility', 'UNKNOWN')}
- Current Price: ${market_data.get('current_price', 0):.2f}

RECENT PERFORMANCE:
- Last 30 trades Win Rate: {market_data.get('win_rate', 0):.1f}%
- Average Profit: ${market_data.get('avg_profit', 0):.2f}
- Average Loss: ${market_data.get('avg_loss', 0):.2f}

Calculate position size and risk parameters. Respond in JSON format.
"""
    
    def parse_output(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from Claude."""
        try:
            clean_response = response.strip()
            if clean_response.startswith("```"):
                lines = clean_response.split("\n")
                clean_response = "\n".join(lines[1:-1])
            
            result = json.loads(clean_response)
            
            # Validate required fields
            assert result.get('action') in ['APPROVE', 'REJECT', 'REDUCE_SIZE']
            assert 0 <= result.get('confidence', 0) <= 100
            
            # Ensure numeric fields
            result['position_size_usd'] = float(result.get('position_size_usd', 0))
            result['stop_loss'] = float(result.get('stop_loss', 0))
            result['take_profit'] = float(result.get('take_profit', 0))
            result['risk_reward_ratio'] = float(result.get('risk_reward_ratio', 0))
            
            return result
        
        except Exception as e:
            return {
                'action': 'REJECT',
                'position_size_usd': 0,
                'stop_loss': 0,
                'take_profit': 0,
                'risk_reward_ratio': 0,
                'confidence': 0,
                'reasoning': f"Parse error: {str(e)}",
                'error': True
            }
