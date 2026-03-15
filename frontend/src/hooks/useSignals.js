import { useState, useEffect } from 'react'
import axios from 'axios'

export default function useSignals() {
  const [signals, setSignals] = useState([])
  const [liveSignals, setLiveSignals] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchSignals = async () => {
    try {
      const [allRes, liveRes, statsRes] = await Promise.all([
        axios.get('/api/signals'),
        axios.get('/api/signals/live'),
        axios.get('/api/stats'),
      ])
      setSignals(allRes.data)
      setLiveSignals(liveRes.data)
      setStats(statsRes.data)
    } catch (e) {
      console.error('Failed to fetch signals:', e)
    } finally {
      setLoading(false)
    }
  }

  const recordResult = async (signalId, result, pnlPips) => {
    await axios.post(`/api/signals/${signalId}/result`, { result, pnl_pips: pnlPips })
    await fetchSignals()
  }

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 30000)
    return () => clearInterval(interval)
  }, [])

  return { signals, liveSignals, stats, loading, fetchSignals, recordResult }
}
