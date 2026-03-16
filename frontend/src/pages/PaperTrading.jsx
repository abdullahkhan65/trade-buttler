import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt2 = (n) => (n == null ? '—' : `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
const fmtPnl = (n) => {
  if (n == null) return '—'
  return `${n >= 0 ? '+' : ''}$${Math.abs(n).toFixed(2)}`
}
const fmtPct = (n) => (n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`)
const timeAgo = (iso) => {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso)) / 1000
  if (diff < 60)    return `${Math.round(diff)}s ago`
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

const STRATEGY_COLORS = {
  '1h_baseline':     '#c9a84c',
  '4h_conservative': '#22c55e',
  '15m_aggressive':  '#f97316',
  'xau_fibonacci':   '#a78bfa',
  'xau_structure':   '#38bdf8',
}

// ── Portfolio card ────────────────────────────────────────────────────────────

function PortfolioCard({ p, onReset, onScan }) {
  const color    = STRATEGY_COLORS[p.strategy_id] || '#888'
  const balColor = p.roi_pct >= 0 ? '#22c55e' : '#ef4444'

  return (
    <div className="rounded-lg border p-4 space-y-3" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: `${color}22`, color }}>{p.timeframe.toUpperCase()}</span>
          <h3 className="font-display font-bold text-sm mt-1.5" style={{ color }}>{p.label}</h3>
        </div>
        <div className="text-right">
          <div className="font-mono text-xl font-bold" style={{ color: balColor }}>{fmt2(p.balance)}</div>
          <div className="text-xs font-mono" style={{ color: balColor }}>{fmtPct(p.roi_pct)} ROI</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-base font-mono font-bold text-white">{p.total_trades}</div>
          <div className="text-xs text-gray-600">Trades</div>
        </div>
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-base font-mono font-bold text-green-400">{p.win_rate.toFixed(0)}%</div>
          <div className="text-xs text-gray-600">Win Rate</div>
        </div>
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-base font-mono font-bold" style={{ color: p.drawdown_pct > 5 ? '#ef4444' : '#888' }}>
            -{p.drawdown_pct.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-600">Drawdown</div>
        </div>
      </div>

      {p.total_trades > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>{p.winning_trades}W / {p.losing_trades}L</span>
            {p.open_trades > 0 && <span className="text-yellow-500">{p.open_trades} open</span>}
          </div>
          <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
            {(p.winning_trades + p.losing_trades) > 0 && (
              <div className="h-full rounded-full bg-green-500"
                style={{ width: `${p.winning_trades / (p.winning_trades + p.losing_trades) * 100}%` }} />
            )}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={() => onScan(p.strategy_id)}
          className="flex-1 text-xs font-mono py-1.5 rounded border transition-colors hover:text-white"
          style={{ borderColor: color, color }}>
          Scan Now
        </button>
        <button onClick={() => onReset(p.strategy_id)}
          className="text-xs font-mono py-1.5 px-3 rounded border"
          style={{ borderColor: '#1a2030', color: '#444' }}>
          Reset
        </button>
      </div>
    </div>
  )
}

// ── Trade row ─────────────────────────────────────────────────────────────────

