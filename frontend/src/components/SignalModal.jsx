import React, { useState } from 'react'

export default function SignalModal({ signal, onClose, onRecord }) {
  const [recording, setRecording] = useState(false)
  const [result, setResult] = useState('')
  const [pnl, setPnl] = useState('')

  const isBuy = signal.direction === 'BUY'
  const dirColor = isBuy ? '#22c55e' : '#ef4444'
  const rr = Math.abs(signal.take_profit - signal.entry_price) / Math.abs(signal.stop_loss - signal.entry_price)

  const handleRecord = async () => {
    if (!result) return
    setRecording(true)
    try {
      await onRecord(signal.id, result, parseFloat(pnl) || null)
      onClose()
    } finally {
      setRecording(false)
    }
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4"
      style={{ background: 'rgba(0,0,0,0.8)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl overflow-hidden"
        style={{ background: '#0d1117', border: `1px solid ${dirColor}44` }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="px-6 py-4 flex items-center justify-between"
          style={{ background: dirColor + '11', borderBottom: `1px solid ${dirColor}22` }}
        >
          <div className="flex items-center gap-3">
            <span
              className="px-2 py-1 rounded text-xs font-bold"
              style={{ background: dirColor + '22', color: dirColor }}
            >
              {signal.direction}
            </span>
            <div>
              <div className="font-mono font-bold">{signal.symbol}</div>
              <div className="text-xs text-gray-500">{signal.signal_type?.toUpperCase()}</div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">×</button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {/* Prices */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Entry', value: signal.entry_price, color: '#c9a84c' },
              { label: 'Stop Loss', value: signal.stop_loss, color: '#ef4444' },
              { label: 'Take Profit', value: signal.take_profit, color: '#22c55e' },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded p-3" style={{ background: '#1a2030' }}>
                <div className="text-xs text-gray-500">{label}</div>
                <div className="font-mono font-bold" style={{ color }}>${value?.toLocaleString()}</div>
              </div>
            ))}
          </div>

          {/* R:R */}
          <div className="rounded p-3 text-center" style={{ background: '#1a2030' }}>
            <span className="text-xs text-gray-500 mr-2">R:R Ratio</span>
            <span className="font-mono font-bold" style={{ color: '#c9a84c' }}>1:{rr.toFixed(1)}</span>
            <span className="mx-4 text-gray-600">|</span>
            <span className="text-xs text-gray-500 mr-2">Score</span>
            <span className="font-mono font-bold" style={{ color: '#c9a84c' }}>{signal.score}/9</span>
          </div>

          {/* Reasons */}
          <div>
            <div className="text-xs text-gray-500 mb-2">Confluence Factors</div>
            <ul className="space-y-1">
              {(signal.reasons || []).map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span style={{ color: '#c9a84c' }}>›</span>
                  <span className="text-gray-300">{r}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Record Result */}
          {!signal.result && (
            <div className="border-t pt-4" style={{ borderColor: '#1a2030' }}>
              <div className="text-xs text-gray-500 mb-3">Record Trade Result</div>
              <div className="flex gap-2 mb-3">
                {['win', 'loss'].map((r) => (
                  <button
                    key={r}
                    onClick={() => setResult(r)}
                    className="flex-1 py-2 rounded text-sm font-mono font-bold transition-all"
                    style={{
                      background: result === r ? (r === 'win' ? '#22c55e' : '#ef4444') : '#1a2030',
                      color: result === r ? '#fff' : '#888',
                    }}
                  >
                    {r.toUpperCase()}
                  </button>
                ))}
              </div>
              <input
                type="number"
                placeholder="P&L in pips (optional)"
                value={pnl}
                onChange={(e) => setPnl(e.target.value)}
                className="w-full px-3 py-2 rounded text-sm font-mono mb-3"
                style={{ background: '#1a2030', border: '1px solid #2a3040', color: '#e6edf3' }}
              />
              <button
                onClick={handleRecord}
                disabled={!result || recording}
                className="w-full py-2 rounded text-sm font-mono font-bold disabled:opacity-50"
                style={{ background: '#c9a84c', color: '#000' }}
              >
                {recording ? 'Saving...' : 'Record Result'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
