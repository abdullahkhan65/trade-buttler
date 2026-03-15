import React from 'react'

export default function StatsPanel({ stats }) {
  if (!stats) return null

  const items = [
    { label: 'Total Signals', value: stats.total_signals, color: '#c9a84c' },
    { label: 'Win Rate', value: `${stats.win_rate}%`, color: stats.win_rate >= 50 ? '#22c55e' : '#ef4444' },
    { label: 'Wins', value: stats.wins, color: '#22c55e' },
    { label: 'Losses', value: stats.losses, color: '#ef4444' },
    { label: 'Total P&L', value: stats.total_pnl >= 0 ? `+${stats.total_pnl}` : stats.total_pnl, color: stats.total_pnl >= 0 ? '#22c55e' : '#ef4444' },
  ]

  return (
    <div className="grid grid-cols-5 gap-3">
      {items.map(({ label, value, color }) => (
        <div
          key={label}
          className="rounded-lg p-4"
          style={{ background: '#0d1117', border: '1px solid #1a2030' }}
        >
          <div className="text-xs text-gray-500 font-mono mb-1">{label}</div>
          <div className="font-mono text-xl font-bold" style={{ color }}>
            {value}
          </div>
        </div>
      ))}
    </div>
  )
}
