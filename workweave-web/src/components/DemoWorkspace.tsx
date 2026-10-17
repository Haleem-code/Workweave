'use client'

import { useRef, useState } from 'react'
import { ArrowRight, GitBranch } from 'lucide-react'
import { api, Company, RunStatus } from '../api'

export function DemoWorkspace({ onReady }: { onReady: (company: Company) => Promise<void> }) {
  const pending = useRef(false)
  const created = useRef<Company | null>(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const start = async () => {
    if (pending.current) return
    pending.current = true; setBusy(true); setError('')
    try {
      if (failed && created.current) {
        await onReady(created.current)
        return
      }
      setStatus('Creating your separate example workspace…')
      created.current = await api<Company>('/companies', 'POST', { name: 'Harbor Supply · example' })
      setStatus('Importing fictional orders and checking the delayed shipment…')
      const base = '/companies/' + created.current.id
      const started = await api<{ runs: RunStatus[] }>(base + '/demo', 'POST', {})
      const runId = started.runs[0]?.id
      if (!runId) throw new Error('The example did not start.')
      // Short reads keep progress recoverable across proxy timeouts. The backend
      // persists the setup checkpoint and resumes it after a process restart.
      let ready = false
      for (let attempt = 0; attempt < 180; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 1500))
        const run = await api<RunStatus>(base + '/runs/' + runId)
        if (run.status === 'blocked') throw new Error(run.error || 'Example preparation needs attention.')
        if (run.checkpoint !== 'preparing_example') { ready = true; break }
      }
      if (!ready) throw new Error('Preparation is still running. You can reopen the example workspace to check progress.')
      setStatus('Opening the investigation…')
      await onReady(created.current)
    } catch (e) {
      setFailed(Boolean(created.current))
      setError((e as Error).message + (created.current ? ' Your example workspace was created. Open it to check the saved progress before trying again.' : ''))
    } finally { pending.current = false; setBusy(false); setStatus('') }
  }
  return <section className="example-workspace" aria-label="Try a graph investigation" aria-busy={busy}>
    <span className="example-icon"><GitBranch size={24} /></span>
    <div><span className="eyebrow">Try it with fictional company data</span><h2>One late shipment. Which promises need attention?</h2><p>Follow a real graph investigation from a changed delivery date to customer orders, evidence, responsible teams, and saved review tasks.</p><small>Creates a separate Harbor Supply workspace. This example runs a deterministic graph workflow; it does not generate an AI answer.</small>
    {status && <p role="status">{status}</p>}{error && <p role="alert" className="alert">{error}</p>}</div>
    <button className="secondary" disabled={busy} onClick={() => { void start() }}>{busy ? 'Preparing example…' : failed ? 'Open example workspace' : 'Try the example'}<ArrowRight size={16} /></button>
  </section>
}
