import React, { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'
import axios from 'axios'

export default function TradingChart({ liveSignals }) {
  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const candleSeriesRef = useRef(null)
  const ema20SeriesRef = useRef(null)
  const ema50SeriesRef = useRef(null)
  const ema200SeriesRef = useRef(null)

  const [symbol, setSymbol] = useState('XAU/USD')
  const [interval, setInterval] = useState('1h')
  const [loading, setLoading] = useState(true)

  function calcEMA(data, period) {
    const k = 2 / (period + 1)
    const result = []
    let ema = null
    for (let i = 0; i < data.length; i++) {
      const close = data[i].close
      if (ema === null) {
        ema = close
      } else {
        ema = close * k + ema * (1 - k)
      }
      if (i >= period - 1) {
        result.push({ time: data[i].time, value: parseFloat(ema.toFixed(4)) })
      }
    }
    return result
  }

  const fetchAndRender = async () => {
    setLoading(true)
    try {
      const encoded = encodeURIComponent(symbol)
      const res = await axios.get(`/api/candles/${encoded}?interval=${interval}`)
      const candles = res.data

      if (candleSeriesRef.current && candles.length > 0) {
        candleSeriesRef.current.setData(candles)

        const ema20 = calcEMA(candles, 20)
        const ema50 = calcEMA(candles, 50)
        const ema200 = calcEMA(candles, 200)

        ema20SeriesRef.current?.setData(ema20)
        ema50SeriesRef.current?.setData(ema50)
        ema200SeriesRef.current?.setData(ema200)

        // Plot signal markers
        if (liveSignals && liveSignals.length > 0) {
          const markers = liveSignals
            .filter((s) => s.symbol === symbol)
            .map((s) => ({
              time: candles[candles.length - 1].time,
              position: s.direction === 'BUY' ? 'belowBar' : 'aboveBar',
              color: s.direction === 'BUY' ? '#22c55e' : '#ef4444',
              shape: s.direction === 'BUY' ? 'arrowUp' : 'arrowDown',
              text: `${s.direction} ${s.score}/9`,
            }))
          candleSeriesRef.current.setMarkers(markers)
        }
      }
    } catch (e) {
      console.error('Chart fetch error:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#1a2030' },
        horzLines: { color: '#1a2030' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#1a2030',
      },
      timeScale: {
        borderColor: '#1a2030',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 420,
    })

    chartRef.current = chart

    candleSeriesRef.current = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    ema20SeriesRef.current = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 1,
      title: 'EMA20',
    })

    ema50SeriesRef.current = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 1,
      title: 'EMA50',
    })

    ema200SeriesRef.current = chart.addLineSeries({
      color: '#ffffff',
      lineWidth: 1,
      title: 'EMA200',
      lineStyle: 2,
    })

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    fetchAndRender()
    const refreshInterval = setInterval(fetchAndRender, 60000)
    return () => clearInterval(refreshInterval)
  }, [symbol, interval])

  useEffect(() => {
    if (liveSignals && candleSeriesRef.current) {
      fetchAndRender()
    }
  }, [liveSignals])

  return (
    <div className="chart-container">
      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid #1a2030' }}>
        <div className="flex gap-2">
          {['XAU/USD', 'BTC/USD'].map((sym) => (
            <button
              key={sym}
              onClick={() => setSymbol(sym)}
              className="px-3 py-1.5 rounded text-xs font-mono transition-all"
              style={{
                background: symbol === sym ? '#c9a84c' : '#1a2030',
                color: symbol === sym ? '#000' : '#8b949e',
              }}
            >
              {sym}
            </button>
          ))}
        </div>

        <div className="flex gap-1">
          {['15m', '1h', '4h'].map((tf) => (
            <button
              key={tf}
              onClick={() => setInterval(tf)}
              className="px-3 py-1.5 rounded text-xs font-mono transition-all"
              style={{
                background: interval === tf ? '#1a2030' : 'transparent',
                color: interval === tf ? '#c9a84c' : '#8b949e',
                border: interval === tf ? '1px solid #c9a84c44' : '1px solid transparent',
              }}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 text-xs font-mono text-gray-600">
          <span style={{ color: '#3b82f6' }}>── EMA20</span>
          <span style={{ color: '#f59e0b' }}>── EMA50</span>
          <span style={{ color: '#ffffff80' }}>── EMA200</span>
        </div>
      </div>

      {/* Chart */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: '#0d1117' }}>
            <div className="text-gray-500 font-mono text-sm">Loading chart...</div>
          </div>
        )}
        <div ref={chartContainerRef} />
      </div>
    </div>
  )
}
