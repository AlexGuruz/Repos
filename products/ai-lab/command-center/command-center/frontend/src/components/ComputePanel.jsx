import { useEffect, useState, useCallback } from 'react'
import { useHardwareStore } from '../store'
import { api } from '../lib/api'
import { BarMeter, SectionLabel } from './Primitives'

const isDev = typeof import.meta !== 'undefined' && import.meta.env?.DEV

function fmtMaybeNum(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}

export default function ComputePanel() {
  const { gpu, cpu_percent, cpu, node, ram_used_gb, ram_total_gb, timestamp, vramHistory, update } = useHardwareStore()

  const [workersHealth, setWorkersHealth] = useState(null)
  const [fleetMap, setFleetMap] = useState(null)
  const [lastHardwareSnap, setLastHardwareSnap] = useState(null)
  const [hardwareFetchError, setHardwareFetchError] = useState(null)
  const [hardwareFetchAt, setHardwareFetchAt] = useState(null)
  const [workersFetchError, setWorkersFetchError] = useState(null)
  const [showRawWorker, setShowRawWorker] = useState(false)
  const [showRawHardware, setShowRawHardware] = useState(false)
  const [tunnelJobs, setTunnelJobs] = useState([])
  const [tunnelErr, setTunnelErr] = useState(null)
  const [cancelBusy, setCancelBusy] = useState(null)

  const fetchHardware = useCallback(() => {
    api.hardware()
      .then(snap => {
        setHardwareFetchError(null)
        setHardwareFetchAt(new Date().toISOString())
        update(snap)
        if (isDev) setLastHardwareSnap(snap)
      })
      .catch((e) => {
        const msg = e?.message ? String(e.message) : String(e)
        setHardwareFetchError(msg)
      })
  }, [update])

  const fetchWorkers = useCallback(() => {
    Promise.all([api.workersHealth(), api.workersMap().catch(() => null)])
      .then(([res, fmap]) => {
        setWorkersFetchError(null)
        setWorkersHealth(res)
        if (fmap) setFleetMap(fmap)
      })
      .catch((e) => {
        const msg = e?.message ? String(e.message) : String(e)
        setWorkersFetchError(msg)
        setWorkersHealth(null)
      })
  }, [])

  useEffect(() => {
    fetchHardware()
    const t = setInterval(fetchHardware, 5000)
    return () => clearInterval(t)
  }, [fetchHardware])

  useEffect(() => {
    fetchWorkers()
    const t = setInterval(fetchWorkers, 15000)
    return () => clearInterval(t)
  }, [fetchWorkers])

  const fetchTunnelJobs = useCallback(() => {
    api.tunnelJobs()
      .then(res => {
        setTunnelErr(null)
        setTunnelJobs(Array.isArray(res?.jobs) ? res.jobs : [])
      })
      .catch((e) => {
        setTunnelErr(e?.message ? String(e.message) : String(e))
      })
  }, [])

  useEffect(() => {
    fetchTunnelJobs()
    const t = setInterval(fetchTunnelJobs, 5000)
    return () => clearInterval(t)
  }, [fetchTunnelJobs])

  async function cancelTunnelJob(jobId) {
    if (!jobId || cancelBusy) return
    setCancelBusy(jobId)
    try {
      await api.tunnelJobCancel(jobId)
      fetchTunnelJobs()
    } catch (e) {
      setTunnelErr(e?.message ? String(e.message) : String(e))
    } finally {
      setCancelBusy(null)
    }
  }

  const snapshotTime = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null

  const vramUsed = gpu?.vram_used_gb ?? null
  const vramTotal = gpu?.vram_total_gb ?? null
  const gpuUtil = gpu?.utilization_pct ?? null
  const gpuTemp = gpu?.temp_c ?? null
  const cpuPct = cpu_percent ?? cpu?.total_usage_percent ?? null

  const cpuTempC = cpu?.package_temp_c ?? null
  const cpuFreqMhz = cpu?.frequency_current_mhz ?? null

  const memUsed = ram_used_gb ?? null
  const memTotal = ram_total_gb ?? null
  const memPct = memTotal && memTotal > 0 ? Math.round(((memUsed || 0) / memTotal) * 100) : null

  const collectorsUnavailable =
    !hardwareFetchError &&
    gpu == null &&
    (memTotal === 0 || memTotal === 0.0) &&
    (memUsed === 0 || memUsed === 0.0)

  const cpuSubParts = [
    node ? `node:${node}` : null,
    cpuTempC != null ? `temp:${Math.round(cpuTempC)}°C` : null,
    cpuFreqMhz != null ? `${Math.round(cpuFreqMhz)} MHz` : null,
  ].filter(Boolean)

  const cpuSub = cpuSubParts.length ? cpuSubParts.join(' · ') : '—'

  const cpuProcesses = Array.isArray(cpu?.process_top) ? cpu.process_top : []

  const vramDenom = vramTotal && vramTotal > 0 ? vramTotal : 24

  return (
    <div className="flex-1 overflow-y-auto">
      {snapshotTime && (
        <div className="px-3 py-1 text-[9px] text-white/20 font-mono">Snapshot: {snapshotTime}</div>
      )}
      {hardwareFetchError && (
        <div className="px-3 py-1 text-[10px] text-red-400/90 font-mono border-b border-red-500/20">
          Hardware fetch failed: {hardwareFetchError}
          {hardwareFetchAt ? ` (last attempt: ${hardwareFetchAt})` : ''}
        </div>
      )}
      {collectorsUnavailable && (
        <div className="px-3 py-1 text-[10px] text-amber-300/90 font-mono border-b border-amber-500/20">
          Hardware metrics appear unavailable in the backend (GPU query failed and CPU/RAM readings are returning 0). This usually means `psutil` and/or `nvidia-smi` are missing from the backend runtime environment.
        </div>
      )}

      {/* Metric row */}
      <div
        className="grid gap-2 p-3 border-b border-white/8"
        style={{ gridTemplateColumns: 'repeat(6, minmax(0, 1fr))' }}
      >
        {[
          {
            label: 'tokens · AI models',
            value: '—',
            sub: 'backend does not expose token usage yet',
          },
          {
            label: 'gpu utilization',
            value: gpuUtil != null ? `${fmtMaybeNum(gpuUtil, 0)}%` : '—',
            sub: gpu?.name ? String(gpu.name) : 'GPU name not available',
          },
          {
            label: 'gpu vram',
            value: vramUsed != null ? `${fmtMaybeNum(vramUsed, 1)}GB` : '—',
            sub: vramTotal != null ? `/ ${fmtMaybeNum(vramTotal, 1)}GB` : 'total not available',
          },
          {
            label: 'gpu temp',
            value: gpuTemp != null ? `${fmtMaybeNum(gpuTemp, 0)}°C` : '—',
            sub: gpuUtil != null ? `util ${fmtMaybeNum(gpuUtil, 0)}%` : 'util not available',
          },
          {
            label: 'cpu utilization',
            value: cpuPct != null ? `${fmtMaybeNum(cpuPct, 1)}%` : '—',
            sub: cpuSub,
          },
          {
            label: 'memory',
            value: memUsed != null ? `${fmtMaybeNum(memUsed, 1)}GB` : '—',
            sub: memTotal != null ? `/ ${fmtMaybeNum(memTotal, 1)}GB${memPct != null ? ` (${memPct}% used)` : ''}` : 'total not available',
          },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="text-[10px] text-white/35 mb-1">{m.label}</div>
            <div className="text-[18px] font-mono font-medium text-white/85">{m.value}</div>
            <div className="text-[10px] text-white/25 mt-0.5">{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Worker services (Guru §26): tunnel, last_checked, per-service latency, ssh_configured, error */}
      {workersHealth && (
        <div className="px-3 py-3 border-t border-white/8">
          <div className="flex items-center gap-2 flex-wrap">
            <SectionLabel>Worker services · {workersHealth.worker_name ?? 'power-1'}</SectionLabel>
            {typeof workersHealth.ssh_configured === 'boolean' && (
              <span className="text-[9px] text-white/35" title="SSH configured for this worker">
                SSH: {workersHealth.ssh_configured ? 'yes' : 'no'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-[10px] flex-wrap">
            <span
              className="inline-flex items-center gap-1.5 font-mono px-2 py-0.5 rounded border"
              style={{
                borderColor: workersHealth.critical_ok ? 'rgba(34,197,94,0.55)' : 'rgba(239,68,68,0.55)',
                color: workersHealth.critical_ok ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.95)',
              }}
              title="Critical path = Worker Assistant HTTP /health on power-1 :8765"
            >
              <span
                className="inline-block rounded-full flex-shrink-0"
                style={{
                  width: 6,
                  height: 6,
                  background: workersHealth.critical_ok ? '#22c55e' : '#ef4444',
                }}
              />
              Critical: {workersHealth.critical_ok ? 'OK' : 'DOWN'}
              {typeof workersHealth.worker_assistant_ok === 'boolean' && (
                <span className="text-white/35">· WA {workersHealth.worker_assistant_ok ? 'up' : 'down'}</span>
              )}
            </span>
            {workersHealth.tunnel_status && (
              <span className="text-white/45 inline-flex items-center gap-1.5">
                <span
                  className="inline-block rounded-full flex-shrink-0"
                  style={{
                    width: 6,
                    height: 6,
                    background: workersHealth.tunnel_status.likely_up ? '#22c55e' : '#ef4444',
                  }}
                />
                Tunnel: {workersHealth.tunnel_status.likely_up ? 'up' : 'down'}
                <span className="text-white/30">·</span>
                <span title={workersHealth.tunnel_status.detail}>
                  {workersHealth.tunnel_status.detail?.slice(0, 50) ?? '—'}
                </span>
              </span>
            )}
            {typeof workersHealth.all_ok === 'boolean' && !workersHealth.all_ok && workersHealth.critical_ok && (
              <span className="text-white/30" title="all_ok requires WA + n8n + ollama; critical_ok is WA only">
                (secondary services degraded)
              </span>
            )}
          </div>
          {workersHealth.last_checked && (
            <div className="text-[9px] text-white/25 mt-0.5">Last checked: {workersHealth.last_checked}</div>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {workersHealth.services?.map(s => (
              <span
                key={s.name}
                className="text-[10px] font-mono px-2 py-1 rounded border"
                style={{
                  borderColor: s.ok ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)',
                  color: s.ok ? 'rgba(34,197,94,0.9)' : 'rgba(239,68,68,0.9)',
                  opacity: s.name === 'worker_assistant' ? 1 : 0.85,
                }}
                title={[
                  s.name === 'worker_assistant' ? 'critical' : 'secondary',
                  s.detail,
                  s.latency_ms != null ? `${s.latency_ms.toFixed(0)} ms` : '',
                ].filter(Boolean).join(' · ')}
              >
                {s.name}: {s.ok ? (s.latency_ms != null ? `ok ${s.latency_ms.toFixed(0)}ms` : 'ok') : (s.detail ?? '—')}
              </span>
            ))}
          </div>
          {workersHealth.error && (
            <div className="text-[10px] text-white/40 mt-1">{workersHealth.error}</div>
          )}
        </div>
      )}
      {fleetMap?.nodes?.length > 0 && (
        <div className="px-3 py-2 border-t border-white/8 text-[10px] font-mono text-white/50 space-y-1">
          <SectionLabel>Fleet map · WORKER_CURRENT</SectionLabel>
          {fleetMap.nodes.map((n) => (
            <div key={n.id} title={n.notes}>
              {n.id}: {n.status}
              {n.tunnel_status?.expected_ports?.length
                ? ` · ports ${n.tunnel_status.reachable_ports?.join(',') || '—'} / ${n.tunnel_status.expected_ports.join(',')}`
                : ' · local only'}
            </div>
          ))}
        </div>
      )}
      {workersFetchError && (
        <div className="px-3 py-2 text-[10px] text-red-400/80 font-mono border-t border-red-500/20">
          Workers health fetch failed: {workersFetchError}
        </div>
      )}
      {/* Tunnel scheduler jobs — cancel queued/running (soft remote) */}
      <div className="px-3 py-3 border-t border-white/8">
        <SectionLabel>Tunnel jobs · cancel</SectionLabel>
        {tunnelErr && (
          <div className="text-[10px] text-red-400/80 font-mono mb-1">{tunnelErr}</div>
        )}
        {tunnelJobs.length === 0 ? (
          <div className="text-[11px] text-white/30">No in-flight tunnel jobs.</div>
        ) : (
          <div className="space-y-1.5 mt-1">
            {tunnelJobs.slice(0, 8).map(j => (
              <div key={j.job_id} className="flex items-center gap-2 text-[10px] font-mono text-white/70">
                <span className="text-white/40">{j.status}</span>
                <span className="truncate" title={j.job_id}>{j.op || 'op'} · {j.lane} · {j.age_ms}ms</span>
                <button
                  type="button"
                  disabled={cancelBusy === j.job_id}
                  onClick={() => void cancelTunnelJob(j.job_id)}
                  className="ml-auto px-2 py-0.5 rounded border text-white/60 hover:text-white/90 disabled:opacity-40"
                  style={{ borderColor: 'rgba(239,68,68,0.35)' }}
                  title="Cancel local scheduler job (remote WA abort is soft)"
                >
                  {cancelBusy === j.job_id ? '…' : 'Cancel'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>



      {/* Top CPU processes (from backend cpu.process_top) */}
      <div className="px-3 py-3">
        <SectionLabel>Top CPU processes · live</SectionLabel>
        {cpuProcesses.length === 0 ? (
          <div className="text-[11px] text-white/30">CPU process telemetry not available in the current hardware payload.</div>
        ) : (
          <div className="space-y-2">
            {cpuProcesses.slice(0, 7).map(p => (
              <div key={`${p.pid}-${p.name}`} className="rounded-lg p-2.5 border border-white/5" style={{ background: 'rgba(255,255,255,0.02)' }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] text-white/85 font-mono truncate">{p.name}</div>
                    <div className="text-[9px] text-white/25 font-mono">pid {p.pid}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[12px] font-mono text-white/75">{p.cpu_percent != null ? `${Number(p.cpu_percent).toFixed(1)}%` : '—'}</div>
                    <div className="text-[9px] text-white/25 font-mono">
                      {p.gpu_memory_mb != null ? `GPU mem ~${Math.round(p.gpu_memory_mb / 1024)}GB` : 'GPU mem —'}
                    </div>
                  </div>
                </div>
                <div className="mt-2">
                  <BarMeter value={p.cpu_percent ?? 0} max={100} color="#4338ca" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mini VRAM sparkline */}
      <div className="px-3 py-3">
        <SectionLabel>vram history · last snapshots</SectionLabel>
        <div className="flex items-end gap-0.5" style={{ height: 48 }}>
          {(vramHistory.length ? vramHistory : Array(20).fill({ value: 0 })).map((p, i) => {
            const h = Math.max(2, Math.round((p.value / vramDenom) * 48))
            return (
              <div
                key={i}
                className="flex-1 rounded-sm transition-all duration-500"
                style={{ height: h, background: `rgba(15,110,86,${0.3 + (h / 48) * 0.6})` }}
              />
            )
          })}
        </div>
        <div className="flex justify-between text-[9px] font-mono text-white/20 mt-1">
          <span>0GB</span>
          <span>{vramTotal != null ? `${vramTotal}GB` : '—'}</span>
        </div>
      </div>

      {/* Dev-only raw payloads for contract verification */}
      {isDev && (
        <div className="px-3 py-3 border-t border-white/10 space-y-2">
          <SectionLabel>Debug · raw payloads</SectionLabel>
          {workersHealth && (
            <div>
              <button
                type="button"
                onClick={() => setShowRawWorker(v => !v)}
                className="text-[10px] text-white/40 hover:text-white/70"
              >
                {showRawWorker ? '▼' : '▶'} Raw worker health
              </button>
              {showRawWorker && (
                <pre className="mt-1 p-2 rounded bg-black/40 text-[10px] font-mono text-white/60 overflow-x-auto max-h-48 overflow-y-auto">
                  {JSON.stringify(workersHealth, null, 2)}
                </pre>
              )}
            </div>
          )}
          {lastHardwareSnap != null && (
            <div>
              <button
                type="button"
                onClick={() => setShowRawHardware(v => !v)}
                className="text-[10px] text-white/40 hover:text-white/70"
              >
                {showRawHardware ? '▼' : '▶'} Raw hardware snapshot
              </button>
              {showRawHardware && (
                <pre className="mt-1 p-2 rounded bg-black/40 text-[10px] font-mono text-white/60 overflow-x-auto max-h-48 overflow-y-auto">
                  {JSON.stringify(lastHardwareSnap, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
