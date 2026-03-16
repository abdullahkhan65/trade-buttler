import React from 'react'

function PriceCard({ symbol, price, prevPrice }) {
  const isUp   = price != null && prevPrice != null && price > prevPrice
  const isDown = price != null && prevPrice != null && price < prevPrice

  const formatPrice = (p) => {
    if (p == null) return '—'
    if (symbol === 'BTC/USD') return p.toLocaleString('en-US', { maximumFractionDigits: 0 })
    return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  const changePct = price != null && prevPrice != null && prevPrice !== 0
    ? ((price - prevPrice) / prevPrice * 100)
    : null

  const color = isUp ? '#22c55e' : isDown ? '#ef4444' : '#c9a84c'

  return (
    <div
      className="flex-1 rounded-lg p-4 border"
      style={{ background: '#0d1117', borderColor: '#1a2030' }}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-gray-500 font-mono mb-1">{symbol}</div>
          <div className="font-mono text-2xl font-bold transition-colors" style={{ color }}>
            ${formatPrice(price)}
          </div>
        </div>
        <div className="text-3xl opacity-30">{symbol === 'XAU/USD' ? '🥇' : '₿'}</div>
      </div>
      <div className="mt-2 text-xs font-mono flex items-center gap-1" style={{ color: color }}>
        {isUp ? '▲' : isDown ? '▼' : '●'}
        {changePct != null
          ? ` ${changePct >= 0 ? '+' : ''}${changePct.toFixed(3)}%`
          : ' Live'}
      </div>
    </div>
  )
}

export default function PriceStrip({ prices, prevPrices = {} }) {
  return (
    <div className="flex gap-4">
      <PriceCard symbol="XAU/USD" price={prices['XAU/USD']} prevPrice={prevPrices['XAU/USD']} />
      <PriceCard symbol="BTC/USD" price={prices['BTC/USD']} prevPrice={prevPrices['BTC/USD']} />
    </div>
  )
}
