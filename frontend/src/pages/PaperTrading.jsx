import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt2 = (n) => (n == null ? '—' : `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
const fmtPnl = (n) => {
  if (n == null) return '—'
  const s = n >= 0 ? '+' : ''
  return `${s}$${Math.abs(n).toFixed(2)}`
}
const fmtPct = (n) => (n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`)
const timeAgo = (iso) => {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso)) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

const STRATEGY_COLORS = {
  '1h_baseline':     '#c9a84c',
  '4h_conservative': '#22c55e',
  '15m_aggressive':  '#f97316',
}

// ── Portfolio card ────────────────────────────────────────────────────────────

function PortfolioCard({ p, onReset, onScan }) {
  const color = STRATEGY_COLORS[p.strategy_id] || '#888'
  const balColor = p.roi_pct >= 0 ? '#22c55e' : '#ef4444'

  return (
    <div className="rounded-lg border p-5 space-y-4" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: `${color}22`, color }}>{p.timeframe.toUpperCase()}</span>
          <h3 className="font-display font-bold text-base mt-1" style={{ color }}>{p.label}</h3>
        </div>
        <div className="text-right">
          <div className="font-mono text-2xl font-bold" style={{ color: balColor }}>{fmt2(p.balance)}</div>
          <div className="text-xs font-mono" style={{ color: balColor }}>{fmtPct(p.roi_pct)} ROI</div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded p-2" style={{ background: '#080b0f' }}>
          <div className="text-lg font-mono font-bold text-white">{p.total_trades}</div>
          <div className="text-xs text-gray-500">Trades</div>
        </div>
        <div className="rounded p-2" style={{ background: '#080b0f' }}>
          <div className="text-lg font-mono font-bold text-green-400">{p.win_rate.toFixed(0)}%</div>
          <div className="text-xs text-gray-500">Win Rate</div>
        </div>
        <div className="rounded p-2" style={{ background: '#080b0f' }}>
          <div className="text-lg font-mono font-bold" style={{ color: p.drawdown_pct > 5 ? '#ef4444' : '#888' }}>
            -{p.drawdown_pct.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500">Drawdown</div>
        </div>
      </div>

      {/* W/L bar */}
      {p.total_trades > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{p.winning_trades}W</span>
            <span>{p.losing_trades}L</span>
            {p.open_trades > 0 && <span className="text-yellow-500">{p.open_trades} open</span>}
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#1a2030' }}>
            {p.total_trades > 0 && (
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(p.winning_trades / (p.winning_trades + p.losing_trades || 1)) * 100}%`,
                  background: '#22c55e'
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onScan(p.strategy_id)}
          className="flex-1 text-xs font-mono py-1.5 rounded border transition-colors hover:text-white"
          style={{ borderColor: color, color }}
        >
          Scan Now
        </button>
        <button
          onClick={() => onReset(p.strategy_id)}
          className="text-xs font-mono py-1.5 px-3 rounded border transition-colors"
          style={{ borderColor: '#1a2030', color: '#555' }}
        >
          Reset
        </button>
      </div>
    </div>
  )
}

// ── Trade row ─────────────────────────────────────────────────────────────────

function TradeRow({ t }) {
  const [expanded, setExpanded] = useState(false)
  const color = STRATEGY_COLORS[t.strategy_id] || '#888'
  const dirColor = t.direction === 'BUY' ? '#22c55e' : '#ef4444'
  const pnlColor = t.pnl_usd == null ? '#888' : t.pnl_usd >= 0 ? '#22c55e' : '#ef4444'

  const rr = t.take_profit && t.stop_loss && t.entry_price
    ? (Math.abs(t.take_profit - t.entry_price) / Math.abs(t.stop_loss - t.entry_price)).toFixed(1)
    : null

  return (
    <>
      <tr
        className="border-b cursor-pointer hover:bg-white/[0.02] transition-colors"
        style={{ borderColor: '#1a2030' }}
        onClick={() => setExpanded(x => !x)}
      >
        <td className="py-2.5 px-3">
          <span className="text-xs font-mono px-1.5 py-0.5 rounded" style={{ background: `${color}22`, color }}>
            {t.timeframe}
          </span>
        </td>
        <td className="py-2.5 px-3 font-mono text-xs text-gray-300">{t.symbol}</td>
        <td className="py-2.5 px-3">
          <span className="text-xs font-mono font-bold" style={{ color: dirColor }}>{t.direction}</span>
        </td>
        <td className="py-2.5 px-3 font-mono text-xs text-gray-300">{fmt2(t.entry_price)}</td>
        <td className="py-2.5 px-3 font-mono text-xs text-gray-400">{fmt2(t.stop_loss)}</td>
        <td className="py-2.5 px-3 font-mono text-xs text-gray-400">
          {fmt2(t.take_profit)}{rr && <span className="text-gray-600 ml-1">({rr}R)</span>}
        </td>
        <td className="py-2.5 px-3">
          {t.status === 'open' ? (
            <span className="text-xs font-mono text-yellow-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />OPEN
            </span>
          ) : (
            <span className="text-xs font-mono" style={{ color: t.result === 'win' ? '#22c55e' : '#ef4444' }}>
              {(t.result || 'closed').toUpperCase()}
            </span>
          )}
        </td>
        <td className="py-2.5 px-3 font-mono text-sm font-bold" style={{ color: pnlColor }}>
          {t.status === 'open' ? <span className="text-gray-600 text-xs">live</span> : fmtPnl(t.pnl_usd)}
        </td>
        <td className="py-2.5 px-3 text-xs text-gray-600">{timeAgo(t.opened_at)}</td>
      </tr>
      {expanded && (
        <tr style={{ background: '#080b0f' }}>
          <td colSpan={9} className="px-3 py-3">
            <div className="space-y-2">
              <div className="flex flex-wrap gap-1">
                {t.reasons.map((r, i) => (
                  <span key={i} className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: '#1a2030', color: '#888' }}>
                    {r}
                  </span>
                ))}
              </div>
              {t.analysis && (
                <div className="text-xs font-mono p-2 rounded" style={{ background: '#0d1117', color: '#c9a84c', borderLeft: '2px solid #c9a84c' }}>
                  {t.analysis}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PaperTrading() {
  const [portfolios, setPortfolios] = useState([])
  const [trades, setTrades] = useState([])
  const [filter, setFilter] = useState('all')   // all | open | closed
  const [stratFilter, setStratFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)

  const load = useCallback(async () => {
    try {
      const [pRes, tRes] = await Promise.all([
        axios.get('/api/paper/portfolios'),
        axios.get('/api/paper/trades', { params: { limit: 200 } }),
      ])
      setPortfolios(pRes.data)
      setTrades(tRes.data)
    } catch (e) {
      console.error('Failed to load paper trading data', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = window.setInterval(load, 15000)  // refresh every 15s
    return () => window.clearInterval(id)
  }, [load])

  const showToast = (msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const handleReset = async (strategyId) => {
    if (!window.confirm(`Reset ${strategyId} portfolio? This clears all trades and resets balance to $100.`)) return
    await axios.post(`/api/paper/reset/${strategyId}`)
    showToast(`${strategyId} reset to $100`)
    load()
  }

  const handleScan = async (strategyId) => {
    await axios.post(`/api/paper/scan/${strategyId}`)
    showToast(`Scanning ${strategyId}...`)
    setTimeout(load, 3000)
  }

  const filteredTrades = trades.filter(t => {
    if (filter === 'open' && t.status !== 'open') return false
    if (filter === 'closed' && t.status !== 'closed') return false
    if (stratFilter !== 'all' && t.strategy_id !== stratFilter) return false
    return true
  })

  const totalBalance = portfolios.reduce((s, p) => s + p.balance, 0)
  const totalInitial = portfolios.reduce((s, p) => s + p.initial_balance, 0)
  const totalRoi = totalInitial > 0 ? ((totalBalance - totalInitial) / totalInitial * 100) : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-gray-600 font-mono text-sm">Loading paper trading data...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 font-mono text-sm px-4 py-2 rounded" style={{ background: '#c9a84c', color: '#000' }}>
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: '#c9a84c' }}>Autonomous Paper Trading</h1>
          <p className="text-sm text-gray-600 mt-1 font-mono">3 strategies running 24/7 · auto-enters confirmed signals · monitors SL/TP every 10s</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-600 font-mono">Combined Portfolio</div>
          <div className="font-mono text-2xl font-bold" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmt2(totalBalance)}
          </div>
          <div className="text-xs font-mono" style={{ color: totalRoi >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmtPct(totalRoi)} total ROI
          </div>
        </div>
      </div>

      {/* Strategy cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {portfolios.map(p => (
          <PortfolioCard key={p.strategy_id} p={p} onReset={handleReset} onScan={handleScan} />
        ))}
      </div>

      {/* Trade history */}
      <div className="rounded-lg border" style={{ background: '#0d1117', borderColor: '#1a2030' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: '#1a2030' }}>
          <h2 className="font-display font-bold" style={{ color: '#c9a84c' }}>Trade Log</h2>
          <div className="flex gap-2 flex-wrap">
            {/* Status filter */}
            {['all', 'open', 'closed'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="text-xs font-mono px-3 py-1 rounded"
                style={{
                  background: filter === f ? '#c9a84c22' : 'transparent',
                  color: filter === f ? '#c9a84c' : '#555',
                  border: `1px solid ${filter === f ? '#c9a84c' : '#1a2030'}`,
                }}
              >{f}</button>
            ))}
            <div className="w-px mx-1" style={{ background: '#1a2030' }} />
            {/* Strategy filter */}
            {['all', ...portfolios.map(p => p.strategy_id)].map(s => (
              <button
                key={s}
                onClick={() => setStratFilter(s)}
                className="text-xs font-mono px-3 py-1 rounded"
                style={{
                  background: stratFilter === s ? '#1a2030' : 'transparent',
                  color: stratFilter === s ? '#fff' : '#555',
                  border: `1px solid ${stratFilter === s ? '#333' : '#1a2030'}`,
                }}
              >{s === 'all' ? 'All' : s.replace('_', ' ')}</button>
            ))}
          </div>
        </div>

        {filteredTrades.length === 0 ? (
          <div className="text-center py-12 text-gray-600 font-mono text-sm">
            No trades yet.<br />
            <span className="text-xs">Waiting for confirmed signals (score ≥ 8 for 1H/4H, ≥ 7 for 15M)</span>
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
          {[
            { id: '1h_baseline',     tf: '1H', risk: '2%', confirm: '8/9', rsi: '45–62 BUY / 38–55 SELL', sl: '1.5× ATR', tp: '3.0× ATR' },
            { id: '4h_conservative', tf: '4H', risk: '2%', confirm: '8/9', rsi: '46–60 BUY / 40–54 SELL', sl: '1.8× ATR', tp: '3.5× ATR' },
            { id: '15m_aggressive',  tf: '15M', risk: '1.5%', confirm: '7/9', rsi: '42–65 BUY / 35–58 SELL', sl: '1.2× ATR', tp: '2.5× ATR' },
          ].map(s => (
            <div key={s.id} className="rounded p-3 space-y-1" style={{ background: '#080b0f', borderLeft: `2px solid ${STRATEGY_COLORS[s.id]}` }}>
              <div style={{ color: STRATEGY_COLORS[s.id] }}>{s.id.replace('_', ' ')}</div>
              <div className="text-gray-600">Timeframe: <span className="text-gray-400">{s.tf}</span></div>
              <div className="text-gray-600">Risk/trade: <span className="text-gray-400">{s.risk}</span></div>
              <div className="text-gray-600">Min score: <span className="text-gray-400">{s.confirm}</span></div>
              <div className="text-gray-600">RSI zones: <span className="text-gray-400">{s.rsi}</span></div>
              <div className="text-gray-600">SL / TP: <span className="text-gray-400">{s.sl} / {s.tp}</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
