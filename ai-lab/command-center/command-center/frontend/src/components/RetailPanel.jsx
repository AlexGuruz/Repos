import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function RetailPanel() {
  const [status, setStatus] = useState({ loading: true, data: null, error: null })

  useEffect(() => {
    let mounted = true
    api.retailHealth()
      .then(data => {
        if (mounted) setStatus({ loading: false, data, error: null })
      })
      .catch(err => {
        if (mounted) setStatus({ loading: false, data: null, error: err.message })
      })
    return () => {
      mounted = false
    }
  }, [])

  const unavailable = status.error || status.data?.available === false

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 18, color: 'rgba(255,255,255,0.82)' }}>
      <div style={{
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: 10,
        padding: 16,
        background: 'rgba(255,255,255,0.035)',
        maxWidth: 760,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Retail dashboard</div>
        {status.loading ? (
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)' }}>Checking retail backend...</div>
        ) : unavailable ? (
          <div style={{ fontSize: 12, color: '#fbbf24', lineHeight: 1.5 }}>
            Retail tools are unavailable in this checkout. The Command Center is still running, and retail
            actions remain disabled until the trusted backend is configured.
            <div style={{ marginTop: 8, color: 'rgba(255,255,255,0.5)' }}>
              {status.error || status.data?.message || 'Retail backend disabled.'}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: '#86efac' }}>Retail backend is available.</div>
        )}
      </div>
    </div>
  )
}
