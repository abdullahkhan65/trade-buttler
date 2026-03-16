import React, { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt2  = (n) => n == null ? '—' : `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtPnl = (n) => {
  if (n == null) return '—'
  const abs = Math.abs(n).toFixed(2)
  return n >= 0 ? `+$${abs}` : `-$${abs}`
}
const fmtPct  = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
const fmtLots = (n) => n == null ? '—' : `${Number(n).toFixed(2)}`
const fmtTime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-US', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
const timeAgo = (iso) => {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso)) / 1000
  if (diff < 60)    return `${Math.round(diff)}s`
  if (diff < 3600)  return `${Math.round(diff / 60)}m`
  if (diff < 86400) return `${Math.round(diff / 3600)}h`
  return `${Math.round(diff / 86400)}d`
}

const STRATEGY_COLORS = {
  '1h_baseline':     '#c9a84c',
  '4h_conservative': '#22c55e',
  '15m_aggressive':  '#f97316',
  'xau_fibonacci':   '#a78bfa',
  'xau_structure':   '#38bdf8',
}

// ── Daily status badge ────────────────────────────────────────────────────────

function DailyBadge({ status }) {
  if (status === 'active')
    return <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#22c55e22', color: '#22c55e' }}>● ACTIVE</span>
  if (status === 'daily_target_reached')
    return <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#c9a84c22', color: '#c9a84c' }}>✓ TARGET HIT</span>
  return <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#ef444422', color: '#ef4444' }}>⚠ RISK LIMIT</span>
}

// ── Portfolio card ────────────────────────────────────────────────────────────

function PortfolioCard({ p, onReset, onScan }) {
  const color    = STRATEGY_COLORS[p.strategy_id] || '#888'
  const balColor = p.roi_pct >= 0 ? '#22c55e' : '#ef4444'

  const dailyColor   = p.daily_pnl >= 0 ? '#22c55e' : '#ef4444'
  const targetDollars = ((p.daily_target_pct / 100) * p.day_start_balance).toFixed(2)
  const riskDollars   = ((p.daily_risk_pct   / 100) * p.day_start_balance).toFixed(2)

  // Daily progress: positive = toward target, negative = toward risk limit
  const dailyProgress = p.daily_pnl >= 0
    ? Math.min((p.daily_pnl / (p.day_start_balance * p.daily_target_pct / 100)) * 100, 100)
    : Math.min((Math.abs(p.daily_pnl) / (p.day_start_balance * p.daily_risk_pct / 100)) * 100, 100)

  return (
    <div className="rounded-lg border p-4 space-y-3" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      {/* Header */}
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

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-sm font-mono font-bold text-white">{p.total_trades}</div>
          <div className="text-xs text-gray-600">Trades</div>
        </div>
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-sm font-mono font-bold text-green-400">{p.win_rate.toFixed(0)}%</div>
          <div className="text-xs text-gray-600">Win Rate</div>
        </div>
        <div className="rounded p-1.5" style={{ background: '#080b0f' }}>
          <div className="text-sm font-mono font-bold" style={{ color: '#c9a84c' }}>{fmtLots(p.lot_size)}</div>
          <div className="text-xs text-gray-600">Lots</div>
        </div>
      </div>

      {/* W/L bar */}
      {(p.winning_trades + p.losing_trades) > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-600 mb-1">
            <span>{p.winning_trades}W / {p.losing_trades}L</span>
            {p.open_trades > 0 && <span className="text-yellow-500">{p.open_trades} open</span>}
          </div>
          <div className="h-1 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
            <div className="h-full rounded-full bg-green-500"
              style={{ width: `${p.winning_trades / (p.winning_trades + p.losing_trades) * 100}%` }} />
          </div>
        </div>
      )}

      {/* Daily session */}
      <div className="rounded p-2.5 space-y-2" style={{ background: '#080b0f' }}>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-600 font-mono">Today</span>
          <DailyBadge status={p.daily_status} />
        </div>
        <div className="flex justify-between text-xs font-mono">
          <span style={{ color: dailyColor }}>{fmtPnl(p.daily_pnl)} ({fmtPct(p.daily_pnl_pct)})</span>
          <span className="text-gray-600">Target: +${targetDollars} · Limit: -${riskDollars}</span>
        </div>
        {/* Progress bar: green = toward target, red = toward risk */}
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
          <div className="h-full rounded-full transition-all"
            style={{ width: `${dailyProgress}%`, background: p.daily_pnl >= 0 ? '#22c55e' : '#ef4444' }} />
        </div>
      </div>

      {/* Actions */}
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

// ── MT5-style open trade row ───────────────────────────────────────────────────

function OpenTradeRow({ t, currentPrices }) {
  const [expanded, setExpanded] = useState(false)
  const color    = STRATEGY_COLORS[t.strategy_id] || '#888'
  const isBuy    = t.direction === 'BUY'
  const dirColor = isBuy ? '#22c55e' : '#ef4444'

  const curPrice = currentPrices?.[t.symbol]
  const floatPnl = curPrice != null
    ? ((isBuy ? curPrice - t.entry_price : t.entry_price - curPrice) * (t.units || t.lot_size || 1))
    : null
  const pnlColor = floatPnl == null ? '#888' : floatPnl >= 0 ? '#22c55e' : '#ef4444'

  const rr = t.take_profit && t.stop_loss && t.entry_price
    ? (Math.abs(t.take_profit - t.entry_price) / Math.abs(t.stop_loss - t.entry_price)).toFixed(1)
    : null

  return (
    <>
      <tr className="border-b cursor-pointer hover:bg-white/[0.02]" style={{ borderColor: '#1a2030' }}
        onClick={() => setExpanded(x => !x)}>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">#{t.id}</td>
        <td className="py-2 px-3">
          <div className="font-mono text-xs text-gray-200">{t.symbol}</div>
          <div className="text-xs" style={{ color }}>{t.timeframe}</div>
        </td>
        <td className="py-2 px-3 font-mono text-xs font-bold" style={{ color: '#c9a84c' }}>
          {fmtLots(t.lot_size ?? t.units)}
        </td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded"
            style={{ background: `${dirColor}22`, color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-400">{fmtTime(t.opened_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2 px-3 font-mono text-xs text-red-400">{fmt2(t.stop_loss)}</td>
        <td className="py-2 px-3 font-mono text-xs text-green-400">
          {fmt2(t.take_profit)}{rr && <span className="text-gray-600 ml-1 text-xs">/{rr}R</span>}
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-400">
          {curPrice != null ? fmt2(curPrice) : <span className="text-gray-600">—</span>}
        </td>
        <td className="py-2 px-3 font-mono text-sm font-bold" style={{ color: pnlColor }}>
          {floatPnl != null ? fmtPnl(floatPnl) : <span className="text-yellow-400 text-xs animate-pulse">live</span>}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={10} className="px-4 py-3 space-y-2">
            <div className="flex flex-wrap gap-1">
              {t.reasons.map((r, i) => (
                <span key={i} className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#1a2030', color: '#888' }}>{r}</span>
              ))}
            </div>
            <div className="text-xs font-mono text-gray-600">
              Risk: {fmt2(t.risk_usd)} · Score: {t.score}/9
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── MT5-style closed trade row ────────────────────────────────────────────────

function ClosedTradeRow({ t }) {
  const [expanded, setExpanded] = useState(false)
  const color    = STRATEGY_COLORS[t.strategy_id] || '#888'
  const isBuy    = t.direction === 'BUY'
  const dirColor = isBuy ? '#22c55e' : '#ef4444'
  const pnlColor = t.pnl_usd == null ? '#888' : t.pnl_usd >= 0 ? '#22c55e' : '#ef4444'
  const rr = t.take_profit && t.stop_loss && t.entry_price
    ? (Math.abs(t.take_profit - t.entry_price) / Math.abs(t.stop_loss - t.entry_price)).toFixed(1)
    : null

  return (
    <>
      <tr className="border-b cursor-pointer hover:bg-white/[0.02]" style={{ borderColor: '#1a2030' }}
        onClick={() => setExpanded(x => !x)}>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">#{t.id}</td>
        <td className="py-2 px-3">
          <div className="font-mono text-xs text-gray-200">{t.symbol}</div>
          <div className="text-xs" style={{ color }}>{t.timeframe}</div>
        </td>
        <td className="py-2 px-3 font-mono text-xs font-bold" style={{ color: '#c9a84c' }}>
          {fmtLots(t.lot_size ?? t.units)}
        </td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold px-1.5 py-0.5 rounded"
            style={{ background: `${dirColor}22`, color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmtTime(t.opened_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2 px-3 font-mono text-xs text-red-400">{fmt2(t.stop_loss)}</td>
        <td className="py-2 px-3 font-mono text-xs text-green-400">
          {fmt2(t.take_profit)}{rr && <span className="text-gray-600 ml-1 text-xs">/{rr}R</span>}
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmtTime(t.closed_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.exit_price)}</td>
        <td className="py-2 px-3 font-mono text-sm font-bold" style={{ color: pnlColor }}>
          {fmtPnl(t.pnl_usd)}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={11} className="px-4 py-3 space-y-2">
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
            <div className="text-xs font-mono text-gray-600">
              Risk: {fmt2(t.risk_usd)} · Score: {t.score}/9
            </div>
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
  const [tab, setTab]         = useState('insights')

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
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: '#1a2030' }}>
        <div>
          <h2 className="font-display font-bold" style={{ color: '#c9a84c' }}>AI Learning Engine</h2>
          {report && <p className="text-xs text-gray-600 font-mono mt-0.5">Last run: {timeAgo(report.created_at)} ago · {report.total_trades} trades analyzed</p>}
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
          No analysis yet — need at least 5 closed trades.<br />
          <span className="text-xs">Click <span style={{ color: '#c9a84c' }}>Run Analysis Now</span> after trades close.</span>
        </div>
      ) : (
        <>
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
                              <td className="px-2 py-2" style={{ color: s.pnl >= 0 ? '#22c55e' : '#ef4444' }}>{fmtPnl(s.pnl)}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  )}
              </div>
            )}

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
  const [portfolios, setPortfolios]   = useState([])
  const [trades, setTrades]           = useState([])
  const [currentPrices, setCurrentPrices] = useState({})
  const [tradeTab, setTradeTab]       = useState('open')   // open | history
  const [stratFilter, setStratFilter] = useState('all')
  const [loading, setLoading]         = useState(true)
  const [toast, setToast]             = useState(null)

  const load = useCallback(async () => {
    try {
      const [pRes, tRes, prRes] = await Promise.all([
        axios.get('/api/paper/portfolios'),
        axios.get('/api/paper/trades', { params: { limit: 300 } }),
        axios.get('/api/prices'),
      ])
      setPortfolios(pRes.data)
      setTrades(tRes.data)
      setCurrentPrices(prRes.data)
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
    if (!window.confirm(`Reset ${sid}?\nThis will clear all trades and restore $500.00 balance.`)) return
    await axios.post(`/api/paper/reset/${sid}`)
    showToast(`${sid} reset to $500`)
    load()
  }

  const handleScan = async (sid) => {
    await axios.post(`/api/paper/scan/${sid}`)
    showToast(`Scanning ${sid}...`)
    setTimeout(load, 3000)
  }

  const filteredTrades = trades.filter(t => {
    if (tradeTab === 'open'    && t.status !== 'open')   return false
    if (tradeTab === 'history' && t.status !== 'closed') return false
    if (stratFilter !== 'all' && t.strategy_id !== stratFilter) return false
    return true
  })

  const openTrades   = trades.filter(t => t.status === 'open')
  const closedTrades = trades.filter(t => t.status === 'closed')

  const totalBalance = portfolios.reduce((s, p) => s + p.balance, 0)
  const totalInitial = portfolios.reduce((s, p) => s + p.initial_balance, 0)
  const totalRoi     = totalInitial > 0 ? ((totalBalance - totalInitial) / totalInitial * 100) : 0
  const totalDailyPnl = portfolios.reduce((s, p) => s + (p.daily_pnl || 0), 0)

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <div className="text-gray-600 font-mono text-sm">Loading...</div>
    </div>
  )

  return (
    <div className="space-y-6">
      {toast && (
        <div className="fixed top-4 right-4 z-50 font-mono text-sm px-4 py-2 rounded shadow-lg"
          style={{ background: '#c9a84c', color: '#000' }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>Autonomous Paper Trading</h1>
          <p className="text-xs text-gray-600 mt-1 font-mono">
            5 strategies · $500/account · lot size = balance/100 · daily target +2% · daily risk limit -10%
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-600 font-mono">Combined ($2,500 deployed)</div>
          <div className="font-mono text-2xl font-bold" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmt2(totalBalance)}
          </div>
          <div className="flex gap-3 justify-end">
            <span className="text-xs font-mono" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
              {fmtPct(totalRoi)} total ROI
            </span>
            <span className="text-xs font-mono" style={{ color: totalDailyPnl >= 0 ? '#22c55e' : '#ef4444' }}>
              {fmtPnl(totalDailyPnl)} today
            </span>
          </div>
        </div>
      </div>

      {/* Strategy cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        {portfolios.map(p => (
          <PortfolioCard key={p.strategy_id} p={p} onReset={handleReset} onScan={handleScan} />
        ))}
      </div>

      {/* AI Insights */}
      <InsightsPanel onRunAnalysis={load} />

      {/* Trade log — MT5 style */}
      <div className="rounded-lg border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
        {/* Tab bar */}
        <div className="flex items-center justify-between px-4 pt-3 border-b flex-wrap gap-2" style={{ borderColor: '#1a2030' }}>
          <div className="flex gap-0">
            {[
              ['open',    `Open (${openTrades.length})`],
              ['history', `History (${closedTrades.length})`],
            ].map(([id, label]) => (
              <button key={id} onClick={() => setTradeTab(id)}
                className="text-xs font-mono px-4 py-2.5 border-b-2 transition-colors"
                style={{ borderColor: tradeTab === id ? '#c9a84c' : 'transparent', color: tradeTab === id ? '#c9a84c' : '#555' }}>
                {label}
              </button>
            ))}
          </div>
          {/* Strategy filter */}
          <div className="flex gap-1.5 flex-wrap pb-2">
            {['all', ...portfolios.map(p => p.strategy_id)].map(s => (
              <button key={s} onClick={() => setStratFilter(s)}
                className="text-xs font-mono px-2.5 py-1 rounded"
                style={{
                  background:   stratFilter === s ? '#1a2030' : 'transparent',
                  color:        stratFilter === s ? (STRATEGY_COLORS[s] || '#fff') : '#555',
                  border:       `1px solid ${stratFilter === s ? '#333' : '#1a2030'}`,
                }}>
                {s === 'all' ? 'All' : s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {filteredTrades.length === 0 ? (
          <div className="text-center py-10 text-gray-600 font-mono text-sm">
            {tradeTab === 'open' ? 'No open positions.' : 'No closed trades yet.'}<br />
            <span className="text-xs">Waiting for confirmed signals.</span>
          </div>
        ) : tradeTab === 'open' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid #1a2030' }}>
                  {['#', 'Symbol', 'Lots', 'Type', 'Open Time', 'Open Price', 'S/L', 'T/P', 'Current', 'Profit'].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-xs text-gray-600 font-mono">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredTrades.map(t => <OpenTradeRow key={t.id} t={t} currentPrices={currentPrices} />)}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid #1a2030' }}>
                  {['#', 'Symbol', 'Lots', 'Type', 'Open Time', 'Open Price', 'S/L', 'T/P', 'Close Time', 'Close Price', 'Profit'].map(h => (
                    <th key={h} className="text-left px-3 py-2 text-xs text-gray-600 font-mono">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredTrades.map(t => <ClosedTradeRow key={t.id} t={t} />)}
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
            { id: '1h_baseline',     tf: '1H',  confirm: '8/9', note: 'EMA + RSI multi-confluence' },
            { id: '4h_conservative', tf: '4H',  confirm: '8/9', note: 'Slower, wider ATR stops' },
            { id: '15m_aggressive',  tf: '15M', confirm: '7/9', note: 'Fast entries, tighter risk' },
            { id: 'xau_fibonacci',   tf: '1H',  confirm: '7/9', note: 'Fib 38.2–61.8% retracement' },
            { id: 'xau_structure',   tf: '1H',  confirm: '7/9', note: 'Order blocks + stop hunts' },
          ].map(s => (
            <div key={s.id} className="rounded p-2.5 space-y-0.5" style={{ background: '#080b0f', borderLeft: `2px solid ${STRATEGY_COLORS[s.id]}` }}>
              <div className="font-bold" style={{ color: STRATEGY_COLORS[s.id] }}>{s.id.replace(/_/g, ' ')}</div>
              <div className="text-gray-600">TF: <span className="text-gray-400">{s.tf}</span></div>
              <div className="text-gray-600">Min score: <span className="text-gray-400">{s.confirm}</span></div>
              <div className="text-gray-600">Daily target: <span className="text-gray-400">+2%</span></div>
              <div className="text-gray-600">Daily limit: <span className="text-gray-400">-10%</span></div>
              <div style={{ color: '#555' }}>{s.note}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
