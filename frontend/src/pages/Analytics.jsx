import React from 'react'
import StatsPanel from '../components/StatsPanel'
import useSignals from '../hooks/useSignals'

export default function Analytics() {
  const { signals, stats } = useSignals()

  const bySymbol = signals.reduce((acc, s) => {
    acc[s.symbol] = acc[s.symbol] || { total: 0, wins: 0, losses: 0 }
    acc[s.symbol].total++
    if (s.result === 'win') acc[s.symbol].wins++
    if (s.result === 'loss') acc[s.symbol].losses++
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>
        Analytics
      </h1>
      <StatsPanel stats={stats} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Object.entries(bySymbol).map(([sym, data]) => {
          const wr = data.wins + data.losses > 0 ? (data.wins / (data.wins + data.losses)) * 100 : 0
          return (
            <div key={sym} className="rounded-lg p-6" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
              <div className="text-lg font-mono font-bold mb-4" style={{ color: '#c9a84c' }}>{sym}</div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="text-xs text-gray-500">Total</div>
                  <div className="font-mono text-xl">{data.total}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Wins</div>
                  <div className="font-mono text-xl text-green-400">{data.wins}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Win Rate</div>
                  <div className="font-mono text-xl" style={{ color: wr >= 50 ? '#22c55e' : '#ef4444' }}>
                    {wr.toFixed(0)}%
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div>
        <h2 className="font-display text-lg font-bold mb-4" style={{ color: '#c9a84c' }}>
          Signal Log
        </h2>
        <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #1a2030' }}>
          <table className="w-full text-sm font-mono">
            <thead>
              <tr style={{ background: '#0d1117', borderBottom: '1px solid #1a2030' }}>
                {['Symbol', 'Direction', 'Type', 'Score', 'Entry', 'Result', 'P&L', 'Date'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr
                  key={s.id}
                  style={{ background: i % 2 === 0 ? '#080b0f' : '#0d1117', borderBottom: '1px solid #1a2030' }}
                >
                  <td className="px-4 py-3">{s.symbol}</td>
                  <td className="px-4 py-3" style={{ color: s.direction === 'BUY' ? '#22c55e' : '#ef4444' }}>
                    {s.direction}
                  </td>
                  <td className="px-4 py-3 text-gray-400">{s.signal_type}</td>
                  <td className="px-4 py-3" style={{ color: '#c9a84c' }}>{s.score}/9</td>
                  <td className="px-4 py-3">${s.entry_price?.toLocaleString()}</td>
                  <td className="px-4 py-3" style={{ color: s.result === 'win' ? '#22c55e' : s.result === 'loss' ? '#ef4444' : '#666' }}>
                    {s.result || '—'}
                  </td>
                  <td className="px-4 py-3" style={{ color: (s.pnl_pips || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                    {s.pnl_pips ? `${s.pnl_pips > 0 ? '+' : ''}${s.pnl_pips}` : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
