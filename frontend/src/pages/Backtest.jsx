import React, { useState } from 'react'
import axios from 'axios'

const DEFAULT_PARAMS = {
  rsi_buy_low: 40, rsi_buy_high: 65,
  rsi_sell_low: 35, rsi_sell_high: 60,
  min_score_forming: 5, min_score_confirmed: 7,
  atr_sl_mult: 1.5, atr_tp_mult: 3.0,
}

function StatCard({ label, value, color }) {
  return (
    <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
      <div className="text-xs text-gray-500 font-mono mb-1">{label}</div>
      <div className="font-mono text-xl font-bold" style={{ color: color || '#c9a84c' }}>{value}</div>
    </div>
  )
}

function EquityCurve({ data }) {
  if (!data || data.length < 2) return null
  const max = Math.max(...data, 0.1)
  const min = Math.min(...data, -0.1)
  const range = max - min || 1
  const h = 120
  const w = 600

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(' ')

  const zeroY = h - ((0 - min) / range) * h

  return (
    <div className="rounded-lg p-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
      <div className="text-xs text-gray-500 font-mono mb-3">Equity Curve (R)</div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height: h }}>
        <line x1="0" y1={zeroY} x2={w} y2={zeroY} stroke="#1a2030" strokeWidth="1" />
        <polyline
          fill="none"
          stroke={data[data.length - 1] >= 0 ? '#22c55e' : '#ef4444'}
          strokeWidth="2"
          points={points}
        />
      </svg>
    </div>
  )
}

