'use client'

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, FileText, Upload, X } from 'lucide-react'
import { api, Company, Mapping, Preview, Profile, Source } from '../api'
import { workAreas, workspacePriorities } from '../company-context'
import { WeaveMark } from './Welcome'
import { ImportReview } from './ImportReview'
import { People } from './People'

type User = { id?: string; username: string }
interface Props { onSuccess: (user: User) => void; onSwitchToSignIn?: () => void; onCancel?: () => void; resumeCompany?: Company; initialProfile?: Profile; currentUser?: User }
const blankProfile: Profile = { description: '', responsibilities: '', procedure: '', confirmed: false, industry: '', workflow_priority: '', missing_information: '', onboarding_step: 'sources' }
const steps = ['Your work', 'Your focus', 'Your workspace', 'Your documents', 'Final review']

export function Setup({ onSuccess, onSwitchToSignIn, onCancel, resumeCompany, initialProfile, currentUser }: Props) {
  const [step, setStep] = useState(resumeCompany ? initialProfile?.onboarding_step === 'review' ? 4 : 3 : 0)
  const [company, setCompany] = useState<Company | null>(resumeCompany || null)
  const [account, setAccount] = useState<User | null>(currentUser || null)
  const [name, setName] = useState(resumeCompany?.name || '')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [profile, setProfile] = useState<Profile>({ ...blankProfile, ...initialProfile })
  const [otherArea, setOtherArea] = useState(Boolean(initialProfile?.industry && !workAreas.includes(initialProfile.industry)))
  const [previews, setPreviews] = useState<Preview[]>([])
  const [mappings, setMappings] = useState<Record<string, Mapping[]>>({})
  const [sources, setSources] = useState<Source[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const saveTail = useRef<Promise<unknown>>(Promise.resolve())
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const generation = useRef(0)
  const finished = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const base = company ? '/companies/' + company.id : ''
  const priority = workspacePriorities.find(item => item.id === profile.workflow_priority)
  const validArea = Boolean(profile.industry?.trim()) && (!otherArea || (profile.industry?.trim().length || 0) >= 2)

  const reloadSources = useCallback(async () => {
    if (!base) return
    const [accepted, pending] = await Promise.all([api<Source[]>(base + '/sources'), api<Preview[]>(base + '/imports')])
    setSources(accepted.filter(s => s.active)); setPreviews(pending)
    setMappings(old => Object.fromEntries(pending.map(p => [p.id, old[p.id] || p.tables.map(t => t.suggested_mapping)])))
  }, [base])
  useEffect(() => { reloadSources().catch(e => setError(e.message)) }, [reloadSources])
  useEffect(() => {
    heading.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [step])

  const stopAutosave = () => { if (saveTimer.current) clearTimeout(saveTimer.current); saveTimer.current = null; generation.current++ }
  const persist = (next: Profile) => {
    saveTail.current = saveTail.current.catch(() => {}).then(() => api(base + '/profile', 'PUT', next))
    return saveTail.current
  }
  // Serialize drafts and cancel the debounce before a final confirmation.
  useEffect(() => {
    if (!base || busy || finished.current) return
    const current = ++generation.current
    setSaved('Saving…')
    saveTimer.current = setTimeout(() => {
      saveTail.current = saveTail.current.catch(() => {}).then(() => api(base + '/profile', 'PUT', { ...profile, confirmed: false, onboarding_step: step === 4 ? 'review' : 'sources' }))
      saveTail.current.then(() => { if (current === generation.current) setSaved('All changes saved') }).catch(e => { if (current === generation.current) setSaved('Could not save: ' + e.message) })
    }, 650)
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); generation.current++ }
  }, [base, profile, step, busy])

  const run = async (action: () => Promise<void>) => {
    stopAutosave(); setBusy(true); setError('')
    try { await action() } catch (e) { finished.current = false; setError((e as Error).message) }
    finally { setBusy(false); setStatus('') }
  }
  const update = (key: keyof Profile, value: string) => setProfile(p => ({ ...p, [key]: value }))
  const advance = (nextStep: number) => {
    if (!company) { setError(''); setStep(nextStep); return }
    void run(async () => { await persist({ ...profile, confirmed: false, onboarding_step: 'sources' }); setStep(nextStep) })
  }
  const create = (event: FormEvent) => {
    event.preventDefault()
    if (company) { advance(3); return }
    void run(async () => {
      setStatus('Creating your workspace…')
      const result = await api<User & { company_id: string }>('/auth/signup', 'POST', { username: username.trim(), password, company_name: name.trim(), ...profile, industry: profile.industry?.trim() })
      setAccount(result); setCompany({ id: result.company_id, name: name.trim() }); setPassword(''); setStep(3)
    })
  }
  const upload = (files: FileList | File[]) => run(async () => {
    for (const file of Array.from(files)) {
      setStatus('Reading ' + file.name + '…')
      const form = new FormData(); form.append('file', file)
      const parsed = await api<Preview>(base + '/sources/upload', 'POST', form)
      setPreviews(old => [...old, parsed]); setMappings(old => ({ ...old, [parsed.id]: parsed.tables.map(t => t.suggested_mapping) }))
    }
  })
  const confirmImport = (preview: Preview) => run(async () => {
    setStatus('Importing ' + preview.filename + '…')
    await api(base + '/imports/' + preview.id + '/confirm', 'POST', { mappings: mappings[preview.id] || [] }); await reloadSources()
  })
  const review = () => run(async () => {
    await saveTail.current.catch(() => {})
    let next = { ...profile }
    if (sources.length && (!profile.description || !profile.responsibilities)) {
      setStatus('Reading company details from your documents…')
      const result = await api<{ draft: Partial<Profile> }>(base + '/profile/preview', 'POST')
      next = { ...profile, description: profile.description || result.draft.description || '', responsibilities: profile.responsibilities || result.draft.responsibilities || '', evidence_ids: [...new Set([...(profile.evidence_ids || []), ...(result.draft.evidence_ids || [])])] }
    }
    await persist({ ...next, confirmed: false, onboarding_step: 'review' })
    setProfile(next); setStep(4)
  })
  const activate = () => run(async () => {
    finished.current = true
    setStatus('Opening your workspace…')
    await saveTail.current.catch(() => {}); await api('/system/readiness')
    await persist({ ...profile, confirmed: true, onboarding_step: 'complete' })
    if (account) onSuccess(account)
  })
  const titles = ['What would you like to manage?', 'What would you like help with first?', company ? 'Your workspace, ready for you.' : 'Make this workspace yours.', 'Bring your company into the picture.', 'Does this look right?']
  const descriptions = ['Choose the closest fit. You can change this later.', 'Choose a starting point. All workspace tools stay available.', company ? 'Your account is created. You can still refine the company details.' : 'A name for your team, and a secure way to come back.', 'Start with a company guide, a procedure, or a spreadsheet.', 'Review what you shared before opening your workspace.']

  return <main className="ww-setup-screen">
    <header className="ww-setup-header">
      <span className="ww-wordmark"><WeaveMark />Workweave.</span>
      <div className="ww-setup-header-actions">
        {!company && onSwitchToSignIn && <button className="text-button" type="button" disabled={busy} onClick={onSwitchToSignIn}>Sign in <ArrowRight size={15} /></button>}
        {company && <span className="ww-setup-save" role="status">{saved || 'Workspace created'}</span>}
        {!company && onCancel && <button className="ww-setup-close" type="button" aria-label="Exit setup" disabled={busy} onClick={onCancel}><X size={18} /></button>}
      </div>
    </header>

    <section className={'ww-setup-stage ' + (step >= 3 ? 'ww-setup-stage-long' : '')} aria-busy={busy}>
      <div className="ww-setup-content" key={step}>
        <span className="ww-setup-step-label">{steps[step]}</span>
        <h1 id="setup-question" ref={heading} tabIndex={-1}>{titles[step]}</h1>
        <p className="ww-setup-description">{descriptions[step]}</p>
        {error && <div className="alert" role="alert"><span>{error}</span><button aria-label="Dismiss error" type="button" onClick={() => setError('')}><X size={16} /></button></div>}
        {status && <div className="notice" role="status"><span className="status-dot" />{status}</div>}

        {step === 0 && <fieldset className="ww-setup-fields" disabled={busy}>
          <legend className="sr-only">Work area</legend>
          <div className="ww-choice-pills" role="group" aria-labelledby="setup-question">
            {workAreas.map(area => <button type="button" className="ww-choice-pill" aria-pressed={!otherArea && profile.industry === area} key={area} onClick={() => { setOtherArea(false); update('industry', area) }}>{area}{!otherArea && profile.industry === area && <Check size={17} aria-hidden="true" />}</button>)}
            <button type="button" className="ww-choice-pill" aria-pressed={otherArea} onClick={() => { if (!otherArea) update('industry', ''); setOtherArea(true) }}>Other{otherArea && <Check size={17} aria-hidden="true" />}</button>
          </div>
          {otherArea && <label className="ww-setup-other">Your type of work<input value={profile.industry || ''} onChange={e => update('industry', e.target.value)} placeholder="For example, event production" maxLength={100} minLength={2} autoFocus /></label>}
        </fieldset>}

        {step === 1 && <fieldset className="ww-setup-fields" disabled={busy}>
          <legend className="sr-only">Workspace priority</legend>
          <div className="ww-choice-pills" role="group" aria-labelledby="setup-question">{workspacePriorities.map(item => <button type="button" className="ww-choice-pill" aria-pressed={profile.workflow_priority === item.id} key={item.id} onClick={() => update('workflow_priority', item.id)}>{item.label}{profile.workflow_priority === item.id && <Check size={17} aria-hidden="true" />}</button>)}</div>
          <p className="ww-setup-selection-help" aria-live="polite">{priority?.description || 'Pick the first thing you want to make easier.'}</p>
        </fieldset>}

        {step === 2 && <form id="setup-account" onSubmit={create} className="ww-setup-account">
          <fieldset className="ww-setup-fields ww-setup-inputs" disabled={busy}>
            <legend className="sr-only">Workspace and account details</legend>
            <label>Company or workspace name<input value={name} onChange={e => setName(e.target.value)} placeholder="Your company or team" required minLength={2} maxLength={100} readOnly={Boolean(company)} autoComplete="organization" /></label>
            {!company && <div className="ww-setup-account-row"><label>Email or username<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required minLength={3} maxLength={128} placeholder="you@company.com" /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" required minLength={12} maxLength={128} placeholder="At least 12 characters" /></label></div>}
            {company && <p className="ww-setup-account-note"><Check size={16} />Signed in as {account?.username}</p>}
            <label>What does your company do? <span className="optional">Optional</span><textarea value={profile.description} onChange={e => update('description', e.target.value)} placeholder="A sentence about your company, or add a company guide next." rows={3} maxLength={10000} /></label>
            {!company && <p className="ww-setup-document-hint">Your workspace starts with Ollama Cloud for AI answers. Questions and relevant excerpts are sent to Ollama Cloud, or a configured Groq or Gemini fallback if needed. You can change this in Settings before asking a question.</p>}
          </fieldset>
        </form>}

        {step === 3 && <div className="ww-setup-documents">
          <label className={'ww-upload-drop ' + (busy ? 'disabled' : '')} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!busy && e.dataTransfer.files.length) void upload(e.dataTransfer.files) }}><Upload size={25} /><strong>Choose files or drop them here</strong><span>PDF, Word, Excel, CSV, Markdown or text · up to 10 MB each</span><input type="file" multiple className="file-input" accept=".csv,.xlsx,.pdf,.docx,.md,.txt" disabled={busy} onChange={e => { if (e.target.files?.length) void upload(e.target.files); e.target.value = '' }} /></label>
          <p className="ww-setup-document-hint">Review each file before adding it to company knowledge. You can also add documents later.</p>
          {sources.map(source => <div className="ww-accepted-source" key={source.id}><FileText size={17} /><div><strong>{source.name}</strong><small>{source.record_count} records · {source.chunk_count} excerpts</small></div><span><Check size={13} /> Imported</span></div>)}
          {previews.map(preview => <ImportReview key={preview.id} preview={preview} mappings={mappings[preview.id] || preview.tables.map(t => t.suggested_mapping)} onChange={next => setMappings(old => ({ ...old, [preview.id]: next }))} onConfirm={() => { void confirmImport(preview) }} busy={busy} />)}
          <details className="ww-setup-connection-note"><summary>Already using Slack or ClickUp?</summary><p>Finish setup, then open Connections to read a selected demo channel or task list. You can preview its content before importing it.</p></details>
        </div>}

        {step === 4 && <div className="ww-setup-review">
          <div className="ww-setup-review-summary"><div><small>Workspace</small><strong>{name}</strong></div><div><small>Your work</small><strong>{profile.industry || 'Not specified'}</strong></div><div><small>Starting focus</small><strong>{priority?.label || 'Company knowledge'}</strong></div><button type="button" className="text-button" disabled={busy} onClick={() => setStep(0)}>Edit choices</button></div>
          {!!sources.length && <People base={base} compact />}
          <fieldset className="ww-setup-fields ww-setup-inputs" disabled={busy}>
            <legend className="sr-only">Confirm company details</legend>
            <label>What your company does<textarea rows={3} maxLength={10000} value={profile.description} onChange={e => update('description', e.target.value)} placeholder="A short description of your company" /></label>
            <label>Who owns the work? <span className="optional">Optional</span><textarea rows={2} maxLength={10000} value={profile.responsibilities} onChange={e => update('responsibilities', e.target.value)} placeholder="Teams and responsibilities. Leave blank if unknown." /></label>
            <details className="ww-setup-more-details"><summary>Procedures and anything still missing</summary><div className="ww-setup-inputs"><label>What procedure should your team follow?<textarea rows={3} maxLength={10000} value={profile.procedure} onChange={e => update('procedure', e.target.value)} placeholder="Your actual agreed procedure. Leave blank if unknown." /><small>Opening the workspace confirms this as your approved guidance.</small></label><label>What is still missing?<textarea rows={2} maxLength={10000} value={profile.missing_information || ''} onChange={e => update('missing_information', e.target.value)} placeholder="Unclear owners, missing dates, or documents to add later" /></label></div></details>
          </fieldset>
          <p className="ww-setup-document-hint">{sources.length ? sources.length + ' documents added. You can review their sources in your workspace.' : 'You can start now. Add documents when you are ready to ask company questions.'}</p>
        </div>}
      </div>
    </section>

    <footer className="ww-setup-footer">
      <div className="ww-setup-progress" role="progressbar" aria-label="Workspace setup" aria-valuemin={1} aria-valuemax={steps.length} aria-valuenow={step + 1} aria-valuetext={'Step ' + (step + 1) + ' of ' + steps.length + ': ' + steps[step]}><span style={{ width: (step + 1) / steps.length * 100 + '%' }} /></div>
      <div className="ww-setup-navigation">
        <button type="button" className="ww-setup-back" disabled={busy || (step === 0 && !onCancel)} onClick={() => { setError(''); if (step === 0) onCancel?.(); else setStep(step - 1) }}><ArrowLeft size={16} />Back</button>
        <span className="ww-setup-counter">{step + 1} <span>/</span> {steps.length}</span>
        {step < 2 && <button type="button" className="ww-setup-next" disabled={busy || (step === 0 ? !validArea : !priority)} onClick={() => advance(step + 1)}>Next <ArrowRight size={17} /></button>}
        {step === 2 && <button form="setup-account" type="submit" className="ww-setup-next" disabled={busy}>{busy ? 'Saving…' : company ? 'Next' : 'Create workspace'}<ArrowRight size={17} /></button>}
        {step === 3 && <button type="button" className="ww-setup-next" disabled={busy || previews.length > 0} onClick={() => { void review() }}>{busy ? 'Working…' : previews.length ? 'Review your files above' : sources.length ? 'Next' : 'Skip for now'}<ArrowRight size={17} /></button>}
        {step === 4 && <button type="button" className="ww-setup-next" disabled={busy} onClick={() => { void activate() }}>{busy ? 'Opening…' : 'Open workspace'}<ArrowRight size={17} /></button>}
      </div>
    </footer>
  </main>
}

