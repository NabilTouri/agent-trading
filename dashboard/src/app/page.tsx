'use client'

import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

// In production (standalone Docker), NEXT_PUBLIC_API_URL points to the API server.
// In dev mode, Next.js rewrites handle /api/* proxying, so empty string works.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

interface Metrics {
    capital: {
        current: number
        initial: number
        pnl: number
        pnl_percent: number
    }
    performance: {
        total_trades: number
        win_rate: number
        profit_factor: number
        total_pnl: number
    }
    positions: {
        open: number
        max: number
    }
    config: {
        testnet: boolean
        trading_pairs: string[]
    }
}

interface Position {
    position_id: string
    pair: string
    side: string
    entry_price: number
    current_price: number
    size: number
    unrealized_pnl: number
    unrealized_pnl_percent: number
}

interface Signal {
    pair: string
    action: string
    confidence: number
    reasoning: string
    timestamp: string
}

export default function Dashboard() {
    const { data: metrics, isLoading: metricsLoading } = useQuery<Metrics>({
        queryKey: ['metrics'],
        queryFn: async () => {
            const res = await axios.get(`${API_BASE}/api/system/metrics`)
            return res.data
        },
        refetchInterval: 30000,
    })

    const { data: positions, isLoading: positionsLoading } = useQuery<Position[]>({
        queryKey: ['positions'],
        queryFn: async () => {
            const res = await axios.get(`${API_BASE}/api/positions/current`)
            return res.data
        },
        refetchInterval: 30000,
    })

    const { data: signals, isLoading: signalsLoading } = useQuery<Signal[]>({
        queryKey: ['signals'],
        queryFn: async () => {
            const res = await axios.get(`${API_BASE}/api/signals/history?limit=50`)
            return res.data
        },
        refetchInterval: 60000,
    })

    const { data: status } = useQuery({
        queryKey: ['status'],
        queryFn: async () => {
            const res = await axios.get(`${API_BASE}/api/system/status`)
            return res.data
        },
        refetchInterval: 30000,
    })

    const isOnline = status?.redis === 'connected' && status?.binance === 'connected'

    return (
        <div className="container">
            <header className="header">
                <h1>🤖 AI Trading Bot</h1>
                <div className="header-right">
                    <span className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
                        {isOnline ? '● Online' : '○ Offline'}
                    </span>
                    {metrics?.config?.testnet && (
                        <span className="status-badge" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', marginLeft: '10px' }}>
                            TESTNET
                        </span>
                    )}
                </div>
            </header>

            <div className="grid">
                {/* Capital Card */}
                <div className="card">
                    <h2>Capital</h2>
                    {metricsLoading ? (
                        <div className="loading">Loading...</div>
                    ) : (
                        <div className="metric">
                            <span className="metric-value">${metrics?.capital.current?.toFixed(2) || '0.00'}</span>
                            <span className={`metric-change ${(metrics?.capital.pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
                                {(metrics?.capital.pnl || 0) >= 0 ? '+' : ''}${metrics?.capital.pnl?.toFixed(2) || '0.00'}
                                ({(metrics?.capital.pnl_percent || 0) >= 0 ? '+' : ''}{metrics?.capital.pnl_percent?.toFixed(2) || '0.00'}%)
                            </span>
                            <span className="metric-label">Initial: ${metrics?.capital.initial?.toFixed(2) || '0.00'}</span>
                        </div>
                    )}
                </div>

                {/* Performance Card */}
                <div className="card">
                    <h2>Performance</h2>
                    {metricsLoading ? (
                        <div className="loading">Loading...</div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                            <div className="metric">
                                <span className="metric-value">{metrics?.performance.total_trades || 0}</span>
                                <span className="metric-label">Total Trades</span>
                            </div>
                            <div className="metric">
                                <span className="metric-value">{metrics?.performance.win_rate?.toFixed(1) || '0'}%</span>
                                <span className="metric-label">Win Rate</span>
                            </div>
                            <div className="metric">
                                <span className="metric-value">{metrics?.performance.profit_factor?.toFixed(2) || '0'}</span>
                                <span className="metric-label">Profit Factor</span>
                            </div>
                            <div className="metric">
                                <span className={`metric-value ${(metrics?.performance.total_pnl || 0) >= 0 ? 'positive' : 'negative'}`}>
                                    ${metrics?.performance.total_pnl?.toFixed(2) || '0.00'}
                                </span>
                                <span className="metric-label">Total PnL</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Positions Card */}
                <div className="card">
                    <h2>Open Positions ({metrics?.positions.open || 0}/{metrics?.positions.max || 3})</h2>
                    {positionsLoading ? (
                        <div className="loading">Loading...</div>
                    ) : positions && positions.length > 0 ? (
                        <div className="positions-list">
                            {positions.map((pos) => (
                                <div key={pos.position_id} className="position-item">
                                    <div>
                                        <span className="position-pair">{pos.pair}</span>
                                        <span className={`position-side ${pos.side.toLowerCase()}`} style={{ marginLeft: '10px' }}>
                                            {pos.side}
                                        </span>
                                    </div>
                                    <div className="position-pnl">
                                        <div className={pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
                                            {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl?.toFixed(2)}
                                        </div>
                                        <div className="metric-label">
                                            Entry: ${pos.entry_price?.toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="empty-state">No open positions</div>
                    )}
                </div>
            </div>

            {/* Signals Card - Full Width */}
            <div className="card">
                <h2>Signals History ({signals?.length || 0})</h2>
                {signalsLoading ? (
                    <div className="loading">Loading...</div>
                ) : signals && signals.length > 0 ? (
                    <div className="signals-list" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                        {signals.map((signal, idx) => (
                            <div key={idx} className="signal-item">
                                <div className="signal-header">
                                    <span>
                                        <span className={`signal-action ${signal.action.toLowerCase()}`}>
                                            {signal.action}
                                        </span>
                                        <span style={{ marginLeft: '10px', color: '#888' }}>{signal.pair}</span>
                                    </span>
                                    <span className="signal-confidence">
                                        {signal.confidence}% confidence
                                    </span>
                                </div>
                                <p className="signal-reasoning">
                                    {signal.reasoning?.substring(0, 150)}...
                                </p>
                                <span className="metric-label">
                                    {new Date(signal.timestamp).toLocaleString()}
                                </span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="empty-state">No signals yet</div>
                )}
            </div>
        </div>
    )
}
