import React, { useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Header from './components/Header'
import Dashboard from './pages/Dashboard'
import Signals from './pages/Signals'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Backtest from './pages/Backtest'
import FactorAnalysis from './pages/FactorAnalysis'
import useWebSocket from './hooks/useWebSocket'

export default function App() {
  const [prices, setPrices] = useState({ 'XAU/USD': null, 'BTC/USD': null })
  const [liveSignals, setLiveSignals] = useState([])
  const [engineStatus, setEngineStatus] = useState('connecting')
  const { lastMessage, isConnected } = useWebSocket('ws://localhost:8000/ws')

  useEffect(() => {
    setEngineStatus(isConnected ? 'live' : 'offline')
  }, [isConnected])

  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage
    if (msg.type === 'price_update') {
      setPrices(prev => ({ ...prev, [msg.symbol]: msg.price }))
    } else if (msg.type === 'new_signal' || msg.type === 'signal_update') {
      setLiveSignals(prev => {
        const filtered = prev.filter(s => s.symbol !== msg.symbol)
        return [msg, ...filtered]
      })
    }
  }, [lastMessage])

  const navItems = [
    { to: '/', label: 'Dashboard' },
    { to: '/signals', label: 'Signals' },
    { to: '/analytics', label: 'Analytics' },
    { to: '/backtest', label: 'Strategy Lab' },
    { to: '/factors', label: 'Factors' },
    { to: '/settings', label: 'Settings' },
  ]

  return (
    <div className="min-h-screen" style={{ background: '#080b0f' }}>
      <Header engineStatus={engineStatus} />
      <nav className="border-b" style={{ borderColor: '#1a2030', background: '#0d1117' }}>
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {navItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `px-4 py-3 text-sm font-mono whitespace-nowrap transition-colors border-b-2 ${
                  isActive
                    ? 'border-yellow-500 text-yellow-400'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard prices={prices} liveSignals={liveSignals} />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/factors" element={<FactorAnalysis />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
