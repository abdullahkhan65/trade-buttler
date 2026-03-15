import React from 'react'
import SignalList from '../components/SignalList'
import useSignals from '../hooks/useSignals'

export default function Signals() {
  const { signals, recordResult, loading } = useSignals()

  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-6" style={{ color: '#c9a84c' }}>
        All Signals
      </h1>
      {loading ? (
        <div className="text-gray-500 font-mono text-sm">Loading...</div>
      ) : (
        <SignalList signals={signals} onRecordResult={recordResult} />
      )}
    </div>
  )
}