function TradeRow({ t }) {
  const [expanded, setExpanded] = useState(false)
  const color    = STRATEGY_COLORS[t.strategy_id] || '#888'
  const dirColor = t.direction === 'BUY' ? '#22c55e' : '#ef4444'
  const pnlColor = t.pnl_usd == null ? '#888' : t.pnl_usd >= 0 ? '#22c55e' : '#ef4444'
  const rr = t.take_profit && t.stop_loss && t.entry_price
    ? (Math.abs(t.take_profit - t.entry_price) / Math.abs(t.stop_loss - t.entry_price)).toFixed(1) : null

  return (
    <>
      <tr className="border-b cursor-pointer hover:bg-white/[0.02] transition-colors"
        style={{ borderColor: '#1a2030' }} onClick={() => setExpanded(x => !x)}>
        <td className="py-2 px-3">
          <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: `${color}22`, color }}>{t.timeframe}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{t.symbol}</td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold" style={{ color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmt2(t.stop_loss)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">
          {fmt2(t.take_profit)}{rr && <span className="text-gray-700 ml-1">({rr}R)</span>}
        </td>
        <td className="py-2 px-3">
          {t.status === 'open'
            ? <span className="text-xs font-mono text-yellow-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />OPEN</span>
            : <span className="text-xs font-mono" style={{ color: t.result === 'win' ? '#22c55e' : '#ef4444' }}>{(t.result || 'closed').toUpperCase()}</span>}
        </td>
        <td className="py-2 px-3 font-mono text-sm font-bold" style={{ color: pnlColor }}>
          {t.status === 'open' ? <span className="text-gray-600 text-xs">live</span> : fmtPnl(t.pnl_usd)}
        </td>
        <td className="py-2 px-3 text-xs text-gray-600">{timeAgo(t.opened_at)}</td>
      </tr>
      {expanded && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={9} className="px-3 py-3 space-y-2">
            <div className="flex flex-wrap gap-1">
              {t.reasons.map((r, i) => (
                <span key={i} className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#1a2030', color: '#888' }}>{r}</span>
              ))}
            </div>
            {t.analysis && (
              <div className="text-xs font-mono p-2 rounded" style={{ background: '#0d1117', color: '#c9a84c', borderLeft: '2px solid #c9a84c' }}>
                {t.analysis}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Insights panel ────────────────────────────────────────────────────────────

function InsightsPanel({ onRunAnalysis }) {
  const [report, setReport]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [tab, setTab]         = useState('insights') // insights | factors | strategies

  const load = useCallback(async () => {
    try {
      const res = await axios.get('/api/analysis/latest')
      setReport(res.data.status === 'no_data' ? null : res.data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRun = async () => {
    setRunning(true)
    await axios.post('/api/analysis/run')
    setTimeout(async () => { await load(); setRunning(false) }, 4000)
    onRunAnalysis?.()
  }

  const factorRows = report?.factor_data
    ? Object.entries(report.factor_data).sort((a, b) => b[1].win_rate - a[1].win_rate)
    : []

  const stratRows = report?.strategy_data
    ? Object.entries(report.strategy_data).sort((a, b) => b[1].win_rate - a[1].win_rate)
    : []

  return (
    <div className="rounded-lg border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: '#1a2030' }}>
        <div>
          <h2 className="font-display font-bold" style={{ color: '#c9a84c' }}>AI Learning Engine</h2>
          {report && <p className="text-xs text-gray-600 font-mono mt-0.5">Last run: {timeAgo(report.created_at)} · {report.total_trades} trades analyzed</p>}
        </div>
        <button onClick={handleRun} disabled={running}
          className="text-xs font-mono px-4 py-1.5 rounded border transition-colors"
          style={{ borderColor: '#c9a84c', color: running ? '#555' : '#c9a84c' }}>
          {running ? 'Analyzing...' : 'Run Analysis Now'}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-600 font-mono text-sm">Loading...</div>
      ) : !report ? (
        <div className="text-center py-10 text-gray-600 font-mono text-sm px-6">
          No analysis yet.<br />
          <span className="text-xs">Need at least 3 closed trades. Click <span style={{ color: '#c9a84c' }}>Run Analysis Now</span> after trades close.</span>
        </div>
      ) : (
        <>
          {/* Tabs */}
          <div className="flex border-b px-4" style={{ borderColor: '#1a2030' }}>
            {[['insights', 'Insights'], ['factors', 'Factor Win Rates'], ['strategies', 'Strategy Comparison']].map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className="text-xs font-mono px-3 py-2.5 border-b-2 mr-2 transition-colors"
                style={{ borderColor: tab === id ? '#c9a84c' : 'transparent', color: tab === id ? '#c9a84c' : '#555' }}>
                {label}
              </button>
            ))}
          </div>

          <div className="p-4">
            {/* Insights tab */}
            {tab === 'insights' && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  {report.insights.map((ins, i) => (
                    <div key={i} className="flex gap-2 text-xs font-mono">
                      <span style={{ color: '#c9a84c' }}>›</span>
                      <span className="text-gray-300">{ins}</span>
                    </div>
                  ))}
                </div>
                {report.recommendations?.length > 0 && (
                  <div className="mt-4 pt-3 border-t space-y-1.5" style={{ borderColor: '#1a2030' }}>
                    <div className="text-xs font-mono font-bold text-gray-500 mb-2">RECOMMENDATIONS</div>
                    {report.recommendations.map((rec, i) => (
                      <div key={i} className="flex gap-2 text-xs font-mono p-2 rounded"
                        style={{ background: '#080b0f', borderLeft: '2px solid #f97316' }}>
                        <span style={{ color: '#f97316' }}>!</span>
                        <span className="text-gray-400">{rec}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Factor win rates tab */}
            {tab === 'factors' && (
              <div>
                {factorRows.length === 0
                  ? <p className="text-gray-600 font-mono text-xs text-center py-4">No factor data yet.</p>
                  : (
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr style={{ borderBottom: '1px solid #1a2030' }}>
                          {['Signal Factor', 'Trades', 'Win Rate', 'W/L', 'PnL'].map(h => (
                            <th key={h} className="text-left px-2 py-2 text-gray-600">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {factorRows.map(([factor, s]) => {
                          const wr = s.win_rate
                          const barColor = wr >= 60 ? '#22c55e' : wr >= 45 ? '#c9a84c' : '#ef4444'
                          return (
                            <tr key={factor} style={{ borderBottom: '1px solid #0d1117' }}>
                              <td className="px-2 py-2 text-gray-300">{factor}</td>
                              <td className="px-2 py-2 text-gray-500">{s.occurrences}</td>
                              <td className="px-2 py-2">
                                <div className="flex items-center gap-2">
                                  <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
                                    <div className="h-full rounded-full" style={{ width: `${wr}%`, background: barColor }} />
                                  </div>
                                  <span style={{ color: barColor }}>{wr}%</span>
                                </div>
                              </td>
                              <td className="px-2 py-2 text-gray-500">{s.wins}W / {s.losses}L</td>
                              <td className="px-2 py-2" style={{ color: s.pnl >= 0 ? '#22c55e' : '#ef4444' }}>
                                {fmtPnl(s.pnl)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
              </div>
            )}

            {/* Strategy comparison tab */}
            {tab === 'strategies' && (
              <div>
                {stratRows.length === 0
                  ? <p className="text-gray-600 font-mono text-xs text-center py-4">No strategy data yet.</p>
                  : (
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr style={{ borderBottom: '1px solid #1a2030' }}>
                          {['Strategy', 'Trades', 'Win Rate', 'Avg Win', 'Avg Loss', 'Profit Factor', 'PnL'].map(h => (
                            <th key={h} className="text-left px-2 py-2 text-gray-600">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {stratRows.map(([sid, s]) => {
                          const color = STRATEGY_COLORS[sid] || '#888'
                          return (
                            <tr key={sid} style={{ borderBottom: '1px solid #0d1117' }}>
                              <td className="px-2 py-2" style={{ color }}>{sid.replace(/_/g, ' ')}</td>
                              <td className="px-2 py-2 text-gray-500">{s.total}</td>
                              <td className="px-2 py-2" style={{ color: s.win_rate >= 50 ? '#22c55e' : '#ef4444' }}>{s.win_rate}%</td>
                              <td className="px-2 py-2 text-green-500">{fmtPnl(s.avg_win)}</td>
                              <td className="px-2 py-2 text-red-400">{fmtPnl(s.avg_loss)}</td>
                              <td className="px-2 py-2" style={{ color: s.profit_factor >= 1 ? '#22c55e' : '#ef4444' }}>{s.profit_factor}x</td>
                              <td className="px-2 py-2" style={{ color: s.total_pnl >= 0 ? '#22c55e' : '#ef4444' }}>{fmtPnl(s.total_pnl)}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PaperTrading() {
  const [portfolios, setPortfolios] = useState([])
  const [trades, setTrades]         = useState([])
  const [filter, setFilter]         = useState('all')
  const [stratFilter, setStratFilter] = useState('all')
  const [loading, setLoading]       = useState(true)
  const [toast, setToast]           = useState(null)

  const load = useCallback(async () => {
    try {
      const [pRes, tRes] = await Promise.all([
        axios.get('/api/paper/portfolios'),
        axios.get('/api/paper/trades', { params: { limit: 200 } }),
      ])
      setPortfolios(pRes.data)
      setTrades(tRes.data)
    } catch (e) {
      console.error('Paper trading load error', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = window.setInterval(load, 15000)
    return () => window.clearInterval(id)
  }, [load])

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000) }

  const handleReset = async (sid) => {
    if (!window.confirm(`Reset ${sid}? Clears all trades and restores $100 balance.`)) return
    await axios.post(`/api/paper/reset/${sid}`)
    showToast(`${sid} reset to $100`)
    load()
  }

  const handleScan = async (sid) => {
    await axios.post(`/api/paper/scan/${sid}`)
    showToast(`Scanning ${sid}...`)
    setTimeout(load, 3000)
  }

  const filteredTrades = trades.filter(t => {
    if (filter === 'open'   && t.status !== 'open')   return false
    if (filter === 'closed' && t.status !== 'closed') return false
    if (stratFilter !== 'all' && t.strategy_id !== stratFilter) return false
    return true
  })

  const totalBalance = portfolios.reduce((s, p) => s + p.balance, 0)
  const totalInitial = portfolios.reduce((s, p) => s + p.initial_balance, 0)
  const totalRoi     = totalInitial > 0 ? ((totalBalance - totalInitial) / totalInitial * 100) : 0

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <div className="text-gray-600 font-mono text-sm">Loading...</div>
    </div>
  )

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed top-4 right-4 z-50 font-mono text-sm px-4 py-2 rounded" style={{ background: '#c9a84c', color: '#000' }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>Autonomous Paper Trading</h1>
          <p className="text-xs text-gray-600 mt-1 font-mono">5 strategies · auto-enters confirmed signals · SL/TP monitored every 10s · self-learning every 6h</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-600 font-mono">Combined ($500 deployed)</div>
          <div className="font-mono text-2xl font-bold" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmt2(totalBalance)}
          </div>
          <div className="text-xs font-mono" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmtPct(totalRoi)} total ROI
          </div>
        </div>
      </div>

      {/* Strategy cards — 5 across */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        {portfolios.map(p => (
          <PortfolioCard key={p.strategy_id} p={p} onReset={handleReset} onScan={handleScan} />
        ))}
      </div>

      {/* AI Insights */}
      <InsightsPanel onRunAnalysis={load} />

      {/* Trade log */}
      <div className="rounded-lg border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b flex-wrap gap-2" style={{ borderColor: '#1a2030' }}>
          <h2 className="font-display font-bold" style={{ color: '#c9a84c' }}>Trade Log</h2>
          <div className="flex gap-1.5 flex-wrap">
            {['all', 'open', 'closed'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className="text-xs font-mono px-2.5 py-1 rounded"
                style={{ background: filter === f ? '#c9a84c22' : 'transparent', color: filter === f ? '#c9a84c' : '#555', border: `1px solid ${filter === f ? '#c9a84c' : '#1a2030'}` }}>
                {f}
              </button>
            ))}
            <div className="w-px mx-0.5" style={{ background: '#1a2030' }} />
            {['all', ...portfolios.map(p => p.strategy_id)].map(s => (
              <button key={s} onClick={() => setStratFilter(s)}
                className="text-xs font-mono px-2.5 py-1 rounded"
                style={{ background: stratFilter === s ? '#1a2030' : 'transparent', color: stratFilter === s ? (STRATEGY_COLORS[s] || '#fff') : '#555', border: `1px solid ${stratFilter === s ? '#333' : '#1a2030'}` }}>
                {s === 'all' ? 'All' : s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {filteredTrades.length === 0 ? (
          <div className="text-center py-10 text-gray-600 font-mono text-sm">
            No trades yet.<br />
            <span className="text-xs">Waiting for confirmed signals. Click Scan Now on any strategy card above.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid #1a2030' }}>
                  {['TF', 'Symbol', 'Dir', 'Entry', 'SL', 'TP', 'Status', 'PnL', 'Age'].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-xs text-gray-600 font-mono">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredTrades.map(t => <TradeRow key={t.id} t={t} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Strategy guide */}
      <div className="rounded-lg border p-4" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
        <h3 className="font-mono text-xs font-bold text-gray-500 mb-3">STRATEGY PARAMETERS</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-2 text-xs font-mono">
          {[
            { id: '1h_baseline',     tf: '1H',  risk: '2%',   confirm: '8/9', note: 'EMA + RSI multi-confluence' },
            { id: '4h_conservative', tf: '4H',  risk: '2%',   confirm: '8/9', note: 'Slower, wider ATR stops' },
            { id: '15m_aggressive',  tf: '15M', risk: '1.5%', confirm: '7/9', note: 'Fast entries, tighter risk' },
            { id: 'xau_fibonacci',   tf: '1H',  risk: '2%',   confirm: '7/9', note: 'Fib 38.2–61.8% retracement' },
            { id: 'xau_structure',   tf: '1H',  risk: '2%',   confirm: '7/9', note: 'Order blocks + stop hunts' },
          ].map(s => (
            <div key={s.id} className="rounded p-2.5 space-y-0.5" style={{ background: '#080b0f', borderLeft: `2px solid ${STRATEGY_COLORS[s.id]}` }}>
              <div className="font-bold" style={{ color: STRATEGY_COLORS[s.id] }}>{s.id.replace(/_/g, ' ')}</div>
              <div className="text-gray-600">TF: <span className="text-gray-400">{s.tf}</span></div>
              <div className="text-gray-600">Risk: <span className="text-gray-400">{s.risk}</span></div>
              <div className="text-gray-600">Min score: <span className="text-gray-400">{s.confirm}</span></div>
              <div className="text-gray-600 leading-tight" style={{ color: '#666' }}>{s.note}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
