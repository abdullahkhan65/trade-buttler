import React from 'react'
import PriceStrip from '../components/PriceStrip'
import TradingChart from '../components/TradingChart'
import SignalList from '../components/SignalList'
import StatsPanel from '../components/StatsPanel'
import useSignals from '../hooks/useSignals'

export default function Dashboard({ prices, prevPrices, liveSignals }) {
  const { signals, stats, fetchSignals, recordResult } = useSignals()

  return (
    <div className="space-y-6">
      {/* Price Strip */}
      <PriceStrip prices={prices} prevPrices={prevPrices || {}} />

      {/* Stats */}
      <StatsPanel stats={stats} />

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="xl:col-span-2">
          <TradingChart liveSignals={liveSignals} prices={prices} />
        </div>

        {/* Live Signals */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-lg font-bold" style={{ color: '#c9a84c' }}>
              Live Signals
            </h2>
            <div className="flex items-center gap-1.5 text-xs text-green-400">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-dot" />
              Live
            </div>
          </div>

          {liveSignals && liveSignals.length > 0 ? (
            <SignalList signals={liveSignals} onRecordResult={recordResult} />
          ) : (
            <div className="text-center py-8 text-gray-600 font-mono text-sm rounded-lg border" style={{ borderColor: '#1a2030' }}>
              No active signals.<br />
              <span className="text-xs">Engine scanning every 60s...</span>
            </div>
          )}
        </div>
      </div>

      {/* Recent Signals */}
      <div>
        <h2 className="font-display text-lg font-bold mb-3" style={{ color: '#c9a84c' }}>
          Signal History
        </h2>
        <SignalList signals={signals.slice(0, 10)} onRecordResult={recordResult} />
      </div>
    </div>
  )
}
