import React, { useEffect, useState } from 'react'
import axios from 'axios'

function FactorBar({ factor, data }) {
  const wr = data.win_rate || 0
  const color = wr >= 60 ? '#22c55e' : wr >= 45 ? '#f59e0b' : '#ef4444'
  const weightColor = data.weight >= 1.2 ? '#22c55e' : data.weight <= 0.8 ? '#ef4444' : '#c9a84c'

  return (
    <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="font-mono text-sm font-bold text-white">{factor.replace('_', ' ').toUpperCase()}</div>
          <div className="text-xs text-gray-600">{data.appearances} signals | {data.wins}W {data.losses}L</div>
        </div>
        <div className="text-right">
          <div className="font-mono font-bold" style={{ color }}>{wr}%</div>
          <div className="text-xs font-mono" style={{ color: weightColor }}>weight x{data.weight}</div>
        </div>
      </div>
      <div className="h-2 rounded-full" style={{ background: '#1a2030' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${wr}%`, background: color }} />
      </div>
      <div className="flex justify-between text-xs text-gray-600 mt-1">
        <span>0%</span>
        <span style={{ color: data.confidence === 'high' ? '#22c55e' : data.confidence === 'medium' ? '#f59e0b' : '#666' }}>
          {data.confidence} confidence
        </span>
        <span>100%</span>
      </div>
    </div>
  )
}

export default function FactorAnalysis() {
  const [data, setData] = useState(null)
  const [symbol, setSymbol] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async (sym) => {
    setLoading(true)
    try {
      const url = sym ? `/api/factors?symbol=${encodeURIComponent(sym)}` : '/api/factors'
      const res = await axios.get(url)
      setData(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(symbol) }, [symbol])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>Factor Analysis</h1>
          <p className="text-xs text-gray-500 font-mono mt-1">Which confluence factors actually predict wins</p>
        </div>
        <div className="flex gap-2">
          {[null, 'XAU/USD', 'BTC/USD'].map(s => (
            <button
              key={s || 'all'}
              onClick={() => setSymbol(s)}
              className="px-4 py-2 rounded text-xs font-mono"
              style={{ background: symbol === s ? '#c9a84c' : '#1a2030', color: symbol === s ? '#000' : '#888' }}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-gray-500 font-mono text-sm">Loading...</div>
      ) : !data || data.total_closed === 0 ? (
        <div className="rounded-lg p-8 text-center" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
          <div className="text-4xl mb-4">📊</div>
          <div className="font-mono text-gray-400 mb-2">No closed trades yet</div>
          <div className="text-xs text-gray-600 font-mono">
            Record trade results (win/loss) on the Signals page to enable factor analysis.
            <br />After 10+ results, this page will show which confluence factors are most predictive.
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
              <div className="text-xs text-gray-500 font-mono">Closed Trades</div>
              <div className="font-mono text-2xl font-bold" style={{ color: '#c9a84c' }}>{data.total_closed}</div>
            </div>
            <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
              <div className="text-xs text-gray-500 font-mono">Overall Win Rate</div>
              <div className="font-mono text-2xl font-bold" style={{ color: data.overall_win_rate >= 50 ? '#22c55e' : '#ef4444' }}>
                {data.overall_win_rate}%
              </div>
            </div>
            <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
              <div className="text-xs text-gray-500 font-mono mb-1">Recommendation</div>
              <div className="text-xs font-mono text-gray-300">{data.recommendation}</div>
            </div>
          </div>

          <div>
            <h2 className="font-display text-lg font-bold mb-4" style={{ color: '#c9a84c' }}>Factor Win Rates</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(data.factors || {}).map(([factor, fdata]) => (
                <FactorBar key={factor} factor={factor} data={fdata} />
              ))}
            </div>
          </div>

          {data.score_analysis && (
            <div>
              <h2 className="font-display text-lg font-bold mb-4" style={{ color: '#c9a84c' }}>Win Rate by Score</h2>
              <div className="grid grid-cols-5 gap-3">
                {Object.entries(data.score_analysis).map(([score, stats]) => (
                  <div key={score} className="rounded-lg p-3 text-center" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
                    <div className="font-mono text-2xl font-bold" style={{ color: '#c9a84c' }}>{score}</div>
                    <div className="text-xs text-gray-500 font-mono">score</div>
                    <div className="font-mono font-bold mt-2" style={{ color: stats.win_rate >= 50 ? '#22c55e' : '#ef4444' }}>
                      {stats.win_rate}%
                    </div>
                    <div className="text-xs text-gray-600">{stats.wins}W {stats.losses}L</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
