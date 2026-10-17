'use client'

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Activity, ArrowRight, BookOpen, Building2, Check, ChevronDown, Database, FileText, History, Layers3, Menu, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Search, Settings2, ShieldCheck, Sparkles, Upload, Users, Workflow, X } from 'lucide-react'
import { People } from './components/People'
import { Account, AccountMenu, WorkspaceSwitcher } from './components/WorkspaceChrome'
import { ConversationHistory, ConversationSummary, RecentActivity } from './components/ConversationHistory'
import { api, ApiError, Company, EvidenceReference, GraphPath, Mapping, MemoryEntry, Message, Preview, Profile, ProviderSettings, RunStatus, Source, Task } from './api'
import { Setup } from './components/Setup'
import { AISettings } from './components/AISettings'
import { DemoWorkspace } from './components/DemoWorkspace'
import { workAreas, workspacePriorities } from './company-context'
import { Welcome, WeaveMark } from './components/Welcome'
import type { Readiness } from './api'

const navSections = [
  {
    category: 'YOUR WORKSPACE',
    items: [
      { name: 'Work', label: 'Home', hint: 'Your next steps', icon: Layers3 },
      { name: 'Assistant', label: 'Ask', hint: 'Questions & answers', icon: MessageSquare }
    ]
  },
  {
    category: 'YOUR COMPANY',
    items: [
      { name: 'Sources', label: 'Documents', hint: 'Upload & update files', icon: FileText },
      { name: 'People', label: 'People & roles', hint: 'Who does what', icon: Users },
      { name: 'Company', label: 'Company', hint: 'About your business', icon: Building2 }
    ]
  },
  {
    category: 'MANAGE',
    items: [
      { name: 'Settings', label: 'Settings', hint: 'Appearance & AI', icon: Settings2 }
    ]
  }
]

const emptyProfile = { description: '', responsibilities: '', procedure: '', confirmed: false }
const normalizeProfile = (data: Profile): Profile => ({ ...data, onboarding_step: data.onboarding_step || (data.confirmed ? 'complete' : 'sources') })

const stamp = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })

function WorkspaceLoading({ text, error }: { text: string; error?: string }) {
  return <main className="workspace-loading" aria-busy={!error}><span className="ww-wordmark"><WeaveMark />Workweave.</span><div className="loading-indicator"><span className="loading-spinner" /><p role="status">{text}</p></div>{error && <div className="alert" role="alert">{error}<button onClick={() => window.location.reload()}>Retry</button></div>}</main>
}

function Badge({ value }: { value: string }) {
  return <span className={'badge ' + value.replaceAll(' ', '_')}>{value.replaceAll('_', ' ')}</span>
}

