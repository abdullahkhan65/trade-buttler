import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt2   = (n) => n == null ? '—' : `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtPnl = (n) => {
  if (n == null) return '—'
  return n >= 0 ? `+$${Math.abs(n).toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`
}
const fmtPct  = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
const fmtLots = (n) => n == null ? '—' : Number(n).toFixed(2)
const fmtTime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const STRATEGY_COLORS = {
  '1h_baseline':     '#c9a84c',
  '4h_conservative': '#22c55e',
  '15m_aggressive':  '#f97316',
  'xau_fibonacci':   '#a78bfa',
  'xau_structure':   '#38bdf8',
}

// ── Account header card ───────────────────────────────────────────────────────

function AccountCard({ p, onReset, onScanAll }) {
  const dailyColor   = p.daily_pnl >= 0 ? '#22c55e' : '#ef4444'
  const balColor     = p.roi_pct  >= 0 ? '#22c55e' : '#ef4444'
  const tradesLeft   = p.max_daily_trades - p.daily_trades

  // Progress: positive = toward target bar, negative = toward risk bar
  const rawProgress = p.daily_pnl >= 0
    ? Math.min(Math.abs(p.daily_pnl) / (p.daily_target_usd || 15) * 100, 100)
    : Math.min(Math.abs(p.daily_pnl) / (p.daily_risk_usd   || 25) * 100, 100)

  const statusLabel = {
    active:               'ACTIVE',
    daily_target_reached: '✓ TARGET HIT',
    daily_risk_limit_hit: '⚠ RISK LIMIT',
    max_trades_reached:   '— MAX TRADES',
  }[p.daily_status] || p.daily_status.toUpperCase()

  const statusColor = {
    active:               '#22c55e',
    daily_target_reached: '#c9a84c',
    daily_risk_limit_hit: '#ef4444',
    max_trades_reached:   '#888',
  }[p.daily_status] || '#888'

  return (
    <div className="rounded-xl border p-5" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      {/* Top row */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-gray-500 font-mono uppercase tracking-widest mb-1">Trade Buttler — Master Account</div>
          <div className="font-mono text-3xl font-bold" style={{ color: balColor }}>{fmt2(p.balance)}</div>
          <div className="text-sm font-mono mt-0.5" style={{ color: balColor }}>
            {fmtPct(p.roi_pct)} overall &nbsp;·&nbsp; Lot size: <span style={{ color: '#c9a84c' }}>{fmtLots(p.lot_size)}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500 font-mono mb-1">Today</div>
          <div className="font-mono text-2xl font-bold" style={{ color: dailyColor }}>{fmtPnl(p.daily_pnl)}</div>
          <div className="text-sm font-mono" style={{ color: dailyColor }}>{fmtPct(p.daily_pnl_pct)}</div>
        </div>
      </div>

      {/* Daily progress bar */}
      <div className="mt-4 space-y-1.5">
        <div className="flex justify-between text-xs font-mono text-gray-500">
          <span>
            Target: <span style={{ color: '#22c55e' }}>+{fmt2(p.daily_target_usd)}</span>
            &nbsp;·&nbsp;
            Limit: <span style={{ color: '#ef4444' }}>-{fmt2(p.daily_risk_usd)}</span>
          </span>
          <span style={{ color: statusColor }}>{statusLabel}</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
          <div className="h-full rounded-full transition-all duration-700"
            style={{ width: `${rawProgress}%`, background: p.daily_pnl >= 0 ? '#22c55e' : '#ef4444' }} />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-2 mt-4 text-center">
        {[
          { v: `${p.daily_trades}/${p.max_daily_trades}`, l: 'Trades Today',  c: tradesLeft > 0 ? '#c9a84c' : '#555' },
          { v: `${p.win_rate.toFixed(0)}%`,               l: 'Win Rate',      c: p.win_rate >= 50 ? '#22c55e' : '#ef4444' },
          { v: `${p.winning_trades}W/${p.losing_trades}L`, l: 'All Time',     c: '#888' },
          { v: `-${p.drawdown_pct.toFixed(1)}%`,           l: 'Drawdown',     c: p.drawdown_pct > 5 ? '#ef4444' : '#888' },
        ].map(({ v, l, c }) => (
          <div key={l} className="rounded p-2" style={{ background: '#080b0f' }}>
            <div className="font-mono font-bold text-sm" style={{ color: c }}>{v}</div>
            <div className="text-xs text-gray-600 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      {/* Strategy performance mini row */}
      {p.strategy_breakdown && Object.keys(p.strategy_breakdown).length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(p.strategy_breakdown).map(([sid, s]) => (
            <div key={sid} className="flex items-center gap-1.5 rounded px-2 py-1 text-xs font-mono"
              style={{ background: '#080b0f', borderLeft: `2px solid ${STRATEGY_COLORS[sid] || '#555'}` }}>
              <span style={{ color: STRATEGY_COLORS[sid] || '#888' }}>{s.label}</span>
              {s.total > 0
                ? <span style={{ color: s.pnl >= 0 ? '#22c55e' : '#ef4444' }}>{fmtPnl(s.pnl)}</span>
                : <span className="text-gray-600">no trades</span>}
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-4">
        <button onClick={onScanAll}
          className="flex-1 text-sm font-mono py-2 rounded border transition-colors hover:text-white"
          style={{ borderColor: '#c9a84c', color: '#c9a84c' }}>
          ⟳ Scan All Strategies
        </button>
        <button onClick={onReset}
          className="text-sm font-mono py-2 px-4 rounded border"
          style={{ borderColor: '#1a2030', color: '#555' }}>
          Reset
        </button>
      </div>
    </div>
  )
}

// ── Open trade row ─────────────────────────────────────────────────────────────

function OpenTradeRow({ t, currentPrices }) {
  const [expanded, setExpanded] = useState(false)
  const color    = STRATEGY_COLORS[t.strategy_id] || '#888'
  const isBuy    = t.direction === 'BUY'
  const dirColor = isBuy ? '#22c55e' : '#ef4444'

  const cur = currentPrices?.[t.symbol]
  const floatPnl = cur != null
    ? (isBuy ? cur - t.entry_price : t.entry_price - cur) * (t.units ?? t.lot_size ?? 1)
    : null
  const pnlColor = floatPnl == null ? '#888' : floatPnl >= 0 ? '#22c55e' : '#ef4444'

  return (
    <>
      <tr className="border-b cursor-pointer hover:bg-white/[0.02] transition-colors"
        style={{ borderColor: '#1a2030' }} onClick={() => setExpanded(x => !x)}>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">#{t.id}</td>
        <td className="py-2 px-3">
          <div className="font-mono text-xs font-bold text-gray-200">{t.symbol}</div>
          <div className="text-xs" style={{ color }}>{t.timeframe} · {t.strategy_id.replace(/_/g,' ')}</div>
        </td>
        <td className="py-2 px-3 font-mono text-xs font-bold" style={{ color: '#c9a84c' }}>{fmtLots(t.lot_size)}</td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded"
            style={{ background: `${dirColor}22`, color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmtTime(t.opened_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2 px-3 font-mono text-xs text-red-400">{fmt2(t.stop_loss)}</td>
        <td className="py-2 px-3 font-mono text-xs text-green-400">{fmt2(t.take_profit)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-400">{cur != null ? fmt2(cur) : '—'}</td>
        <td className="py-2 px-3 font-mono text-sm font-bold" style={{ color: pnlColor }}>
          {floatPnl != null ? fmtPnl(floatPnl) : <span className="text-yellow-400 text-xs animate-pulse">live</span>}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={10} className="px-4 py-3 space-y-1.5">
            <div className="flex flex-wrap gap-1">
              {t.reasons.map((r, i) => (
                <span key={i} className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#1a2030', color: '#888' }}>{r}</span>
              ))}
            </div>
            <div className="text-xs font-mono text-gray-600">Score {t.score}/9 · Risk {fmt2(t.risk_usd)}</div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Closed trade row ──────────────────────────────────────────────────────────

function ClosedTradeRow({ t }) {
  const [expanded, setExpanded] = useState(false)
  const color    = STRATEGY_COLORS[t.strategy_id] || '#888'
  const dirColor = t.direction === 'BUY' ? '#22c55e' : '#ef4444'
  const pnlColor = (t.pnl_usd ?? 0) >= 0 ? '#22c55e' : '#ef4444'
  const resultLabel = { win: 'TP', loss: 'SL', invalidated: 'EXIT' }[t.result] || t.result?.toUpperCase() || '—'
  const resultColor = { win: '#22c55e', loss: '#ef4444', invalidated: '#c9a84c' }[t.result] || '#888'

  return (
    <>
      <tr className="border-b cursor-pointer hover:bg-white/[0.02] transition-colors"
        style={{ borderColor: '#1a2030' }} onClick={() => setExpanded(x => !x)}>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">#{t.id}</td>
        <td className="py-2 px-3">
          <div className="font-mono text-xs font-bold text-gray-200">{t.symbol}</div>
          <div className="text-xs" style={{ color }}>{t.timeframe} · {t.strategy_id.replace(/_/g,' ')}</div>
        </td>
        <td className="py-2 px-3 font-mono text-xs font-bold" style={{ color: '#c9a84c' }}>{fmtLots(t.lot_size)}</td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded"
            style={{ background: `${dirColor}22`, color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmtTime(t.opened_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2 px-3 font-mono text-xs text-red-400">{fmt2(t.stop_loss)}</td>
        <td className="py-2 px-3 font-mono text-xs text-green-400">{fmt2(t.take_profit)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-500">{fmtTime(t.closed_at)}</td>
        <td className="py-2 px-3 font-mono text-xs text-gray-300">{fmt2(t.exit_price)}</td>
        <td className="py-2 px-3">
          <span className="text-xs font-mono font-bold mr-2" style={{ color: resultColor }}>{resultLabel}</span>
          <span className="font-mono text-sm font-bold" style={{ color: pnlColor }}>{fmtPnl(t.pnl_usd)}</span>
        </td>
      </tr>
      {expanded && t.analysis && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={11} className="px-4 py-3">
            <div className="text-xs font-mono p-2 rounded" style={{ background: '#0d1117', color: '#c9a84c', borderLeft: '2px solid #c9a84c' }}>
              {t.analysis}
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {t.reasons.map((r, i) => (
                <span key={i} className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#1a2030', color: '#666' }}>{r}</span>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Insights panel ────────────────────────────────────────────────────────────

function InsightsPanel() {
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
  }

  const factorRows = report?.factor_data
    ? Object.entries(report.factor_data).sort((a, b) => b[1].win_rate - a[1].win_rate)
    : []
  const stratRows = report?.strategy_data
    ? Object.entries(report.strategy_data).sort((a, b) => b[1].win_rate - a[1].win_rate)
    : []

  return (
    <div className="rounded-xl border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: '#1a2030' }}>
        <div>
          <span className="font-display font-bold" style={{ color: '#c9a84c' }}>AI Learning Engine</span>
          {report && <span className="text-xs text-gray-600 font-mono ml-3">{report.total_trades} trades · {new Date(report.created_at).toLocaleString()}</span>}
        </div>
        <button onClick={handleRun} disabled={running}
          className="text-xs font-mono px-4 py-1.5 rounded border"
          style={{ borderColor: '#c9a84c', color: running ? '#555' : '#c9a84c' }}>
          {running ? 'Analyzing…' : 'Run Now'}
        </button>
      </div>

      {loading ? <div className="text-center py-8 text-gray-600 font-mono text-sm">Loading…</div>
      : !report  ? <div className="text-center py-8 text-gray-600 font-mono text-sm">Need 5+ closed trades first.</div>
      : (
        <>
          <div className="flex border-b px-4" style={{ borderColor: '#1a2030' }}>
            {[['insights','Insights'],['factors','Factor Win Rates'],['strategies','By Strategy']].map(([id,lbl]) => (
              <button key={id} onClick={() => setTab(id)}
                className="text-xs font-mono px-3 py-2.5 border-b-2 mr-2"
                style={{ borderColor: tab===id ? '#c9a84c' : 'transparent', color: tab===id ? '#c9a84c' : '#555' }}>
                {lbl}
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
              factorRows.length === 0
                ? <p className="text-gray-600 text-xs font-mono text-center py-4">No factor data yet.</p>
                : <table className="w-full text-xs font-mono">
                    <thead><tr style={{ borderBottom:'1px solid #1a2030' }}>
                      {['Factor','Trades','Win Rate','W/L','PnL'].map(h=><th key={h} className="text-left px-2 py-2 text-gray-600">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {factorRows.map(([f,s]) => {
                        const c = s.win_rate>=60?'#22c55e':s.win_rate>=45?'#c9a84c':'#ef4444'
                        return <tr key={f} style={{ borderBottom:'1px solid #0d1117' }}>
                          <td className="px-2 py-2 text-gray-300">{f}</td>
                          <td className="px-2 py-2 text-gray-500">{s.occurrences}</td>
                          <td className="px-2 py-2">
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background:'#1a2030' }}>
                                <div className="h-full rounded-full" style={{ width:`${s.win_rate}%`, background:c }}/>
                              </div>
                              <span style={{ color:c }}>{s.win_rate}%</span>
                            </div>
                          </td>
                          <td className="px-2 py-2 text-gray-500">{s.wins}W/{s.losses}L</td>
                          <td className="px-2 py-2" style={{ color:s.pnl>=0?'#22c55e':'#ef4444' }}>{fmtPnl(s.pnl)}</td>
                        </tr>
                      })}
                    </tbody>
                  </table>
            )}
            {tab === 'strategies' && (
              stratRows.length === 0
                ? <p className="text-gray-600 text-xs font-mono text-center py-4">No strategy data yet.</p>
                : <table className="w-full text-xs font-mono">
                    <thead><tr style={{ borderBottom:'1px solid #1a2030' }}>
                      {['Strategy','Trades','Win Rate','Avg Win','Avg Loss','P Factor','PnL'].map(h=><th key={h} className="text-left px-2 py-2 text-gray-600">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {stratRows.map(([sid,s]) => {
                        const c = STRATEGY_COLORS[sid]||'#888'
                        return <tr key={sid} style={{ borderBottom:'1px solid #0d1117' }}>
                          <td className="px-2 py-2" style={{ color:c }}>{sid.replace(/_/g,' ')}</td>
                          <td className="px-2 py-2 text-gray-500">{s.total}</td>
                          <td className="px-2 py-2" style={{ color:s.win_rate>=50?'#22c55e':'#ef4444' }}>{s.win_rate}%</td>
                          <td className="px-2 py-2 text-green-500">{fmtPnl(s.avg_win)}</td>
                          <td className="px-2 py-2 text-red-400">{fmtPnl(s.avg_loss)}</td>
                          <td className="px-2 py-2" style={{ color:s.profit_factor>=1?'#22c55e':'#ef4444' }}>{s.profit_factor}x</td>
                          <td className="px-2 py-2" style={{ color:s.total_pnl>=0?'#22c55e':'#ef4444' }}>{fmtPnl(s.total_pnl)}</td>
                        </tr>
                      })}
                    </tbody>
                  </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PaperTrading() {
  const [portfolio, setPortfolio]     = useState(null)
  const [trades, setTrades]           = useState([])
  const [prices, setPrices]           = useState({})
  const [tab, setTab]                 = useState('open')
  const [loading, setLoading]         = useState(true)
  const [toast, setToast]             = useState(null)

  const load = useCallback(async () => {
    try {
      const [pRes, tRes, prRes] = await Promise.all([
        axios.get('/api/paper/portfolios'),
        axios.get('/api/paper/trades', { params: { limit: 300 } }),
        axios.get('/api/prices'),
      ])
      setPortfolio(pRes.data[0] || null)
      setTrades(tRes.data)
      setPrices(prRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [load])

  const showToast = (msg, color='#c9a84c') => {
    setToast({ msg, color })
    setTimeout(() => setToast(null), 3000)
  }

  const handleReset = async () => {
    if (!window.confirm('Reset master account?\nAll trades deleted, balance restored to $500.')) return
    await axios.post('/api/paper/reset')
    showToast('Account reset to $500')
    load()
  }

  const handleScanAll = async () => {
    await axios.post('/api/paper/scan-all')
    showToast('Scanning all strategies…')
    setTimeout(load, 4000)
  }

  const openTrades   = trades.filter(t => t.status === 'open')
  const closedTrades = trades.filter(t => t.status === 'closed')

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="text-gray-600 font-mono text-sm">Loading…</div>
    </div>
  )

  return (
    <div className="space-y-5">
      {toast && (
        <div className="fixed top-4 right-4 z-50 font-mono text-sm px-4 py-2 rounded shadow-lg"
          style={{ background: toast.color, color: '#000' }}>
          {toast.msg}
        </div>
      )}

      {/* Account card */}
      {portfolio
        ? <AccountCard p={portfolio} onReset={handleReset} onScanAll={handleScanAll} />
        : <div className="text-center py-10 text-gray-600 font-mono text-sm">No portfolio. Restart the backend.</div>
      }

      {/* AI Learning Engine */}
      <InsightsPanel />

      {/* Trade terminal */}
      <div className="rounded-xl border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
        {/* Tab bar */}
        <div className="flex border-b px-4" style={{ borderColor: '#1a2030' }}>
          {[
            ['open',    `Positions (${openTrades.length})`],
            ['history', `History (${closedTrades.length})`],
          ].map(([id, lbl]) => (
            <button key={id} onClick={() => setTab(id)}
              className="text-xs font-mono px-4 py-3 border-b-2 mr-1 transition-colors"
              style={{ borderColor: tab===id ? '#c9a84c' : 'transparent', color: tab===id ? '#c9a84c' : '#555' }}>
              {lbl}
            </button>
          ))}
        </div>

        {tab === 'open' && (
          openTrades.length === 0
            ? <div className="text-center py-10 text-gray-600 font-mono text-sm">
                No open positions.<br />
                <span className="text-xs">Waiting for confirmed signals — scanning every 5–30 min.</span>
              </div>
            : <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid #1a2030' }}>
                      {['#','Symbol','Lots','Type','Open Time','Open Price','S/L','T/P','Current','Profit'].map(h => (
                        <th key={h} className="text-left px-3 py-2.5 text-xs text-gray-600 font-mono">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {openTrades.map(t => <OpenTradeRow key={t.id} t={t} currentPrices={prices} />)}
                  </tbody>
                </table>
              </div>
        )}

        {tab === 'history' && (
          closedTrades.length === 0
            ? <div className="text-center py-10 text-gray-600 font-mono text-sm">No closed trades yet.</div>
            : <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid #1a2030' }}>
                      {['#','Symbol','Lots','Type','Open Time','Open Price','S/L','T/P','Close Time','Close Price','Result / Profit'].map(h => (
                        <th key={h} className="text-left px-3 py-2.5 text-xs text-gray-600 font-mono">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {closedTrades.map(t => <ClosedTradeRow key={t.id} t={t} />)}
                  </tbody>
                </table>
              </div>
        )}
      </div>
    </div>
  )
}
