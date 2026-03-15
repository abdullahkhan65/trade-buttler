import React, { useState, useEffect } from 'react'

export default function Header({ engineStatus }) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const statusColor = {
    live: '#22c55e',
    offline: '#ef4444',
    connecting: '#f59e0b',
  }[engineStatus] || '#f59e0b'

  return (
    <header style={{ background: '#0d1117', borderBottom: '1px solid #1a2030' }}>
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-2xl">⚡</div>
          <div>
            <h1 className="font-display text-xl font-bold" style={{ color: '#c9a84c' }}>
              Trade Buttler
            </h1>
            <div className="text-xs text-gray-500 font-mono">XAU/USD · BTC/USD Signal Engine</div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Engine Status */}
          <div className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full pulse-dot"
              style={{ background: statusColor, boxShadow: `0 0 8px ${statusColor}` }}
            />
            <span className="text-xs font-mono" style={{ color: statusColor }}>
              {engineStatus.toUpperCase()}
            </span>
          </div>

          {/* Clock */}
          <div className="text-right">
            <div className="font-mono text-sm text-gray-300">
              {time.toLocaleTimeString('en-US', { hour12: false })}
            </div>
            <div className="font-mono text-xs text-gray-600">
              {time.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