export default function Backtest() {
  const [symbol, setSymbol] = useState('XAU/USD')
  const [interval, setInterval] = useState('1h')
  const [params, setParams] = useState({ ...DEFAULT_PARAMS })
  const [result, setResult] = useState(null)
  const [optimResult, setOptimResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [optimLoading, setOptimLoading] = useState(false)
  const [tab, setTab] = useState('backtest')

  const runBacktest = async () => {
    setLoading(true)
    setResult(null)
    try {
      const res = await axios.post('/api/backtest', { symbol, interval, params, limit: 500 })
      setResult(res.data)
    } catch (e) {
      alert('Backtest failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const runOptimize = async (quick = true) => {
    setOptimLoading(true)
    setOptimResult(null)
    try {
      const res = await axios.post('/api/optimize', { symbol, interval, quick })
      setOptimResult(res.data)
      if (res.data.best_params) {
        setParams(res.data.best_params)
      }
    } catch (e) {
      alert('Optimization failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setOptimLoading(false)
    }
  }

  const ParamInput = ({ k, label, step = 1 }) => (
    <div>
      <label className="block text-xs text-gray-500 font-mono mb-1">{label}</label>
      <input
        type="number"
        step={step}
        value={params[k]}
        onChange={e => setParams(p => ({ ...p, [k]: parseFloat(e.target.value) }))}
        className="w-full px-3 py-2 rounded text-sm font-mono"
        style={{ background: '#1a2030', border: '1px solid #2a3040', color: '#e6edf3' }}
      />
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>
          Strategy Lab
        </h1>
        <div className="flex gap-2">
          {['backtest', 'optimizer'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-4 py-2 rounded text-sm font-mono capitalize"
              style={{
                background: tab === t ? '#c9a84c' : '#1a2030',
                color: tab === t ? '#000' : '#888',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls */}
        <div className="rounded-lg p-5 space-y-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
          <div>
            <label className="block text-xs text-gray-500 font-mono mb-1">Symbol</label>
            <div className="flex gap-2">
              {['XAU/USD', 'BTC/USD'].map(s => (
                <button
                  key={s}
                  onClick={() => setSymbol(s)}
                  className="flex-1 py-2 rounded text-xs font-mono"
                  style={{ background: symbol === s ? '#c9a84c' : '#1a2030', color: symbol === s ? '#000' : '#888' }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono mb-1">Interval</label>
            <div className="flex gap-2">
              {['15m', '1h', '4h'].map(iv => (
                <button
                  key={iv}
                  onClick={() => setInterval(iv)}
                  className="flex-1 py-2 rounded text-xs font-mono"
                  style={{ background: interval === iv ? '#c9a84c22' : '#1a2030', color: interval === iv ? '#c9a84c' : '#888', border: interval === iv ? '1px solid #c9a84c44' : '1px solid transparent' }}
                >
                  {iv}
                </button>
              ))}
            </div>
          </div>

          <div className="border-t pt-4" style={{ borderColor: '#1a2030' }}>
            <div className="text-xs text-gray-500 font-mono mb-3">RSI Parameters</div>
            <div className="grid grid-cols-2 gap-3">
              <ParamInput k="rsi_buy_low" label="RSI Buy Low" />
              <ParamInput k="rsi_buy_high" label="RSI Buy High" />
              <ParamInput k="rsi_sell_low" label="RSI Sell Low" />
              <ParamInput k="rsi_sell_high" label="RSI Sell High" />
            </div>
          </div>

          <div className="border-t pt-4" style={{ borderColor: '#1a2030' }}>
            <div className="text-xs text-gray-500 font-mono mb-3">Risk Parameters</div>
            <div className="grid grid-cols-2 gap-3">
              <ParamInput k="atr_sl_mult" label="ATR SL x" step={0.1} />
              <ParamInput k="atr_tp_mult" label="ATR TP x" step={0.1} />
              <ParamInput k="min_score_forming" label="Min Score (Forming)" />
              <ParamInput k="min_score_confirmed" label="Min Score (Confirmed)" />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <button
              onClick={runBacktest}
              disabled={loading}
              className="w-full py-2.5 rounded text-sm font-mono font-bold disabled:opacity-50"
              style={{ background: '#c9a84c', color: '#000' }}
            >
              {loading ? 'Running Backtest...' : 'Run Backtest'}
            </button>
            <button
              onClick={() => runOptimize(true)}
              disabled={optimLoading}
              className="w-full py-2.5 rounded text-sm font-mono border disabled:opacity-50"
              style={{ borderColor: '#c9a84c', color: '#c9a84c' }}
            >
              {optimLoading ? 'Optimizing...' : 'Quick Optimize'}
            </button>
            <button
              onClick={() => runOptimize(false)}
              disabled={optimLoading}
              className="w-full py-2.5 rounded text-sm font-mono border disabled:opacity-50"
              style={{ borderColor: '#3b82f6', color: '#3b82f6' }}
            >
              {optimLoading ? 'Optimizing...' : 'Full Optimize (slow)'}
            </button>
          </div>

          {optimLoading && (
            <div className="text-xs text-gray-500 font-mono text-center animate-pulse">
              Testing parameter combinations...
            </div>
          )}
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-4">
          {result && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Win Rate" value={`${result.win_rate}%`} color={result.win_rate >= 50 ? '#22c55e' : '#ef4444'} />
                <StatCard label="Profit Factor" value={result.profit_factor} color={result.profit_factor >= 1.5 ? '#22c55e' : '#f59e0b'} />
                <StatCard label="Avg R" value={`${result.avg_r > 0 ? '+' : ''}${result.avg_r}R`} color={result.avg_r >= 0 ? '#22c55e' : '#ef4444'} />
                <StatCard label="Sharpe" value={result.sharpe} color={result.sharpe >= 1 ? '#22c55e' : '#f59e0b'} />
                <StatCard label="Total Trades" value={result.total_trades} />
                <StatCard label="Wins" value={result.wins} color="#22c55e" />
                <StatCard label="Losses" value={result.losses} color="#ef4444" />
                <StatCard label="Max Drawdown" value={`${result.max_drawdown_r}R`} color="#ef4444" />
              </div>

              <EquityCurve data={result.equity_curve} />

              <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #1a2030' }}>
                <div className="px-4 py-3 text-xs text-gray-500 font-mono" style={{ background: '#0d1117', borderBottom: '1px solid #1a2030' }}>
                  Trade Log ({result.trades?.length} trades)
                </div>
                <div className="overflow-auto max-h-80">
                  <table className="w-full text-xs font-mono">
                    <thead>
                      <tr style={{ background: '#0d1117' }}>
                        {['Dir', 'Score', 'Entry', 'SL', 'TP', 'Outcome', 'P&L (R)', 'Bars'].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-gray-600">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(result.trades || []).map((t, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #1a2030', background: i % 2 === 0 ? '#080b0f' : '#0d1117' }}>
                          <td className="px-3 py-2" style={{ color: t.direction === 'BUY' ? '#22c55e' : '#ef4444' }}>{t.direction}</td>
                          <td className="px-3 py-2" style={{ color: '#c9a84c' }}>{t.score}/9</td>
                          <td className="px-3 py-2">${t.entry_price?.toLocaleString()}</td>
                          <td className="px-3 py-2 text-red-400">${t.stop_loss?.toLocaleString()}</td>
                          <td className="px-3 py-2 text-green-400">${t.take_profit?.toLocaleString()}</td>
                          <td className="px-3 py-2" style={{ color: t.outcome === 'win' ? '#22c55e' : t.outcome === 'loss' ? '#ef4444' : '#666' }}>
                            {t.outcome || 'open'}
                          </td>
                          <td className="px-3 py-2" style={{ color: (t.pnl_r || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                            {t.pnl_r !== null ? `${t.pnl_r > 0 ? '+' : ''}${t.pnl_r}R` : '-'}
                          </td>
                          <td className="px-3 py-2 text-gray-600">{t.bars_held || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {optimResult && (
            <div className="rounded-lg p-5 space-y-4" style={{ background: '#0d1117', border: '1px solid #1a2030' }}>
              <div className="text-sm font-mono font-bold" style={{ color: '#c9a84c' }}>
                Optimization Complete — {optimResult.total_combinations_tested} combinations tested
              </div>
              {optimResult.best_summary && (
                <div className="grid grid-cols-4 gap-3">
                  <StatCard label="Best Win Rate" value={`${optimResult.best_summary.win_rate}%`} color="#22c55e" />
                  <StatCard label="Profit Factor" value={optimResult.best_summary.profit_factor} color="#22c55e" />
                  <StatCard label="Sharpe" value={optimResult.best_summary.sharpe} />
                  <StatCard label="Trades" value={optimResult.best_summary.closed_trades} />
                </div>
              )}
              <div>
                <div className="text-xs text-gray-500 font-mono mb-2">Best Parameters (applied to form)</div>
                <div className="grid grid-cols-4 gap-2">
                  {Object.entries(optimResult.best_params || {}).map(([k, v]) => (
                    <div key={k} className="rounded p-2 text-center" style={{ background: '#1a2030' }}>
                      <div className="text-xs text-gray-600">{k}</div>
                      <div className="font-mono text-sm" style={{ color: '#c9a84c' }}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
              {optimResult.top_10 && (
                <div>
                  <div className="text-xs text-gray-500 font-mono mb-2">Top 10 Configurations</div>
                  <div className="overflow-auto max-h-60">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr style={{ borderBottom: '1px solid #1a2030' }}>
                          {['Rank', 'Win Rate', 'PF', 'Sharpe', 'Trades', 'Score'].map(h => (
                            <th key={h} className="px-3 py-2 text-left text-gray-600">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {optimResult.top_10.map((r, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid #1a2030' }}>
                            <td className="px-3 py-2 text-gray-500">#{i + 1}</td>
                            <td className="px-3 py-2" style={{ color: r.win_rate >= 50 ? '#22c55e' : '#ef4444' }}>{r.win_rate}%</td>
                            <td className="px-3 py-2 text-yellow-400">{r.profit_factor}</td>
                            <td className="px-3 py-2 text-blue-400">{r.sharpe}</td>
                            <td className="px-3 py-2 text-gray-400">{r.closed_trades}</td>
                            <td className="px-3 py-2" style={{ color: '#c9a84c' }}>{r.score}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {!result && !optimResult && !loading && !optimLoading && (
            <div className="flex items-center justify-center h-64 rounded-lg text-gray-600 font-mono text-sm" style={{ border: '1px solid #1a2030' }}>
              Configure parameters and run a backtest or optimization
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
