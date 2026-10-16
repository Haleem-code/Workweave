'use client'

import { useCallback, useEffect, useState } from 'react'
import { Check, FileText, Plus, Users, X } from 'lucide-react'
import { api } from '../api'

export type Person = { id?: string; name: string; role: string; responsibility: string; evidence_ids: string[]; source_name?: string; quote?: string; current?: boolean }
type Directory = { people: Person[]; suggestions: Person[]; can_edit: boolean }
const blank: Person = { name: '', role: '', responsibility: '', evidence_ids: [] }

export function People({ base, onDocument, onCitation, compact = false }: { base: string; onDocument?: () => void; onCitation?: (id: string) => void; compact?: boolean }) {
  const [data, setData] = useState<Directory | null>(null)
  const [editing, setEditing] = useState<Person | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [members, setMembers] = useState<{ id: string; username: string; role: string }[]>([])
  const load = useCallback(async () => { setData(await api<Directory>(base + '/people')) }, [base])
  useEffect(() => { let active = true; setData(null); api<Directory>(base + '/people').then(value => { if (active) setData(value) }).catch(e => { if (active) setError(e.message) }); return () => { active = false } }, [base])
  const save = async (person: Person) => {
    setBusy(true); setError('')
    try { await api(base + '/people', 'POST', person); setEditing(null); await load(); setNotice('Person and responsibility saved.') } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  return <div className="people-directory">
    {!compact && <div className="page-heading"><div><span className="eyebrow">Your company</span><h1>People & roles</h1><p>Who does what, with the document behind each responsibility.</p></div>{data?.can_edit && <button className="primary" onClick={() => setEditing({ ...blank })}><Plus size={16} />Add a person</button>}</div>}
    {error && <div className="alert" role="alert">{error}</div>}{notice && <p className="notice" role="status">{notice}</p>}
    {!data && !error && <p role="status">Reading your company documents…</p>}
    {data && <>
      {!compact && <div className="ww-help-note"><Users size={20} /><div><strong>Start with a company profile or team guide.</strong><p>We suggest explicitly named roles and responsibilities. Review them before saving. Riders, delivery owners, and reporting lines need to be stated in your documents or added here.</p></div>{onDocument && <button className="secondary" onClick={onDocument}>Upload a document</button>}</div>}
      {editing && <form className="panel people-edit" onSubmit={e => { e.preventDefault(); save(editing) }}><div className="panel-heading"><h2>{editing.id ? 'Review this person' : 'Add a person'}</h2><button type="button" className="icon-button" aria-label="Close person form" onClick={() => setEditing(null)}><X size={17} /></button></div><label>Name<input required maxLength={120} value={editing.name} onChange={e => setEditing({ ...editing, name: e.target.value })} /></label><label>Role<input maxLength={160} value={editing.role} placeholder="For example, Delivery supervisor" onChange={e => setEditing({ ...editing, role: e.target.value })} /></label><label>What are they responsible for?<textarea maxLength={2000} rows={3} value={editing.responsibility} onChange={e => setEditing({ ...editing, responsibility: e.target.value })} /></label>{editing.quote && <blockquote><small>From the uploaded document</small>{editing.quote}</blockquote>}<button className="primary" disabled={busy}><Check size={16} />Confirm & save</button></form>}
      <section className="panel"><div className="panel-heading"><div><h2>Found in your documents</h2><p>Suggestions need your review. Documents never grant app permissions.</p></div><span className="pill">{data.suggestions.length} to review</span></div>
        {!data.suggestions.length && <p className="empty-inline">No new explicit roles found. Upload a company guide or add a person yourself.</p>}
        <div className="people-grid">{data.suggestions.map(person => <article className="person-card" key={person.id}><div className="person-initial">{person.name.split(' ').map(n => n[0]).slice(0, 2).join('')}</div><h3>{person.name}</h3><span className="badge needs_review">{person.role || 'Responsibility found'}</span><p>{person.responsibility}</p><small><FileText size={12} />{person.source_name}</small><div className="person-actions">{onCitation && <button className="text-button" onClick={() => onCitation(person.evidence_ids[0])}>Read source</button>}{data.can_edit && <button className="secondary" disabled={busy} onClick={() => { setEditing(person); setNotice('') }}>Review & save</button>}</div></article>)}</div>
      </section>
      {!!data.people.length && <section className="panel"><div className="panel-heading"><div><h2>Confirmed people</h2><p>Saved in your company graph. These are role records, not login accounts.</p></div><span className="pill">{data.people.length} records</span></div><div className="people-grid">{data.people.map(person => <article className="person-card" key={person.id}><h3>{person.name}</h3><span className={'badge ' + (person.current ? 'completed' : 'needs_review')}>{person.role || 'Company contact'}</span><p>{person.responsibility}</p>{person.current === false && <p className="ww-warning">The supporting document changed. Review the current source.</p>}{data.can_edit && <button className="text-button" onClick={() => setEditing(person)}>Edit details</button>}</article>)}</div></section>}
      {!compact && <details className="panel access-panel" onToggle={e => { if (e.currentTarget.open) api<typeof members>(base + '/members').then(setMembers).catch(err => setError(err.message)) }}><summary>Workspace access <span className="muted">· People who can sign in</span></summary><p>Adding a contact above does not invite them. Workspace accounts are managed separately.</p>{members.map(member => <div className="member-row" key={member.id}><span>{member.username}</span><span className="badge">{member.role}</span></div>)}{data.can_edit && <form className="people-edit" onSubmit={async e => { e.preventDefault(); const form = e.currentTarget; const values = new FormData(form); setBusy(true); setError(''); try { await api(base + '/members', 'POST', { username: values.get('username'), password: values.get('password') }); form.reset(); setMembers(await api<typeof members>(base + '/members')); setNotice('Workspace account created. Share the initial password privately.') } catch (err) { setError((err as Error).message) } finally { setBusy(false) } }}><h3>Create a workspace account</h3><label>Username<input name="username" required minLength={3} maxLength={60} pattern="[a-zA-Z0-9_.\-]+" autoComplete="off" /></label><label>Initial password<input type="password" name="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label><button className="secondary" disabled={busy}>Create account</button></form>}</details>}
    </>}
  </div>
}
