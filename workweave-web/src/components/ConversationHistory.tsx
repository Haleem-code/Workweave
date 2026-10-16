'use client'

import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, History, MessageSquare, Search, X } from 'lucide-react'
import { RunStatus } from '../api'

export type ConversationSummary = { id: string; title: string; created_at?: number; updated_at?: number }
const date = (seconds: number) => new Date(seconds * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' })

export function RecentActivity({ runs, onOpen, onHistory }: { runs: RunStatus[]; onOpen: (run: RunStatus) => void; onHistory: () => void }) {
  const [page, setPage] = useState(0)
  const [query, setQuery] = useState('')
  const unique = new Map<string, RunStatus>()
  for (const run of [...runs].sort((a, b) => b.created_at - a.created_at)) {
    const key = run.conversation_id || run.id
    if (!unique.has(key)) unique.set(key, run)
  }
  const items = [...unique.values()].filter(run => run.query.toLowerCase().includes(query.toLowerCase()))
  const pages = Math.max(1, Math.ceil(items.length / 3))
  const current = Math.min(page, pages - 1)
  return <section className="panel recent-activity"><div className="recent-heading"><div><h2>Recent conversations</h2><p>Pick up where you left off.</p></div><button className="text-button" onClick={onHistory}><History size={14} />View history</button></div>
    {unique.size > 3 && <label className="recent-search"><Search size={14} /><input aria-label="Search recent conversations" placeholder="Find a conversation…" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} /></label>}
    <div className="recent-items">{items.slice(current * 3, current * 3 + 3).map(run => <button className="recent-conversation" key={run.id} onClick={() => onOpen(run)}><span className="recent-icon"><MessageSquare size={16} /></span><span><strong>{run.query}</strong><small>{date(run.created_at)}{run.status === 'blocked' ? ' · Needs attention' : run.status === 'running' || run.status === 'queued' ? ' · In progress' : ''}</small></span><ChevronRight size={15} /></button>)}{!items.length && <p className="recent-empty">{query ? 'No conversations match your search.' : 'Your conversations will appear here after you ask a question.'}</p>}</div>
    <div className="recent-pagination"><span>{items.length ? `${current * 3 + 1}–${Math.min(current * 3 + 3, items.length)} of ${items.length}` : 'No conversations yet'}</span><div><button aria-label="Previous recent conversations" disabled={!current} onClick={() => setPage(current - 1)}><ChevronLeft size={15} /></button><button aria-label="Next recent conversations" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}><ChevronRight size={15} /></button></div></div>
  </section>
}

export function ConversationHistory({ conversations, active, onSelect, onClose, loading, error }: { conversations: ConversationSummary[]; active: string; onSelect: (id: string) => void; onClose: () => void; loading: boolean; error: string }) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const close = useRef<HTMLButtonElement>(null)
  useEffect(() => { const prior = document.activeElement as HTMLElement; close.current?.focus(); return () => prior?.focus() }, [])
  const items = [...conversations].sort((a, b) => (b.updated_at || b.created_at || 0) - (a.updated_at || a.created_at || 0)).filter(item => item.title.toLowerCase().includes(query.toLowerCase()))
  const pages = Math.max(1, Math.ceil(items.length / 10))
  const current = Math.min(page, pages - 1)
  return <div className="history-backdrop" onClick={onClose}><aside className="history-panel" role="dialog" aria-modal="true" aria-labelledby="history-heading" onClick={event => event.stopPropagation()} onKeyDown={event => {
    if (event.key === 'Escape') onClose()
    if (event.key === 'Tab') {
      const targets = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input'))
      const first = targets[0], last = targets[targets.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
  }}><div className="history-heading"><div><span className="eyebrow">Your workspace</span><h2 id="history-heading">Conversation history</h2><p>Only your conversations are shown.</p></div><button className="icon-button" ref={close} aria-label="Close conversation history" onClick={onClose}><X size={19} /></button></div><label className="history-search"><Search size={16} /><input aria-label="Search conversation history" placeholder="Search your conversations…" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} /></label><div className="history-list">{loading && <p role="status">Loading your conversations…</p>}{error && <p role="alert" className="alert">{error}</p>}{!loading && !error && !items.length && <p className="recent-empty">{query ? 'No matching conversations.' : 'No conversations yet. Start a new question to begin.'}</p>}{items.slice(current * 10, current * 10 + 10).map(item => <button className={'history-item ' + (item.id === active ? 'active' : '')} key={item.id} aria-current={item.id === active ? 'true' : undefined} onClick={() => onSelect(item.id)}><MessageSquare size={17} /><span><strong>{item.title}</strong><small>{item.updated_at || item.created_at ? date(item.updated_at || item.created_at || 0) : 'Saved conversation'}</small></span><ChevronRight size={14} /></button>)}</div><div className="recent-pagination"><span>{items.length} conversations</span><div><button aria-label="Previous history page" disabled={!current} onClick={() => setPage(current - 1)}><ChevronLeft size={15} /></button><button aria-label="Next history page" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}><ChevronRight size={15} /></button></div></div></aside></div>
}
