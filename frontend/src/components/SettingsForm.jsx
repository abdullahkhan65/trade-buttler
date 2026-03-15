import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function SettingsForm() {
  const [config, setConfig] = useState({})
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    axios.get('/api/config').then((res) => {
      setConfig(res.data)
      setForm(res.data)
    })
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await axios.post('/api/config', {
        email_sender: form.email_sender,
        email_recipient: form.email_recipient,
        scan_interval: parseInt(form.scan_interval),
      })
      setMessage('Saved! Restart backend to apply.')
    } catch (e) {
      setMessage('Error saving config.')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const res = await axios.post('/api/test-email')
      setMessage(res.data.message)
    } catch (e) {
      setMessage('Email test failed.')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="space-y-4">
        {[
          { key: 'email_sender', label: 'Gmail Sender', placeholder: 'your@gmail.com' },
          { key: 'email_recipient', label: 'Alert Recipient', placeholder: 'alerts@gmail.com' },
          { key: 'scan_interval', label: 'Scan Interval (seconds)', placeholder: '60' },
        ].map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="block text-xs text-gray-500 mb-1 font-mono">{label}</label>
            <input
              type="text"
              placeholder={placeholder}
              value={form[key] || ''}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="w-full px-3 py-2 rounded text-sm font-mono"
              style={{ background: '#1a2030', border: '1px solid #2a3040', color: '#e6edf3' }}
            />
          </div>
        ))}

        <div className="text-xs text-gray-600 font-mono p-3 rounded" style={{ background: '#1a2030' }}>
          Note: Gmail App Password required. Regular Gmail password will not work.
          Get it at: myaccount.google.com → Security → App Passwords
        </div>

        {message && (
          <div className="text-sm font-mono p-3 rounded" style={{ background: '#1a2030', color: '#c9a84c' }}>
            {message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-2 rounded text-sm font-mono font-bold disabled:opacity-50"
            style={{ background: '#c9a84c', color: '#000' }}
          >
            {saving ? 'Saving...' : 'Save Config'}
          </button>
          <button
            onClick={handleTest}
            disabled={testing}
            className="flex-1 py-2 rounded text-sm font-mono border disabled:opacity-50"
            style={{ borderColor: '#c9a84c', color: '#c9a84c' }}
          >
            {testing ? 'Sending...' : 'Test Email'}
          </button>
        </div>
      </div>
    </div>
  )
}
