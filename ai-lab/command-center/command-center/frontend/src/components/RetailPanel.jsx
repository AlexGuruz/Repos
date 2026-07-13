import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function RetailPanel() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    api.retailHealth()
      .then(data => {
        if (mounted) setHealth(data)
      })
      .catch(err => {
        if (mounted) setError(err?.message || 'Retail health unavailable')
      })
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 20, color: 'rgba(255,255,255,0.82)' }}>
      <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 600 }}>Retail</h2>
      <p style={{ margin: '0 0 18px', color: 'rgba(255,255,255,0.55)', maxWidth: 720, lineHeight: 1.5 }}>
        Retail/Growflow integration hooks are available in read-only mode. No refresh, approval, capital,
        or reconciliation action is applied from this panel.
      </p>

      <div style={{
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 10,
        padding: 16,
        background: 'rgba(255,255,255,0.035)',
        maxWidth: 760,
      }}>
        <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>API status</div>
        {error ? (
          <div style={{ color: '#fca5a5', fontSize: 13 }}>{error}</div>
        ) : health ? (
          <pre style={{
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            color: '#d1d5db',
            fontSize: 12,
            lineHeight: 1.45,
          }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        ) : (
          <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 13 }}>Loading retail status...</div>
        )}
      </div>
    </div>
  )
}
