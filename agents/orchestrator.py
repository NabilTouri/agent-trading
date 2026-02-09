from agents.base_agent import BaseAgent
from typing import Dict, Any
import json
import os


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent using Claude Haiku for Phase 1 (cost-effective)."""
    
    def __init__(self):
        # Phase 1: use Haiku for low cost
        super().__init__(name="Orchestrator", model="claude-3-5-haiku-20241022")
    
    def get_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "orchestrator.txt")
        with open(prompt_path, 'r') as f:
            return f.read()
    
    def format_input(self, agent_results: Dict[str, Any]) -> str:
        """Format results from 2 agents (NO sentiment in Phase 1)."""
        return f"""
AGENT RECOMMENDATIONS for {agent_results['pair']}:

MARKET ANALYSIS AGENT:
{json.dumps(agent_results.get('market_analysis', {}), indent=2)}

RISK MANAGEMENT AGENT:
{json.dumps(agent_results.get('risk_management', {}), indent=2)}

CURRENT CONTEXT:
- Account Balance: ${agent_results.get('account_balance', 0):.2f}
- Open Positions: {agent_results.get('open_positions', 0)}
- Recent Win Rate: {agent_results.get('win_rate', 0):.1f}%

Make FINAL decision. Respond in JSON format.
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
            assert result.get('final_action') in ['BUY', 'SELL', 'HOLD']
            assert 0 <= result.get('confidence', 0) <= 100
            assert result.get('risk_level') in ['LOW', 'MEDIUM', 'HIGH']
            
            return result
        
        except Exception as e:
            return {
                'final_action': 'HOLD',
                'confidence': 0,
                'reasoning': f"Parse error: {str(e)}",
                'risk_level': 'HIGH',
                'overrides': [],
                'error': True
            }
    
    def make_decision(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Main orchestration method."""
        return self.analyze(agent_results)
