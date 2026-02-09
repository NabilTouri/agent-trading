"""
Test suite for trading agents.
"""

import pytest
from unittest.mock import Mock, patch
import json


class TestMarketAnalysisAgent:
    """Tests for MarketAnalysisAgent."""
    
    def test_format_input(self):
        """Test input formatting."""
        from agents.market_analysis import MarketAnalysisAgent
        
        agent = MarketAnalysisAgent()
        
        market_data = {
            'pair': 'BTC/USDT',
            'current_price': 50000.0,
            'candles_15m': [
                {'open': 49900, 'high': 50100, 'low': 49800, 'close': 50000, 'volume': 1000}
            ],
            'indicators': {
                'rsi': 55.0,
                'macd': 100.0,
                'macd_signal': 80.0,
                'bb_upper': 51000.0,
                'bb_lower': 49000.0,
                'atr': 500.0
            },
            'volume_24h': 1000000,
            'change_1h': 0.5,
            'change_4h': 1.2,
            'change_24h': 2.5,
            'volatility': 'MEDIUM'
        }
        
        result = agent.format_input(market_data)
        
        assert 'BTC/USDT' in result
        assert '50000' in result
        assert 'RSI: 55.0' in result
    
    def test_parse_output_valid(self):
        """Test valid JSON parsing."""
        from agents.market_analysis import MarketAnalysisAgent
        
        agent = MarketAnalysisAgent()
        
        response = json.dumps({
            'action': 'BUY',
            'confidence': 75,
            'reasoning': 'Strong uptrend',
            'key_levels': {'support': 49000, 'resistance': 51000},
            'market_regime': 'trending_up'
        })
        
        result = agent.parse_output(response)
        
        assert result['action'] == 'BUY'
        assert result['confidence'] == 75
        assert 'error' not in result
    
    def test_parse_output_invalid(self):
        """Test invalid JSON parsing fallback."""
        from agents.market_analysis import MarketAnalysisAgent
        
        agent = MarketAnalysisAgent()
        
        result = agent.parse_output("invalid json")
        
        assert result['action'] == 'HOLD'
        assert result['confidence'] == 0
        assert result.get('error') is True


class TestRiskManagementAgent:
    """Tests for RiskManagementAgent."""
    
    def test_parse_output_valid(self):
        """Test valid risk assessment parsing."""
        from agents.risk_management import RiskManagementAgent
        
        agent = RiskManagementAgent()
        
        response = json.dumps({
            'action': 'APPROVE',
            'position_size_usd': 60.0,
            'stop_loss': 49000.0,
            'take_profit': 52000.0,
            'risk_reward_ratio': 2.0,
            'confidence': 80,
            'reasoning': 'Risk within parameters'
        })
        
        result = agent.parse_output(response)
        
        assert result['action'] == 'APPROVE'
        assert result['position_size_usd'] == 60.0
        assert result['stop_loss'] == 49000.0
    
    def test_parse_output_reject(self):
        """Test risk rejection."""
        from agents.risk_management import RiskManagementAgent
        
        agent = RiskManagementAgent()
        
        result = agent.parse_output("invalid")
        
        assert result['action'] == 'REJECT'
        assert result['position_size_usd'] == 0


class TestOrchestratorAgent:
    """Tests for OrchestratorAgent."""
    
    def test_parse_output_valid(self):
        """Test orchestrator decision parsing."""
        from agents.orchestrator import OrchestratorAgent
        
        agent = OrchestratorAgent()
        
        response = json.dumps({
            'final_action': 'BUY',
            'confidence': 70,
            'reasoning': 'All agents agree on bullish signal',
            'risk_level': 'MEDIUM',
            'overrides': []
        })
        
        result = agent.parse_output(response)
        
        assert result['final_action'] == 'BUY'
        assert result['confidence'] == 70
        assert result['risk_level'] == 'MEDIUM'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
