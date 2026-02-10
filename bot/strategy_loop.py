import asyncio
from loguru import logger
from datetime import datetime
from core.config import settings
from core.database import db
from core.exchange import exchange
from core.models import Signal, ActionType
from agents.market_analysis import MarketAnalysisAgent
from agents.risk_management import RiskManagementAgent
from agents.orchestrator import OrchestratorAgent
from services.telegram_bot import telegram_notifier
from core.data_pipeline import DataPipeline


class StrategyLoop:
    """Strategy loop: Phase 1 with 3 agents (no sentiment)."""
    
    def __init__(self):
        self.interval = settings.strategy_interval_minutes * 60  # to seconds
        self.market_agent = MarketAnalysisAgent()
        # NO sentiment agent in Phase 1
        self.risk_agent = RiskManagementAgent()
        self.orchestrator = OrchestratorAgent()
        self.data_pipeline = DataPipeline()
        
        logger.info(f"StrategyLoop PHASE 1 initialized (3 agents: Market, Risk, Orchestrator)")
        logger.info(f"Interval: {self.interval}s ({settings.strategy_interval_minutes}min)")
    
    async def run(self):
        """Main loop."""
        # Initial delay to let system stabilize
        await asyncio.sleep(5)
        
        while True:
            try:
                logger.info("=" * 50)
                logger.info(f"STRATEGY CYCLE START - {datetime.now()}")
                
                # Analyze each trading pair
                for pair in settings.pairs_list:
                    await self.analyze_pair(pair)
                
                logger.info(f"STRATEGY CYCLE END - sleeping {self.interval}s")
                logger.info("=" * 50)
                
            except Exception as e:
                logger.error(f"Strategy loop error: {e}")
            
            await asyncio.sleep(self.interval)
    
    async def analyze_pair(self, pair: str):
        """Analyze with 2 agents + orchestrator (NO sentiment in Phase 1)."""
        logger.info(f"Analyzing {pair}...")
        
        try:
            # 1. Fetch market data (no news in Phase 1)
            market_data = await self.data_pipeline.fetch_market_data(pair)
            
            # 2. Market Analysis Agent
            market_result = await asyncio.to_thread(
                self.market_agent.analyze, 
                market_data
            )
            
            # 3. Risk Management Agent
            risk_data = {
                **market_data,
                'proposed_action': market_result.get('action', 'HOLD'),
                'analysis_confidence': market_result.get('confidence', 0),
                'account_balance': db.get_current_capital(),
                'open_positions_count': len(db.get_all_open_positions()),
                'drawdown': self._calculate_drawdown(),
                'win_rate': db.calculate_metrics()['win_rate'],
                'avg_profit': db.calculate_metrics()['avg_profit'],
                'avg_loss': db.calculate_metrics()['avg_loss']
            }
            
            risk_result = await asyncio.to_thread(
                self.risk_agent.analyze, 
                risk_data
            )
            
            # 4. Orchestrator (2 inputs only - no sentiment in Phase 1)
            orchestrator_input = {
                'pair': pair,
                'market_analysis': market_result,
                'risk_management': risk_result,
                # NO 'sentiment' in Phase 1
                'account_balance': risk_data['account_balance'],
                'open_positions': risk_data['open_positions_count'],
                'win_rate': risk_data['win_rate']
            }
            
            final_decision = await asyncio.to_thread(
                self.orchestrator.make_decision,
                orchestrator_input
            )
            
            # 5. Create signal
            signal = Signal(
                pair=pair,
                action=ActionType(final_decision.get('final_action', 'HOLD')),
                confidence=final_decision.get('confidence', 0),
                reasoning=final_decision.get('reasoning', ''),
                agent_votes={
                    'market_analysis': market_result.get('action', 'HOLD'),
                    # 'sentiment': NOT in Phase 1
                    'risk_management': risk_result.get('action', 'REJECT'),
                    'orchestrator': final_decision.get('final_action', 'HOLD')
                },
                market_data={
                    'price': market_data.get('current_price', 0),
                    'rsi': market_data.get('indicators', {}).get('rsi', 0),
                    'stop_loss': risk_result.get('stop_loss', 0),
                    'take_profit': risk_result.get('take_profit', 0),
                    'position_size': risk_result.get('position_size_usd', 0)
                }
            )
            
            # 6. Save signal
            db.save_signal(signal)
            
            logger.info(
                f"Signal generated for {pair}: {signal.action} "
                f"(confidence: {signal.confidence}%)"
            )
            
            # 7. Notify if strong signal
            if signal.confidence >= 70 and signal.action != ActionType.HOLD:
                await self._notify_signal(signal)
        
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        current_capital = exchange.get_account_balance()
        initial_capital = db.get_initial_capital()
        
        if initial_capital == 0 or current_capital >= initial_capital:
            return 0.0
        
        return ((initial_capital - current_capital) / initial_capital) * 100
    
    async def _notify_signal(self, signal: Signal):
        """Send Telegram notification for strong signal."""
        emoji = "🟢" if signal.action == ActionType.BUY else "🔴"
        
        message = f"""
{emoji} <b>SIGNAL: {signal.action}</b>

Pair: {signal.pair}
Confidence: {signal.confidence}%
Price: ${signal.market_data.get('price', 0):.2f}

<i>{signal.reasoning[:200]}...</i>

Agent Votes:
- Market: {signal.agent_votes.get('market_analysis', 'N/A')}
- Risk: {signal.agent_votes.get('risk_management', 'N/A')}
"""
        
        await telegram_notifier.send_message(message)
