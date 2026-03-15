import React from 'react'
import SettingsForm from '../components/SettingsForm'

export default function Settings() {
  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-2" style={{ color: '#c9a84c' }}>
        Settings
      </h1>
      <p className="text-gray-500 text-sm font-mono mb-6">
        Configure email alerts and engine parameters.
      </p>
      <SettingsForm />
    </div>
  )
}
