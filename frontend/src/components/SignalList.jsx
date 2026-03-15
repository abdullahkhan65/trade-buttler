import React, { useState } from 'react'
import SignalModal from './SignalModal'

function ConfidenceBar({ score }) {
  const pct = (score / 9) * 100
  const color = score >= 7 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444'
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Confluence</span>
        <span style={{ color }}>{score}/9</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: '#1a2030' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}

export default function SignalList({ signals, onRecordResult }) {
  const [selected, setSelected] = useState(null)

  if (!signals || signals.length === 0) {
    return (
      <div className="text-center py-12 text-gray-600 font-mono text-sm">
        No signals yet. Engine is scanning...
      </div>
    )
  }

  return (
    <>
      <div className="space-y-3">
        {signals.map((s) => {
          const isBuy = s.direction === 'BUY'
          const isConfirmed = s.signal_type === 'confirmed' || s.status === 'confirmed'
          const dirColor = isBuy ? '#22c55e' : '#ef4444'

          return (
            <div
              key={s.id}
              className="signal-card rounded-lg p-4 cursor-pointer"
              style={{ background: '#0d1117' }}
              onClick={() => setSelected(s)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className="px-2 py-1 rounded text-xs font-bold font-mono"
                    style={{ background: dirColor + '22', color: dirColor, border: `1px solid ${dirColor}44` }}
                  >
                    {s.direction}
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold">{s.symbol}</div>
                    <div className="text-xs text-gray-500">
                      {s.created_at ? new Date(s.created_at).toLocaleString() : 'Just now'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {isConfirmed ? (
                    <span className="text-xs px-2 py-1 rounded font-mono" style={{ background: '#22c55e22', color: '#22c55e' }}>
                      CONFIRMED
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-1 rounded font-mono" style={{ background: '#f59e0b22', color: '#f59e0b' }}>
                      FORMING
                    </span>
                  )}
                  {s.result && (
                    <span
                      className="text-xs px-2 py-1 rounded font-mono"
                      style={{
                        background: s.result === 'win' ? '#22c55e22' : '#ef444422',
                        color: s.result === 'win' ? '#22c55e' : '#ef4444',
                      }}
                    >
                      {s.result.toUpperCase()}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 mt-3">
                <div>
                  <div className="text-xs text-gray-600">Entry</div>
                  <div className="font-mono text-sm" style={{ color: '#c9a84c' }}>
                    ${s.entry_price?.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">SL</div>
                  <div className="font-mono text-sm text-red-400">${s.stop_loss?.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">TP</div>
                  <div className="font-mono text-sm text-green-400">${s.take_profit?.toLocaleString()}</div>
                </div>
              </div>

              <ConfidenceBar score={s.score} />
            </div>
          )
        })}
      </div>

      {selected && (
        <SignalModal
          signal={selected}
          onClose={() => setSelected(null)}
          onRecord={onRecordResult}
        />
      )}
    </>
  )
}