export default function App() {
  const [user, setUser] = useState<Account | null>(null)
  const accountKey = user?.id || user?.username || ''
  const [workspacesFor, setWorkspacesFor] = useState('')
  const [checking, setChecking] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [companies, setCompanies] = useState<Company[]>([])
  const [company, setCompany] = useState<Company | null>(null)
  const [screen, setScreen] = useState('Work')
  const [mobileNav, setMobileNav] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [runs, setRuns] = useState<RunStatus[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<RunStatus | null>(null)
  const [evidence, setEvidence] = useState<EvidenceReference | null>(null)
  const [theme, setTheme] = useState('light')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const initialScreen = new URLSearchParams(window.location.search).get('screen')
      if (initialScreen) setScreen(initialScreen)
      const savedTheme = localStorage.getItem('workweave-theme')
      if (savedTheme) setTheme(savedTheme)
      setSidebarCollapsed(localStorage.getItem('workweave-sidebar-collapsed') === 'true')
    }
  }, [])
  useEffect(() => {
    const viewport = matchMedia('(max-width: 650px)')
    const update = () => { setMobileNav(false) }
    update(); viewport.addEventListener('change', update)
    return () => viewport.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!mobileNav) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileNav(false) }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [mobileNav])
  const [profile, setProfile] = useState<Profile>(emptyProfile)
  const [profileFor, setProfileFor] = useState('')
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const currentCompany = useRef('')
  currentCompany.current = company?.id || ''
  const [candidateFacts, setCandidateFacts] = useState<{ text: string; evidence_ids: string[] }[]>([])
  const [candidateDraft, setCandidateDraft] = useState<Partial<Profile> | null>(null)
  const [memory, setMemory] = useState<{ episodes: MemoryEntry[]; procedures: { id: string; text: string; version: number; active: boolean }[] }>({ episodes: [], procedures: [] })
  const [providers, setProviders] = useState<ProviderSettings | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [mappings, setMappings] = useState<Mapping[]>([])
  const [draft, setDraft] = useState('')
  const [conversationId, setConversationId] = useState('')
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const conversationRequest = useRef(0)
  const conversationRef = useRef('')
  conversationRef.current = conversationId
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState('')
  const [phase, setPhase] = useState('')
  const [activeRunId, setActiveRunId] = useState('')

  const eventStream = useRef<EventSource | null>(null)
  const focusReturn = useRef<HTMLElement | null>(null)
  const inspectorReturn = useRef<HTMLElement | null>(null)
  const apiBase = company ? '/companies/' + company.id : ''
  const awaitingWork = Boolean(activeRunId) || runs.some(run => run.status === 'queued' || run.status === 'running')

  const perform = async (action: () => Promise<void>) => {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const preference = matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      document.documentElement.dataset.theme = theme === 'system' ? (preference.matches ? 'dark' : 'light') : theme
    }
    apply()
    localStorage.setItem('workweave-theme', theme)
    preference.addEventListener('change', apply)
    return () => preference.removeEventListener('change', apply)
  }, [theme])

  useEffect(() => {
    api<Account>('/auth/me')
      .then(setUser)
      .catch(e => { if (!(e instanceof ApiError && e.status === 401)) setSessionError(e.message || 'We could not check your session. Please retry.') })
      .finally(() => setChecking(false))
    return () => eventStream.current?.close()
  }, [])

  useEffect(() => {
    if (!accountKey) return
    let cancelled = false
      api<Company[]>('/companies')
        .then(items => {
          if (cancelled) return
          setCompanies(items)
          const saved = localStorage.getItem('workweave-workspace:' + accountKey)
          setCompany(items.find(item => item.id === saved) || items[0] || null)
          setWorkspacesFor(accountKey)
        })
        .catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [accountKey])

  const refresh = useCallback(async () => {
    if (!company) return
    const [r, t, s] = await Promise.all([
      api<RunStatus[]>(apiBase + '/runs'),
      api<Task[]>(apiBase + '/tasks'),
      api<Source[]>(apiBase + '/sources')
    ])
    if (currentCompany.current !== company.id) return
    setRuns(r)
    setTasks(t)
    setSources(s)
    setSelected(old => (old ? r.find(x => x.id === old.id) || old : null))
  }, [company, apiBase])

  useEffect(() => {
    if (!company) return
    setProfileFor('')
    setProfile(emptyProfile)
    setRuns([]); setTasks([]); setSources([]); setCandidateFacts([])
    let cancelled = false
    api<Profile>(apiBase + '/profile').then(data => { if (!cancelled) { setProfile(normalizeProfile(data)); setProfileFor(company.id) } }).catch(e => { if (!cancelled) setError(e.message) })
    api<Readiness>('/system/readiness').then(data => { if (!cancelled) setReadiness(data) }).catch(() => { if (!cancelled) setReadiness(null) })
    setSelected(null)
    setConversationId('')
    setMessages([])
    setConversations([]); setHistoryOpen(false); setHistoryError(''); setHistoryLoading(false); setChatLoading(false); setCandidateDraft(null); setMemory({ episodes: [], procedures: [] }); setProviders(null); setEvidence(null); setReadiness(null)
    conversationRequest.current++
    setError(''); setNotice('')
    setPreview(null)
    eventStream.current?.close()
    setStreaming('')
    setPhase('')
    setActiveRunId('')
    refresh().catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [company, refresh, apiBase])

  useEffect(() => {
    if (!company) return
    let refreshing = false
    const timer = setInterval(async () => {
      if (document.hidden || refreshing) return
      refreshing = true
      try { await refresh() } catch (e) { setError((e as Error).message) } finally { refreshing = false }
    }, awaitingWork ? 2500 : 60000)
    return () => clearInterval(timer)
  }, [company, refresh, awaitingWork])

  // A saved run is authoritative. A dropped event stream must never leave the
  // composer disabled or hide an answer already stored by the backend.
  useEffect(() => {
    if (!activeRunId || !conversationId || !company) return
    let cancelled = false
    let polling = false
    const timer = setInterval(async () => {
      if (polling) return
      polling = true
      try {
        const run = await api<RunStatus>(apiBase + '/runs/' + activeRunId)
        if (cancelled) return
        if (run.status === 'completed' || run.status === 'blocked') {
          const saved = await api<Message[]>(apiBase + '/conversations/' + conversationId + '/messages')
          if (cancelled) return
          eventStream.current?.close(); setMessages(saved); setPhase(''); setStreaming(''); setActiveRunId('')
          if (run.status === 'blocked') setError(run.error || 'We could not finish this answer. Try again.')
          await refresh()
        }
      } catch { /* The event stream can still deliver; keep the saved-run fallback alive. */ }
      finally { polling = false }
    }, 2500)
    return () => { cancelled = true; clearInterval(timer) }
  }, [activeRunId, conversationId, company, apiBase, refresh])

  useEffect(() => {
    if (!company) return
    let cancelled = false
    const path =
      screen === 'Company'
        ? '/profile'
        : screen === 'Memory'
        ? '/memory'
        : screen === 'Settings'
        ? '/providers'
        : screen === 'Assistant'
        ? '/conversations'
        : ''
    if (path)
      api<never>(apiBase + path)
        .then(data => {
          if (cancelled) return
          if (screen === 'Company') setProfile(normalizeProfile(data))
          if (screen === 'Memory') setMemory(data)
          if (screen === 'Settings') setProviders(data)
          if (screen === 'Assistant') setConversations(data)
        })
        .catch(e => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [screen, company, apiBase])

  useEffect(() => {
    if (evidence) {
      focusReturn.current = document.activeElement as HTMLElement
      document.querySelector<HTMLButtonElement>('.modal .close-button')?.focus()
    }
  }, [evidence])

  useEffect(() => {
    if (selected && screen === 'Work') {
      inspectorReturn.current = document.activeElement as HTMLElement
      document.querySelector<HTMLButtonElement>('.inspector .icon-button')?.focus()
    }
  }, [selected?.id, screen])

  const closeEvidence = () => {
    setEvidence(null)
    focusReturn.current?.focus()
  }

  const citation = (id: string) =>
    perform(async () => setEvidence(await api<EvidenceReference>(apiBase + '/evidence/' + id)))

  const loadPreview = (data: Preview) => {
    setPreview(data)
    setMappings(data.tables.map(t => t.suggested_mapping))
    setNotice('Check the document below, then choose Confirm & import.')
  }

  const switchScreen = (value: string) => {
    setScreen(value)
    setMobileNav(false)
    setError('')
    setNotice('')
    setHistoryOpen(false)
  }

  const toggleSidebar = () => {
    if (matchMedia('(max-width: 650px)').matches) setMobileNav(value => !value)
    else setSidebarCollapsed(value => { localStorage.setItem('workweave-sidebar-collapsed', String(!value)); return !value })
  }

  const changeWorkspace = (next: Company) => {
    localStorage.setItem('workweave-workspace:' + accountKey, next.id)
    setCompany(next)
  }

  const openHistory = async () => {
    switchScreen('Assistant'); setHistoryOpen(true); setHistoryLoading(true); setHistoryError('')
    const target = company?.id
    try { const items = await api<ConversationSummary[]>(apiBase + '/conversations'); if (currentCompany.current === target) setConversations(items) }
    catch (e) { if (currentCompany.current === target) setHistoryError((e as Error).message) }
    finally { if (currentCompany.current === target) setHistoryLoading(false) }
  }

  const openConversation = async (id: string) => {
    const request = ++conversationRequest.current
    const target = company?.id
    conversationRef.current = id
    eventStream.current?.close(); setPhase(''); setStreaming(''); setActiveRunId(''); setMessages([]); setDraft(''); setHistoryOpen(false); setChatLoading(true); setConversationId(id); setScreen('Assistant'); setError('')
    try {
      const saved = await api<Message[]>(apiBase + '/conversations/' + id + '/messages')
      if (request !== conversationRequest.current || currentCompany.current !== target) return
      setMessages(saved)
      const active = runs.find(run => run.conversation_id === id && (run.status === 'running' || run.status === 'queued'))
      if (active) streamRun(active)
    } catch (e) { if (request === conversationRequest.current && currentCompany.current === target) setError((e as Error).message) }
    finally { if (request === conversationRequest.current && currentCompany.current === target) setChatLoading(false) }
  }

  const newConversation = () => {
    conversationRequest.current++; conversationRef.current = ''; eventStream.current?.close(); setConversationId(''); setMessages([]); setDraft(''); setStreaming(''); setPhase(''); setActiveRunId(''); setHistoryOpen(false); setChatLoading(false); setError('')
  }

  const acceptUser = (account: Account) => {
    conversationRef.current = ''; setScreen('Work'); setCompanies([]); setCompany(null); setWorkspacesFor(''); setProfileFor(''); setError(''); setMemory({ episodes: [], procedures: [] }); setProviders(null); setEvidence(null); setReadiness(null); setUser(account)
  }

  const streamRun = (run: RunStatus) => {
    eventStream.current?.close()
    setStreaming('')
    setActiveRunId(run.id)
    setPhase('Reading your company documents…')
    const stream = new EventSource('/api/v1' + apiBase + '/runs/' + run.id + '/events')
    const isCurrent = () => currentCompany.current === company?.id && conversationRef.current === run.conversation_id
    eventStream.current = stream
    for (const name of [
      'run.started',
      'retrieval.selected',
      'agent.started',
      'agent.handoff',
      'tool.started',
      'provider.selected',
      'provider.wait',
      'provider.retry'
    ])
      stream.addEventListener(name, event => {
        if (!isCurrent()) return
        const data = JSON.parse((event as MessageEvent).data)
        setPhase(
          name === 'provider.retry'
            ? 'Trying another available AI service…'
            : data.name
            ? 'Checking ' + data.name.replaceAll('_', ' ') + '…'
            : data.provider
            ? (data.provider === 'ollama' ? 'Writing an answer on your computer. This can take longer.' : 'Writing your answer…')
            : 'Checking the evidence…'
        )
      })
    stream.addEventListener('message.delta', event => {
      if (isCurrent()) setStreaming(text => text + JSON.parse((event as MessageEvent).data).text)
    })
    const finish = async () => {
      stream.close()
      if (currentCompany.current !== company?.id || conversationRef.current !== run.conversation_id) return
      setStreaming('')
      setPhase('')
      setActiveRunId('')
      await refresh()
      const saved = await api<Message[]>(apiBase + '/conversations/' + run.conversation_id + '/messages')
      if (currentCompany.current === company?.id && conversationRef.current === run.conversation_id) setMessages(saved)
    }
    stream.addEventListener('run.completed', () => finish().catch(e => setError(e.message)))
    stream.addEventListener('run.failed', event => {
      if (!isCurrent()) return
      setError(JSON.parse((event as MessageEvent).data).error)
      finish().catch(e => setError(e.message))
    })
    stream.onerror = () => {
      stream.close()
      if (isCurrent()) setPhase('Checking for your saved answer…')
    }
  }

  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft.trim() || phase || chatLoading || !company) return
    await perform(async () => {
      const id = conversationId || (await api<{ id: string }>(apiBase + '/conversations', 'POST')).id
      conversationRef.current = id
      setConversationId(id)
      const query = draft
      setConversations(old => old.some(c => c.id === id) ? old.map(c => c.id === id ? { ...c, updated_at: Date.now() / 1000 } : c) : [{ id, title: query.slice(0, 80), created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }, ...old])
      setDraft('')
      const run = await api<RunStatus>(apiBase + '/conversations/' + id + '/messages', 'POST', { text: query })
      setMessages(await api<Message[]>(apiBase + '/conversations/' + id + '/messages'))
      setScreen('Assistant')
      streamRun(run)
    })
  }

  const handleDirectUpload = (file: File) => {
    switchScreen('Sources')
    perform(async () => {
      setNotice('Reading your document…')
      const form = new FormData()
      form.append('file', file)
      const res = await api<Preview>(apiBase + '/sources/upload', 'POST', form)
      loadPreview(res)
      setNotice('Your file is ready to review. Confirm it below to add it to company knowledge.')
    })
  }

  if (checking || sessionError) return <WorkspaceLoading text="Checking your session…" error={sessionError} />
  if (!user) return <AuthPortal onLogin={acceptUser} />
  if (workspacesFor !== accountKey) return <WorkspaceLoading text="Opening your workspace…" error={error} />

  if (!company)
    return (
      <main className="welcome">
        <div className="brand">
          <span className="brand-title">Workweave</span>
        </div>
        <span className="eyebrow">System setup · 00</span>
        <h1>Turn company knowledge<br />Into coordinated work.</h1>
        <p>Start with a company guide and spreadsheets.<br />Connect the evidence, responsibilities, and next steps.</p>
        {error && <div className="alert" role="alert">{error}</div>}
        <form
          onSubmit={e => {
            e.preventDefault()
            const data = new FormData(e.currentTarget)
            perform(async () => {
              const created = await api<Company>('/companies', 'POST', { name: data.get('name') })
              setCompanies([created])
              changeWorkspace(created)
            })
          }}
        >
          <label>
            <span className="field-label">Workspace identifier</span>
            <input name="name" placeholder="e.g. HARBOR SUPPLY" required minLength={2} />
          </label>
          <p className="muted small">This workspace will use Ollama Cloud for AI answers. Questions and relevant excerpts are sent to Ollama Cloud, or a configured Groq or Gemini fallback if needed. You can change this in Settings before asking.</p>
          <button disabled={busy} className="primary">Initialize workspace</button>
        </form>
        <div className="welcome-footer">
          <small>[prototype profile] â· [data enclave: local first with audit lock]</small>
        </div>
      </main>
    )

  if (profileFor !== company.id) return <WorkspaceLoading text="Opening your workspace…" error={error} />

  if (!profile.confirmed && profile.onboarding_step !== 'complete') return <Setup key={company.id} resumeCompany={company} initialProfile={profile} currentUser={user} onSuccess={() => { api<Profile>(apiBase + '/profile').then(data => setProfile(normalizeProfile(data))).catch(e => setError(e.message)) }} />

  const openTasks = tasks.filter(t => t.status !== 'done')
  const activeSources = sources.filter(s => s.active)

  return (
    <div className={"application " + (sidebarCollapsed ? "sidebar-collapsed" : "")}>
      <header className="topbar">
        <button className="icon-button mobile-navigation-toggle" onClick={toggleSidebar} aria-label={mobileNav ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileNav} aria-controls="workspace-navigation"><Menu size={19} /></button>
        <a href="#" className="brand" onClick={e => { e.preventDefault(); switchScreen('Work') }}>
          <WeaveMark /><span className="brand-title">Workweave.</span>
        </a>
        <WorkspaceSwitcher company={company} companies={companies} onChange={changeWorkspace} />
        <div className="topbar-cluster-badge"><span className={readiness ? 'status-dot' : 'status-dot unverified'} /><span>{readiness ? `FalkorDB · ${readiness.database.mode === 'local' ? 'Local' : 'Remote'}` : 'Connection not verified'}</span></div>
        <AccountMenu key={accountKey} user={user} company={company} busy={busy} onNavigate={switchScreen} onSignOut={() => perform(async () => {
          await api('/auth/logout', 'POST'); eventStream.current?.close(); conversationRequest.current++; setUser(null); setCompany(null); setCompanies([]); setProfileFor(''); setWorkspacesFor(''); setReadiness(null); setMessages([]); setConversations([]); setSelected(null); setEvidence(null); setHistoryOpen(false); setPhase(''); setActiveRunId(''); setRuns([]); setTasks([]); setSources([])
        })} />
      </header>

      {mobileNav && <button className="navigation-backdrop" aria-label="Close navigation overlay" onClick={() => setMobileNav(false)} />}
      <aside id="workspace-navigation" className={'rail ' + (mobileNav ? 'expanded' : '')}>
        <button className="sidebar-edge-toggle" onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!sidebarCollapsed} aria-controls="workspace-navigation">{sidebarCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}</button>
        <div className="rail-scroll">
          <div className="rail-label">Workspace Console</div>
          <nav aria-label="Main navigation">
            {navSections.map(section => (
              <div key={section.category} className="rail-group" style={{ marginBottom: '12px' }}>
                <div className="rail-category">{section.category}</div>
                {section.items.map(({ name, label, hint, icon: Icon }) => (
                  <button
                    key={name}
                    title={sidebarCollapsed ? label : undefined}
                    aria-label={label}
                    aria-current={screen === name ? 'page' : undefined}
                    className={screen === name ? 'active' : ''}
                    onClick={() => switchScreen(name)}
                  >
                    <Icon size={15} />
                    <span className="nav-description"><strong>{label}</strong><small>{hint}</small></span>
                    {name === 'Work' && openTasks.length > 0 && <span className="nav-count">{openTasks.length}</span>}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        </div>
        <div className="rail-bottom">
          <div className="local-status">
            <span className="status-dot" />
            Company knowledge
          </div>
          <p style={{ margin: '4px 0 8px', fontSize: '11px', color: 'var(--outline)' }}>
            Add documents. Confirm people.<br />Ask with the facts in view.
          </p>
          <div className="theme-buttons">
            {['light', 'dark', 'system'].map(t => (
              <button
                key={t}
                aria-label={t + ' theme'}
                aria-pressed={theme === t}
                className={theme === t ? 'chosen' : ''}
                onClick={() => setTheme(t)}
              >
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </aside>

      <main className={'main-content ' + (selected && screen === 'Work' ? 'inspecting' : '')}>
        {error && (
          <div className="alert" role="alert">
            <span>{error}</span>
            <button onClick={() => setError('')} aria-label="Dismiss error">✕</button>
          </div>
        )}
        {notice && <div className="notice" role="status">{notice}</div>}

        {screen === 'Work' && (
          <>
            <Heading
              eyebrow={profile.industry || 'Your company workspace'}
              title="What would you like to do?"
              text={workspacePriorities.find(item => item.id === profile.workflow_priority)?.description || 'Keep your company information in one place. Start with a document, then ask a question.'}
              action={
                <button className="primary" onClick={() => switchScreen('Sources')}><Upload size={16} />Upload a document</button>
              }
            />

            <div className="ww-start-grid">
              <button onClick={() => switchScreen('Sources')}><span className="step-number">1</span><FileText size={22} /><strong>Add your documents</strong><p>Company profile, procedures, and work records.</p><span className="card-link">{activeSources.length ? `${activeSources.length} documents added` : 'Choose your first file'} <ArrowRight size={15} /></span></button>
              <button onClick={() => switchScreen('People')}><span className="step-number">2</span><Users size={22} /><strong>Check who does what</strong><p>Review people and responsibilities found in your files.</p><span className="card-link">Review people & roles <ArrowRight size={15} /></span></button>
              <button onClick={() => switchScreen('Assistant')}><span className="step-number">3</span><MessageSquare size={22} /><strong>Ask your company</strong><p>Get a clear answer and open the source behind it.</p><span className="card-link">Ask a question <ArrowRight size={15} /></span></button>
            </div>
            <div className="ww-help-note"><ShieldCheck size={20} /><div><strong>{/logistic|delivery|distribution/i.test(profile.industry || profile.description) ? 'A home for your logistics knowledge' : 'Built around your company information'}</strong><p>{/logistic|delivery|distribution/i.test(profile.industry || profile.description) ? 'Start with your company profile and delivery procedure. Add order and stock spreadsheets for supplier-delay checks. Rider assignments must be stated in a document or confirmed in People & roles.' : 'Your company guide explains the business. Your documents supply the facts. You confirm people and responsibilities before relying on them.'}</p></div></div>

            {activeSources.length === 0 && <section className="ww-first-source"><div><span className="eyebrow">Your first connection</span><h2>Start with what your company knows.</h2><p>Add a guide, a procedure, or a spreadsheet. Review the parsed information before it becomes company knowledge.</p></div><label className="button primary"><Upload size={16} /> Add your first source<input className="file-input" type="file" accept=".xlsx,.csv,.pdf,.docx,.txt,.md" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (file) handleDirectUpload(file); e.target.value = '' }} /></label></section>}

            <div className="stats">
              <div className="stat-card">
                <span className="stat-idx">Metric · 01</span>
                <span className="stat-label">Open tasks</span>
                <strong>{openTasks.length}</strong>
                <small>Across your workspace</small>
              </div>
              <div className="stat-card">
                <span className="stat-idx">Metric · 02</span>
                <span className="stat-label">Affected commitments</span>
                <strong>
                  {new Set(runs.flatMap(r => r.findings.filter(f => f.severity === 'affected').map(f => f.entity_id))).size}
                </strong>
                <small>Distinct commitments in investigations</small>
              </div>
              <div className="stat-card">
                <span className="stat-idx">Metric · 03</span>
                <span className="stat-label">Documents added</span>
                <strong>{activeSources.length}</strong>
                <small>
                  {activeSources.some(s => s.semantic_status === 'degraded')
                    ? 'Some search features need setup'
                    : 'Current accepted versions'}
                </small>
              </div>
            </div>

            <RecentActivity key={'recent-' + company.id} runs={runs} onHistory={() => { void openHistory() }} onOpen={run => {
              if (run.entity_id) perform(async () => setSelected(await api<RunStatus>(apiBase + '/runs/' + run.id)))
              else void openConversation(run.conversation_id)
            }} />

            {!runs.some(run => run.demo) && <DemoWorkspace key={'demo-' + company.id} onReady={async next => {
              const items = await api<Company[]>('/companies')
              setCompanies(items); switchScreen('Work'); changeWorkspace(next)
            }} />}

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Internal review tasks</h2>
                  <p>Created from findings. Progress is retained in memory.</p>
                </div>
                <button className="text-button" onClick={() => switchScreen('Memory')}><BookOpen size={15} />View remembered outcomes</button>
              </div>
              {tasks.length ? (
                tasks.map((t, i) => (
                  <div className="task-row" key={t.id}>
                    <span className="investigation-idx">[{String(i + 1).padStart(2, '0')}]</span>
                    <div>
                      <strong>{t.title}</strong>
                      <span>Owner: {t.owner}</span>
                    </div>
                    <select
                      aria-label={'Status of ' + t.title}
                      value={t.status}
                      onChange={e =>
                        perform(async () => {
                          await api(apiBase + '/tasks/' + t.id, 'PATCH', { status: e.target.value })
                          await refresh()
                        })
                      }
                    >
                      {['open', 'in_progress', 'done'].map(s => (
                        <option key={s} value={s}>
                          {s.replace('_', ' ')}
                        </option>
                      ))}
                    </select>
                    <button
                      className="bracket-btn text-button"
                      onClick={() => perform(async () => setSelected(await api<RunStatus>(apiBase + '/runs/' + t.run_id)))}
                    >View evidence</button>
                  </div>
                ))
              ) : (
                <p className="empty-inline">No review tasks yet. Investigations create tasks when a commitment needs attention.</p>
              )}
            </section>

            <div className="assistant-strip">
              <div>
                <strong>Your company context, ready to query.</strong>
                <p>Ask with current evidence and previous outcomes.</p>
              </div>
              <button className="primary" onClick={() => switchScreen('Assistant')}>Ask Workweave</button>
            </div>
          </>
        )}

        {screen === 'Sources' && (
          <>
            <Heading
              eyebrow="Company knowledge"
              title="Documents"
              text="Upload a file, check what we read, and confirm it. New versions of the same file replace older information."
            />
            <section className="upload-area">
              <Upload size={32} />
              <div>
                <h2>Documents & spreadsheets</h2>
                <p>Accepted: excel (.xlsx), csv, text, markdown, pdf, word â· up to 10 mb</p>
              </div>
              <label className="button primary">
                {busy ? 'Reading your file…' : 'Choose a file'}
                <input
                  className="file-input"
                  type="file"
                  accept=".xlsx,.csv,.txt,.md,.pdf,.docx"
                  disabled={busy}
                  onChange={e => {
                    const file = e.target.files?.[0]
                    if (file)
                      perform(async () => {
                        const form = new FormData()
                        form.append('file', file)
                        loadPreview(await api<Preview>(apiBase + '/sources/upload', 'POST', form))
                      })
                    e.target.value = ''
                  }}
                />
              </label>
            </section>

            {preview && (
              <section className="panel import-preview">
                <div className="panel-heading">
                  <div>
                    <h2>Review import: {preview.filename}</h2>
                    <p>VERSION {preview.version} · INACTIVE UNTIL CONFIRMED</p>
                  </div>
                  <button className="icon-button" aria-label="Close preview" onClick={() => setPreview(null)}>
                    <X size={16} />
                  </button>
                </div>
                {preview.warnings.map(w => (
                  <p className="notice" key={w}>
                    [WARNING] {w}
                  </p>
                ))}
                {preview.sections.map(s => (
                  <blockquote key={s.location}>
                    <small>Section · {s.location}</small>
                    {s.text}
                  </blockquote>
                ))}
                {preview.tables.map((table, index) => (
                  <div className="mapping" key={table.name}>
                    <h3>
                      {table.name} <small>[{table.row_count} ROWS]</small>
                    </h3>
                    <div className="mapping-controls">
                      <label>
                        <span className="field-label">Record type</span>
                        <select
                          value={mappings[index].entity_type}
                          onChange={e =>
                            setMappings(m =>
                              m.map((v, i) => (i === index ? { ...v, entity_type: e.target.value } : v))
                            )
                          }
                        >
                          {['Supplier', 'Product', 'PurchaseOrder', 'SalesOrder', 'Team', 'BusinessRecord'].map(v => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span className="field-label">Stable identifier</span>
                        <select
                          value={mappings[index].key_column}
                          onChange={e =>
                            setMappings(m =>
                              m.map((v, i) => (i === index ? { ...v, key_column: e.target.value } : v))
                            )
                          }
                        >
                          {table.headers.map(v => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <details>
                      <summary>Configure column meanings</summary>
                      <div className="field-grid">
                        {[
                          'name',
                          'supplier_id',
                          'product_id',
                          'purchase_order_id',
                          'delivery_date',
                          'required_date',
                          'quantity',
                          'stock',
                          'owner',
                          'status'
                        ].map(field => (
                          <label key={field}>
                            <span className="field-label">[{field.replaceAll('_', ' ')}]</span>
                            <select
                              value={mappings[index].fields[field] || ''}
                              onChange={e =>
                                setMappings(m =>
                                  m.map((v, i) => {
                                    if (i !== index) return v
                                    const fields = { ...v.fields }
                                    if (e.target.value) fields[field] = e.target.value
                                    else delete fields[field]
                                    return { ...v, fields }
                                  })
                                )
                              }
                            >
                              <option value="">Not mapped</option>
                              {table.headers.map(v => (
                                <option key={v}>{v}</option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>
                    </details>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            {table.headers.map(v => (
                              <th key={v}>{v}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {table.rows.map((row, i) => (
                            <tr key={i}>
                              {row.map((cell, j) => (
                                <td key={j}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
                <button
                  className="primary"
                  style={{ margin: '20px 24px' }}
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      setNotice('Adding your document to company knowledge…')
                      await api(apiBase + '/imports/' + preview.id + '/confirm', 'POST', { mappings })
                      setPreview(null)
                      await refresh()
                      setNotice('Document added. Open People & roles to review any responsibilities found.')
                    })
                  }
                >
                  <Check size={16} />
                  {busy ? 'Adding your document…' : 'Confirm & import'}
                </button>
              </section>
            )}

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Your documents</h2>
                  <p>Upload the same filename again when the information changes.</p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    perform(async () => {
                      setNotice('Preparing documents for search…')
                      const result = await api<{ indexed_excerpts: number }>(apiBase + '/sources/reindex', 'POST')
                      await refresh()
                      setNotice(result.indexed_excerpts + ' document sections prepared for search.')
                    })
                  }
                >Refresh document search</button>
              </div>
              {sources.length ? (
                sources.map((s, idx) => (
                  <div className="source-row" key={s.id}>
                    <span className="investigation-idx">[{String(idx + 1).padStart(2, '0')}]</span>
                    <FileText size={20} />
                    <div>
                      <strong>{s.name}</strong>
                      <span>
                        {s.record_count} RECORDS · {s.chunk_count} EXCERPTS · REV {s.version}
                      </span>
                    </div>
                    <Badge
                      value={!s.active ? 'revoked' : s.semantic_status === 'ready' ? 'ready' : 'semantic degraded'}
                    />
                    {s.drive_file_id && s.active && (
                      <button
                        className="secondary"
                        onClick={() =>
                          perform(async () => {
                            const result = await api<{ preview?: Preview }>(apiBase + '/sources/' + s.id + '/sync', 'POST')
                            if (result.preview) loadPreview(result.preview)
                            await refresh()
                          })
                        }
                      >Sync</button>
                    )}
                    {s.active && (
                      <button
                        className="bracket-btn text-button"
                        onClick={() =>
                          perform(async () => {
                            await api(apiBase + '/sources/' + s.id, 'DELETE')
                            await refresh()
                          })
                        }
                      >✕ revoke</button>
                    )}
                  </div>
                ))
              ) : (
                <p className="empty-inline">No sources attached. start by uploading a company guide.</p>
              )}
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Selected google drive files</h2>
                  <p>Google Docs and Sheets synchronize under the external product profile.</p>
                </div>
                <Badge value="event profile" />
              </div>
              <p className="empty-inline">
                PRIVATE DRIVE IS DISABLED BY DEFAULT FOR THE PROTOTYPE DEMONSTRATION. USE SYNTHETIC OR LOCAL UPLOADS.
              </p>
              <div className="panel-actions" style={{ padding: '0 24px 24px', display: 'flex', gap: '12px' }}>
                <button
                  className="secondary"
                  onClick={() =>
                    perform(async () => {
                      const data = await api<{ url: string }>(apiBase + '/drive/connect')
                      location.assign(data.url)
                    })
                  }
                >Connect google drive</button>
                <button
                  className="secondary"
                  onClick={() =>
                    perform(async () => {
                      const config = await api<PickerConfig>(apiBase + '/drive/picker')
                      const ids = await chooseGoogleFiles(config)
                      const data = await api<Preview[]>(apiBase + '/drive/select', 'POST', { file_ids: ids })
                      if (data[0]) loadPreview(data[0])
                    })
                  }
                >Choose connected file</button>
              </div>
            </section>
          </>
        )}

        {screen === 'People' && <People key={company.id} base={apiBase} onDocument={() => switchScreen('Sources')} onCitation={citation} />}

        {screen === 'Company' && (
          <>
            <Heading
              eyebrow="Confirmed Company Knowledge"
              title="How your company works"
              text="Tell Workweave what your company does. Documents provide facts; you confirm the company details."
              action={<button className="secondary" onClick={() => switchScreen('Memory')}><BookOpen size={16} />Past decisions</button>}
            />
            <form
              className="panel profile-form"
              onSubmit={e => {
                e.preventDefault()
                perform(async () => {
                  await api(apiBase + '/profile', 'PUT', { ...profile, confirmed: true })
                  setProfile(p => ({ ...p, confirmed: true }))
                  setNotice('Company details saved.')
                })
              }}
            >
              <Badge value={profile.confirmed ? 'confirmed' : 'needs review'} />
              <label>Type of work<input list="company-work-areas" maxLength={100} value={profile.industry || ''} onChange={e => setProfile({ ...profile, industry: e.target.value })} placeholder="Choose or enter your type of work" /><datalist id="company-work-areas">{workAreas.map(value => <option key={value} value={value} />)}</datalist></label>
              <label>Starting focus<select value={profile.workflow_priority || ''} onChange={e => setProfile({ ...profile, workflow_priority: e.target.value })}><option value="">Choose a focus</option>{workspacePriorities.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() =>
                  perform(async () => {
                    const result = await api<{ facts: { text: string; evidence_ids: string[] }[]; draft: Partial<Profile> }>(
                      apiBase + '/profile/preview',
                      'POST'
                    )
                    setCandidateFacts(result.facts)
                    setCandidateDraft(result.draft)
                  })
                }
              >
                <FileText size={16} />Read company details from documents</button>

              {candidateFacts.length > 0 && (
                <section>
                  <h3>Suggested facts · review before accepting</h3>
                  {candidateFacts.map((fact, i) => (
                    <article className="memory-entry" key={i}>
                      <p>{fact.text}</p>
                      <Citations ids={fact.evidence_ids} onClick={citation} />
                    </article>
                  ))}
                  <button
                    type="button"
                    className="secondary"
                    style={{ marginTop: '14px' }}
                    onClick={() => {
                      setProfile({
                        ...profile,
                        description: candidateDraft?.description || profile.description,
                        responsibilities: candidateDraft?.responsibilities || profile.responsibilities,
                        evidence_ids: [...new Set([...(profile.evidence_ids || []), ...candidateFacts.flatMap(f => f.evidence_ids)])],
                        confirmed: false
                      })
                      setCandidateFacts([])
                    }}
                  >Use reviewed facts in draft</button>
                </section>
              )}

              {[
                { key: 'description', label: 'What does your company do?' },
                { key: 'responsibilities', label: 'Who owns which responsibilities?' },
                { key: 'procedure', label: 'Approved procedure' }
              ].map(f => (
                <label key={f.key}>
                  <span className="field-label">{f.label}</span>
                  <textarea
                    rows={5}
                    value={(profile[f.key as keyof Profile] as string) || ''}
                    onChange={e => setProfile({ ...profile, [f.key]: e.target.value, confirmed: false })}
                  />
                </label>
              ))}
              <p className="muted" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                Company guides provide business context. You approve procedures and keep control over actions.
              </p>
              <button className="primary" disabled={busy}>
                <ShieldCheck size={16} />Confirm company understanding</button>
            </form>
          </>
        )}

        {screen === 'Memory' && (
          <>
            <Heading
              eyebrow="Organizational Memory"
              title="Keep the context that matters."
              text="Revisit investigations, their recorded outcomes, and approved procedure versions."
            />
            <div className="memory-layout">
              <section className="panel">
                <div className="panel-heading">
                  <h2>Investigation episodes</h2>
                  <Badge value={memory.episodes.length + ' RETAINED'} />
                </div>
                {memory.episodes.map(e => (
                  <article className="memory-entry" key={e.id}>
                    <span className="eyebrow">[{stamp(e.created_at)}]</span>
                    <p className="preserve-lines">{e.summary}</p>
                    <div className="outcome">
                      <Check size={14} />
                      <span>{e.outcome}</span>
                    </div>
                    <Citations ids={e.evidence_ids} onClick={citation} />
                  </article>
                ))}
                {!memory.episodes.length && (
                  <p className="empty-inline">
                    Completed investigations and recorded outcomes appear here. Past outcomes remain separate from approved company facts.
                  </p>
                )}
              </section>

              <section className="panel">
                <div className="panel-heading">
                  <h2>Procedure history</h2>
                </div>
                {memory.procedures.map(p => (
                  <article className="memory-entry" key={p.id}>
                    <Badge value={p.active ? 'approved current' : 'superseded'} />
                    <h3 style={{ marginTop: '12px' }}>VERSION {p.version}</h3>
                    <p>{p.text}</p>
                  </article>
                ))}
                {!memory.procedures.length && (
                  <p className="empty-inline">No approved procedures recorded. approve a procedure on the company screen.</p>
                )}
              </section>
            </div>
          </>
        )}

        {screen === 'Settings' && (
          <>
            <Heading
              eyebrow="Workspace Settings"
              title="Make the workspace yours."
              text="Choose the appearance and how your company information is processed."
            />
            <section className="panel settings-section">
              <h2>Appearance</h2>
              <div className="segmented">
                {['system', 'light', 'dark'].map(t => (
                  <button key={t} className={theme === t ? 'active' : ''} onClick={() => setTheme(t)}>
                    {t[0].toUpperCase() + t.slice(1)}
                  </button>
                ))}
              </div>
            </section>
            <section className="panel settings-section">
              <h2>Company knowledge connection</h2>
              <p>{readiness ? `FalkorDB is connected through ${readiness.database.mode === 'local' ? 'your local runtime' : 'a remote instance'}. ${readiness.database.tls ? 'TLS protects the database connection.' : 'The database connection does not use TLS.'}` : 'The database connection has not been verified.'}</p>
              <button className="secondary" disabled={busy} onClick={() => perform(async () => { setReadiness(null); setReadiness(await api<Readiness>('/system/readiness')) })}>Check connection</button>
            </section>

            {providers && <AISettings
              key={company.id}
              settings={providers}
              onChange={setProviders}
              onNotice={setNotice}
              perform={perform}
              base={apiBase}
              busy={busy}
              platformAdmin={Boolean(readiness?.platform_admin)}
            />}

            <section className="panel settings-section">
              <h2>Data retention & access audit</h2>
              <p>
                Revoked sources and superseded versions remain stored for cryptographic audit and are excluded from active
                vector retrieval. Conversations are private to the author.
              </p>
              <p>
                Internal tasks and automated investigations are synchronized across workspace members.
              </p>
            </section>
          </>
        )}

        {screen === 'Assistant' && (
          <>
            <Heading
              eyebrow="Ask your company"
              title="What do you need to know?"
              text="Answers come from your uploaded documents. If a detail is missing, we’ll tell you."
            />
            <div className="conversation-toolbar">
              <div className="conversation-heading"><MessageSquare size={17} /><span>{conversations.find(item => item.id === conversationId)?.title || (conversationId ? 'Saved conversation' : 'New conversation')}</span></div>
              <div className="conversation-actions"><button className="secondary" onClick={() => { void openHistory() }} aria-expanded={historyOpen}><History size={16} />History</button><button className="primary" onClick={newConversation}><Plus size={16} />New conversation</button></div>
            </div>

            <section className="panel chat-panel" aria-busy={chatLoading}>
              {chatLoading && <div className="chat-loading" role="status"><span className="loading-spinner" />Opening your conversation…</div>}
              {!chatLoading && !messages.length && (
                <Empty
                  title="What would you like to understand?"
                  text="Try one of the questions below, or type your own. You can open the source behind an answer."
                />
              )}
              {!chatLoading && !messages.length && <div className="question-starters">{['What does our company do?', 'Who is responsible for operations?', 'What information is missing?'].map(question => <button className="secondary" key={question} onClick={() => { setDraft(question); document.querySelector<HTMLTextAreaElement>('.composer textarea')?.focus() }}>{question}<ArrowRight size={14} /></button>)}</div>}
              {messages.map(m => (
                <article className={'message ' + m.role} key={m.id}>
                  <span className="eyebrow">{m.role === 'user' ? 'You' : 'Workweave'}</span>
                  {m.claims?.length ? (
                    m.claims.map((claim, i) => (
                      <div key={i} style={{ marginBottom: '12px' }}>
                        <p className="preserve-lines">{claim.text}</p>
                        <Citations ids={claim.evidence_ids} onClick={citation} />
                      </div>
                    ))
                  ) : (
                    <>
                      <p className="preserve-lines">{m.content}</p>
                      {m.evidence_ids && <Citations ids={m.evidence_ids} onClick={citation} />}
                    </>
                  )}
                </article>
              ))}
              {phase && (
                <article className="message assistant" role="status">
                  <span className="eyebrow">Working on your answer</span>
                  <p>{phase}</p>
                  {streaming && <p className="preserve-lines" style={{ marginTop: '8px' }}>{streaming}</p>}
                </article>
              )}
            </section>

            <form className="composer" onSubmit={send}>
              <textarea
                aria-label="Message Workweave"
                rows={2}
                placeholder="Ask about your company…"
                value={draft}
                onChange={e => setDraft(e.target.value)}
              />
              <button className="primary" disabled={busy || chatLoading || !!phase || !draft.trim()}>
                <ArrowRight size={18} />
                <span className="sr-only">Send message</span>
              </button>
            </form>
          </>
        )}

        <footer>Workweave · Company knowledge, connected · Powered by FalkorDB</footer>
      </main>

      {historyOpen && <ConversationHistory conversations={conversations} active={conversationId} onSelect={id => { void openConversation(id) }} onClose={() => setHistoryOpen(false)} loading={historyLoading} error={historyError} />}

      {selected && screen === 'Work' && (
        <Inspector
          run={selected}
          tasks={tasks.filter(t => t.run_id === selected.id)}
          busy={busy}
          onClose={() => {
            setSelected(null)
            inspectorReturn.current?.focus()
          }}
          onEvidence={citation}
          onResume={() =>
            perform(async () => {
              await api(apiBase + '/runs/' + selected.id + '/resume', 'POST')
              await refresh()
            })
          }
          onAsk={() => {
            setDraft('Explain the evidence for ' + selected.query)
            switchScreen('Assistant')
          }}
        />
      )}

      {evidence && (
        <div className="modal-backdrop" onClick={closeEvidence}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="evidence-heading"
            onClick={e => e.stopPropagation()}
            onKeyDown={e => {
              if (e.key === 'Escape') closeEvidence()
              if (e.key === 'Tab') {
                const targets = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('button,a,input'))
                if (e.shiftKey && document.activeElement === targets[0]) {
                  e.preventDefault()
                  targets.at(-1)?.focus()
                } else if (!e.shiftKey && document.activeElement === targets.at(-1)) {
                  e.preventDefault()
                  targets[0]?.focus()
                }
              }
            }}
          >
            <button className="close-button icon-button" aria-label="Close evidence" onClick={closeEvidence}>
              <X size={20} />
            </button>
            <span className="eyebrow">Source evidence · audit entry</span>
            <h2 id="evidence-heading">{evidence.title}</h2>
            <p className="small">{evidence.location}</p>
            <Badge value={evidence.current ? 'current version' : 'historical or revoked'} />
            <p className="version" style={{ marginTop: '12px' }}>
              REVISION {evidence.version}
            </p>
            <blockquote className="preserve-lines">{evidence.excerpt}</blockquote>
          </section>
        </div>
      )}
    </div>
  )
}

function Heading({
  eyebrow,
  title,
  text,
  action
}: {
  eyebrow: string
  title: string
  text: string
  action?: React.ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {action}
    </div>
  )
}

function Empty({ title, text, action }: { title: string; text: string; action?: React.ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Workflow size={28} />
      </span>
      <h2>{title}</h2>
      <p>{text}</p>
      <div className="empty-actions">{action}</div>
    </div>
  )
}

function Citations({ ids, onClick }: { ids: string[]; onClick: (id: string) => void }) {
  return (
    <div className="citations">
      {ids.slice(0, 12).map((id, i) => (
        <button key={id} onClick={() => onClick(id)} className="bracket-btn citation-btn">
          Source {i + 1}
        </button>
      ))}
    </div>
  )
}

function Inspector({
  run,
  tasks,
  busy,
  onClose,
  onEvidence,
  onResume,
  onAsk
}: {
  run: RunStatus
  tasks: Task[]
  busy: boolean
  onClose: () => void
  onEvidence: (id: string) => void
  onResume: () => void
  onAsk: () => void
}) {
  const [findingId, setFindingId] = useState('')
  const finding = run.findings.find(f => f.id === findingId) || run.findings[0]
  const paths = run.paths.filter(p => !finding || p.nodes[0]?.id === finding.entity_id)

  return (
    <aside className="inspector" aria-label="Investigation inspector" onKeyDown={e => { if (e.key === 'Escape') onClose() }}>
      <div className="inspector-heading">
        <span className="eyebrow">Investigation · audit</span>
        <button className="icon-button" aria-label="Close investigation" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <h2>{run.entity_id ? 'Supplier delivery changed' : run.query}</h2>
      <Badge value={run.status} />
      {run.demo && <p className="muted small" style={{ marginTop: '10px' }}>Demo workflow · deterministic graph</p>}

      <section>
        <h3>What changed</h3>
        <p style={{ color: 'var(--primary)', fontWeight: 600 }}>{run.query}</p>
        {run.answer && <p className="small preserve-lines">{run.answer}</p>}
        {run.error && <div className="alert">{run.error}</div>}
        {run.status === 'blocked' && (
          <button className="primary" disabled={busy} onClick={onResume}>Resume investigation</button>
        )}
      </section>

      <section>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3>Affected commitments</h3>
          <span className="pill">[{run.findings.length}]</span>
        </div>
        {run.findings.map((f, i) => (
          <button
            className={'finding ' + (finding?.id === f.id ? 'chosen' : '')}
            key={f.id}
            onClick={() => setFindingId(f.id)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <span className="stat-idx">[{String(i + 1).padStart(2, '0')} //]</span>
              <Badge value={f.severity} />
            </div>
            <strong>{f.title}</strong>
            <span>Owner: {f.owner}</span>
          </button>
        ))}
        {!run.findings.length && <p className="muted small">No affected commitments recorded.</p>}
      </section>

      {run.impact_review && <section className="impact-review">
        <h3>Why other orders do not need review</h3>
        <p className="small muted">{run.impact_review.candidate_count} orders checked along recorded dependency paths.</p>
        {run.impact_review.excluded.map(item => <article className="excluded-order" key={item.entity_id}><strong>{item.title}</strong><p className="small">{item.reason}</p><Citations ids={item.evidence_ids} onClick={onEvidence} /></article>)}
        {!run.impact_review.excluded.length && <p className="small muted">{run.impact_review.candidate_count ? 'Every assessed order needs attention.' : 'No current dependency paths were found. This does not establish that other orders are unaffected.'}</p>}
        <p className="small muted">{run.impact_review.assumption}</p>
      </section>}

      {finding && (
        <section>
          <h3>Why this needs attention</h3>
          <p className="small">{finding.explanation}</p>
          <Citations ids={finding.evidence_ids} onClick={onEvidence} />
        </section>
      )}

      <section>
        <h3>The connected evidence</h3>
        {paths.map((p, i) => (
          <DependencyPath key={i} path={p} />
        ))}
        {!paths.length && <p className="muted small">Relationships appear following graph investigation.</p>}
      </section>

      <section>
        <h3>Internal review tasks</h3>
        {tasks.map(t => (
          <div className="inspector-task" key={t.id}>
            <Check size={14} />
            <div>
              <strong>{t.title}</strong>
              <span>
                {t.owner} · [{t.status.replaceAll('_', ' ')}]
              </span>
            </div>
          </div>
        ))}
      </section>

      <section>
        <h3>Execution audit trail</h3>
        {run.handoff && <p className="small"><strong>{run.handoff.from} → {run.handoff.to}</strong><br />{run.handoff.finding_ids.length} findings handed over · {stamp(run.handoff.at)}</p>}
        <div className="timeline">
          {(run.events || [])
            .filter(e => !e.type.startsWith('message.'))
            .slice(-8)
            .map((e, i) => (
              <div key={i}>
                <span className="status-dot" />
                <span>[{e.type.replaceAll('.', ' · ').replaceAll('_', ' ')}]</span>
              </div>
            ))}
        </div>
      </section>

      <button className="primary inspector-ask" onClick={onAsk}>
        <MessageSquare size={16} />Ask about this investigation</button>
    </aside>
  )
}

function DependencyPath({ path }: { path: GraphPath }) {
  return (
    <ol className="dependency-path">
      {path.nodes.map((n, i) => (
        <li key={n.id}>
          <div className="path-node">
            <span className="path-type">[{n.type.replace(/([A-Z])/g, ' $1').trim()}]</span>
            <strong>{n.label}</strong>
          </div>
          {i < path.nodes.length - 1 && (
            <div className="path-edge">
              <span className="path-rule" />
              <span>↓ DEPENDS ON</span>
              <span className="path-rule" />
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

function AuthPortal({ onLogin }: { onLogin: (u: Account) => void }) {
  const [mode, setMode] = useState<'landing' | 'signin' | 'signup'>('landing')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [googleEnabled, setGoogleEnabled] = useState(false)
  useEffect(() => { api<{google: boolean}>('/auth/options').then(data => setGoogleEnabled(data.google)).catch(() => {}) }, [])
  if (mode === 'landing') return <Welcome onGetStarted={() => setMode('signup')} onSignIn={() => setMode('signin')} />
  if (mode === 'signup') return <Setup onSuccess={onLogin} onSwitchToSignIn={() => setMode('signin')} onCancel={() => setMode('landing')} />
  return <main className="ww-signin"><aside><span className="ww-wordmark"><WeaveMark />Workweave.</span><div><span className="ww-kicker">Pick up where the work left off</span><h1>Your company.<br /><em>In context.</em></h1><p>Your sources, investigations, and remembered outcomes are ready when you are.</p></div><small>Connected knowledge. Accountable work.</small></aside><section><button className="text-button" onClick={() => setMode('landing')}>← Back to Workweave</button><form onSubmit={async e => { e.preventDefault(); setBusy(true); setError(''); const data = new FormData(e.currentTarget); try { onLogin(await api('/auth/login', 'POST', {username: data.get('username'), password: data.get('password')})) } catch(err) { setError((err as Error).message) } finally { setBusy(false) } }}><div className="ww-form-intro"><h2>Welcome back.</h2><p>Sign in to your company workspace.</p></div>{error && <div className="alert" role="alert">{error}</div>}<label>Email or username<input name="username" autoComplete="username" required autoFocus placeholder="you@company.com" /></label><label>Password<input name="password" type="password" autoComplete="current-password" required placeholder="Your password" /></label><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Open your workspace'}<ArrowRight size={16} /></button>{googleEnabled && <button type="button" disabled={busy} onClick={async () => { setBusy(true); try { const data = await api<{url:string}>('/auth/google/url'); window.location.href = data.url } catch(err) { setError((err as Error).message); setBusy(false) } }}>Continue with Google</button>}{googleEnabled && <p className="muted small">New Google workspaces use Ollama Cloud for AI answers. Questions and relevant excerpts are sent to Ollama Cloud, or a configured Groq or Gemini fallback if needed. Change this in Settings before asking.</p>}<p className="ww-signin-create">New here? <button type="button" className="text-button" onClick={() => setMode('signup')}>Create a workspace →</button></p></form></section></main>
}

type PickerConfig = { access_token: string; developer_key: string; app_id: string }

async function chooseGoogleFiles(config: PickerConfig): Promise<string[]> {
  type Builder = {
    addView: (view: string) => void
    setOAuthToken: (token: string) => void
    setDeveloperKey: (key: string) => void
    setAppId: (id: string) => void
    setCallback: (fn: (data: { action: string; docs?: { id: string }[] }) => void) => void
    build: () => { setVisible: (value: boolean) => void }
  }
  const win = window as unknown as {
    gapi: { load: (name: string, options: { callback: () => void }) => void }
    google: { picker: { PickerBuilder: new () => Builder; ViewId: { DOCS: string } } }
  }
  if (!win.gapi)
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://apis.google.com/js/api.js'
      script.onload = () => resolve()
      script.onerror = () => reject(new Error('Google Picker could not load'))
      document.head.append(script)
    })
  await new Promise<void>(resolve => win.gapi.load('picker', { callback: resolve }))
  return new Promise((resolve, reject) => {
    const builder = new win.google.picker.PickerBuilder()
    builder.addView(win.google.picker.ViewId.DOCS)
    builder.setOAuthToken(config.access_token)
    builder.setDeveloperKey(config.developer_key)
    builder.setAppId(config.app_id)
    builder.setCallback(data => {
      if (data.action === 'picked') resolve((data.docs || []).map(d => d.id))
      if (data.action === 'cancel') reject(new Error('File selection cancelled'))
    })
    builder.build().setVisible(true)
  })
}
