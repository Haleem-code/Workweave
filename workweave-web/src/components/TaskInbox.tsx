'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Award,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Edit2,
  ExternalLink,
  FileText,
  Hash,
  Inbox,
  MessageSquare,
  RefreshCw,
  RotateCcw,
  Send,
  Shield,
  Sparkles,
  User,
  Users,
  Workflow,
  X,
} from 'lucide-react'
import { api } from '../api'
import { SlackIcon, ClickUpIcon } from './BrandIcons'

export type Candidate = {
  person_id: string
  name: string
  role?: string
  clickup_id?: string
  score: number
  evidence_ids?: string[]
  path_ids?: string[]
  evidence_chunks?: { id: string; text: string; location?: string }[]
  breakdown?: {
    role_match?: boolean
    responsibility_score?: number
    completed_outcomes?: number
    active_load?: number
  }
}

export type Proposal = {
  id: string
  event_id?: string
  channel?: string
  thread_ts?: string
  author_id?: string
  author_name?: string
  slack_message?: string
  title: string
  description?: string
  urgency?: string
  recommended_person_id?: string
  recommended_person_name?: string
  recommended_role?: string
  recommended_clickup_id?: string
  recommended_score?: number
  evidence_ids?: string[]
  evidence_chunks?: { id: string; text: string; location?: string }[]
  candidates?: Candidate[]
  reasoning?: string
  state: 'pending' | 'approved' | 'completed' | 'rejected'
  outbox_id?: string
  outbox_state?: string
  outbox_error?: string
  clickup_task_id?: string
  clickup_task_url?: string
  created_at: number
  updated_at?: number
}

function formatTime(epochSec: number) {
  if (!epochSec) return ''
  const d = new Date(epochSec * 1000)
  return d.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function TaskInbox({
  base,
  onRoster,
  onConnections,
  onCitation,
}: {
  base: string
  onRoster?: () => void
  onConnections?: () => void
  onCitation?: (id: string) => void
}) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [filterState, setFilterState] = useState<'pending' | 'completed' | 'rejected' | 'all'>('pending')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // Card modifications before approval
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, Candidate>>({})
  const [editedTitles, setEditedTitles] = useState<Record<string, string>>({})
  const [editedDescriptions, setEditedDescriptions] = useState<Record<string, string>>({})
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({})
  const [actingProposalId, setActingProposalId] = useState<string | null>(null)

  const loadProposals = async (showLoading = true) => {
    if (showLoading) setBusy(true)
    setError('')
    try {
      const data = await api<Proposal[]>(`${base}/proposals?state=${filterState}`)
      setProposals(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      if (showLoading) setBusy(false)
    }
  }

  useEffect(() => {
    void loadProposals()
  }, [base, filterState])

  // Periodic polling for status updates (every 6 seconds while on inbox)
  useEffect(() => {
    const timer = setInterval(() => {
      void loadProposals(false)
    }, 6000)
    return () => clearInterval(timer)
  }, [base, filterState])

  const handleApprove = async (p: Proposal) => {
    setActingProposalId(p.id)
    setError('')
    setNotice('')
    try {
      const candidate = selectedCandidates[p.id] || {
        person_id: p.recommended_person_id || '',
        name: p.recommended_person_name || '',
        clickup_id: p.recommended_clickup_id || '',
      }
      const title = editedTitles[p.id] !== undefined ? editedTitles[p.id] : p.title
      const description = editedDescriptions[p.id] !== undefined ? editedDescriptions[p.id] : p.description

      await api(`${base}/proposals/${p.id}/approve`, 'POST', {
        title,
        description,
        assignee_person_id: candidate.person_id || undefined,
        assignee_clickup_id: candidate.clickup_id || undefined,
      })

      setNotice(`Task approved! Creating in ClickUp for ${candidate.name || 'assignee'}...`)
      await loadProposals(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setActingProposalId(null)
    }
  }

  const handleReject = async (p: Proposal) => {
    if (!window.confirm('Are you sure you want to dismiss this inbound request?')) return
    setActingProposalId(p.id)
    setError('')
    setNotice('')
    try {
      await api(`${base}/proposals/${p.id}/reject`, 'POST')
      setNotice('Request dismissed.')
      await loadProposals(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setActingProposalId(null)
    }
  }

  const handleRetry = async (p: Proposal) => {
    if (!p.outbox_id) return
    setActingProposalId(p.id)
    setError('')
    setNotice('')
    try {
      await api(`${base}/outbox/${p.outbox_id}/retry`, 'POST')
      setNotice('Retrying ClickUp task creation...')
      await loadProposals(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setActingProposalId(null)
    }
  }

  const toggleExpand = (id: string) => {
    setExpandedCards(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const pendingCount = proposals.filter(p => p.state === 'pending').length

  return (
    <div className="task-inbox-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <SlackIcon size={14} /> SLACK TRIAGE &amp; <ClickUpIcon size={14} /> CLICKUP ASSIGNMENT
          </span>
          <h1>Task Inbox</h1>
          <p>
            Review inbound work requests from Slack. FalkorDB and AI evaluate roles, responsibilities, and past task
            outcomes to propose the ideal assignee. You approve before anything is created in ClickUp.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {onRoster && (
            <button className="secondary" onClick={onRoster}>
              <Users size={16} />
              Team Roster
            </button>
          )}
          {onConnections && (
            <button className="secondary" onClick={onConnections}>
              <Workflow size={16} />
              Connections
            </button>
          )}
          <button className="icon-button" onClick={() => void loadProposals(true)} title="Refresh inbox" disabled={busy}>
            <RefreshCw size={18} className={busy ? 'loading-spinner' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <div className="alert" role="alert" style={{ marginBottom: '20px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError('')} className="bracket-btn text-button" style={{ marginLeft: 'auto' }}>
            Dismiss
          </button>
        </div>
      )}

      {notice && (
        <div className="alert success" role="status" style={{ marginBottom: '20px' }}>
          <Check size={18} />
          <span>{notice}</span>
          <button onClick={() => setNotice('')} className="bracket-btn text-button" style={{ marginLeft: 'auto' }}>
            ✕
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="segmented" style={{ marginBottom: '24px', maxWidth: '480px' }}>
        <button
          className={filterState === 'pending' ? 'active' : ''}
          onClick={() => setFilterState('pending')}
        >
          Pending {filterState === 'pending' && proposals.length > 0 ? `(${proposals.length})` : ''}
        </button>
        <button
          className={filterState === 'completed' ? 'active' : ''}
          onClick={() => setFilterState('completed')}
        >
          Completed
        </button>
        <button
          className={filterState === 'rejected' ? 'active' : ''}
          onClick={() => setFilterState('rejected')}
        >
          Rejected
        </button>
        <button
          className={filterState === 'all' ? 'active' : ''}
          onClick={() => setFilterState('all')}
        >
          All
        </button>
      </div>

      {proposals.length === 0 && !busy && (
        <div className="empty">
          <span className="empty-icon">
            <Inbox size={32} />
          </span>
          <h2>
            {filterState === 'pending'
              ? 'No pending proposals'
              : filterState === 'completed'
              ? 'No completed tasks yet'
              : 'Inbox is clear'}
          </h2>
          <p>
            {filterState === 'pending'
              ? 'When a team member posts a request or bug report in a watched Slack channel, Workweave triages it, queries FalkorDB for matching team members, and stages the task here for your approval.'
              : 'Tasks approved here will create tickets in ClickUp with an audit marker and reply back into the Slack thread.'}
          </p>
          <div className="empty-actions" style={{ display: 'flex', gap: '12px' }}>
            {onConnections && (
              <button className="secondary" onClick={onConnections}>
                <Hash size={16} />
                Check Slack Channels
              </button>
            )}
            {onRoster && (
              <button className="primary" onClick={onRoster}>
                <Users size={16} />
                Manage Team Roster
              </button>
            )}
          </div>
        </div>
      )}

      <div className="proposal-list">
        {proposals.map(p => {
          const isActing = actingProposalId === p.id
          const isExpanded = Boolean(expandedCards[p.id])
          const chosenCandidate =
            selectedCandidates[p.id] ||
            (p.candidates && p.candidates.length > 0
              ? p.candidates[0]
              : {
                  person_id: p.recommended_person_id || '',
                  name: p.recommended_person_name || 'Unassigned',
                  role: p.recommended_role || '',
                  clickup_id: p.recommended_clickup_id || '',
                  score: p.recommended_score || 0,
                  evidence_ids: p.evidence_ids || [],
                  evidence_chunks: p.evidence_chunks || [],
                })

          const effectiveTitle = editedTitles[p.id] !== undefined ? editedTitles[p.id] : p.title
          const effectiveDesc = editedDescriptions[p.id] !== undefined ? editedDescriptions[p.id] : p.description || ''

          const isOutboxFailed = p.outbox_state === 'failed'
          const isCreating = !isOutboxFailed && (p.state === 'approved' || p.outbox_state === 'creating' || p.outbox_state === 'replying')

          return (
            <article key={p.id} className={`panel proposal-card proposal-${p.state}`}>
              {/* Header */}
              <div className="proposal-header">
                <div className="proposal-meta-left">
                  <span className="channel-badge">
                    <Hash size={13} />
                    {p.channel || 'slack'}
                  </span>
                  <span className="author-tag">
                    <User size={13} />
                    {p.author_name || 'Team member'}
                  </span>
                  <span className="time-tag">
                    <Clock size={13} />
                    {formatTime(p.created_at)}
                  </span>
                </div>

                <div className="proposal-meta-right">
                  {p.urgency && p.urgency !== 'normal' && (
                    <span className={`urgency-pill urgency-${p.urgency}`}>{p.urgency.toUpperCase()}</span>
                  )}
                  {p.state === 'pending' && <span className="status-pill status-pending">Needs Approval</span>}
                  {p.state === 'completed' && <span className="status-pill status-completed">Created in ClickUp</span>}
                  {p.state === 'rejected' && <span className="status-pill status-rejected">Dismissed</span>}
                  {isCreating && <span className="status-pill status-creating">{p.clickup_task_id ? 'Confirming in Slack...' : 'Creating ClickUp task...'}</span>}
                  {isOutboxFailed && <span className="status-pill status-failed">Delivery Error</span>}
                </div>
              </div>

              {/* Slack original message block */}
              <div className="slack-message-quote">
                <div className="slack-quote-label">
                  <SlackIcon size={15} />
                  <span>Slack Message Content</span>
                </div>
                <blockquote className="preserve-lines">{p.slack_message || effectiveDesc}</blockquote>
              </div>

              {/* Task Details Section */}
              <div className="task-details-form">
                <div className="field-group">
                  <label htmlFor={`title-${p.id}`} className="field-label">
                    Task Title for ClickUp
                  </label>
                  {p.state === 'pending' ? (
                    <input
                      id={`title-${p.id}`}
                      type="text"
                      className="input"
                      value={effectiveTitle}
                      onChange={e => setEditedTitles({ ...editedTitles, [p.id]: e.target.value })}
                      placeholder="Task Title"
                      disabled={isActing}
                    />
                  ) : (
                    <h3 className="proposal-title-static">{effectiveTitle}</h3>
                  )}
                </div>

                <div className="field-group">
                  <label htmlFor={`desc-${p.id}`} className="field-label">
                    Task Description & Context
                  </label>
                  {p.state === 'pending' ? (
                    <textarea
                      id={`desc-${p.id}`}
                      rows={3}
                      className="textarea"
                      value={effectiveDesc}
                      onChange={e => setEditedDescriptions({ ...editedDescriptions, [p.id]: e.target.value })}
                      placeholder="Task description"
                      disabled={isActing}
                    />
                  ) : (
                    <p className="proposal-desc-static preserve-lines">{effectiveDesc}</p>
                  )}
                </div>

                {p.reasoning && (
                  <div className="ai-rationale-box">
                    <Sparkles size={15} />
                    <span>
                      <strong>AI Triage:</strong> {p.reasoning}
                    </span>
                  </div>
                )}
              </div>

              {/* Assignee & FalkorDB Matching Section */}
              <div className="assignee-section">
                <div className="assignee-section-heading">
                  <h4>Recommended Assignee</h4>
                  <span className="small muted">Ranked via FalkorDB roles, responsibilities & past task outcomes</span>
                </div>

                {/* Candidate Selection */}
                {p.candidates && p.candidates.length > 1 && p.state === 'pending' && (
                  <div className="candidate-options">
                    <span className="small muted">Change assignee:</span>
                    <div className="candidate-chips">
                      {p.candidates.map(c => {
                        const isSelected = (chosenCandidate?.person_id || chosenCandidate?.name) === (c.person_id || c.name)
                        return (
                          <button
                            key={c.person_id || c.name}
                            type="button"
                            className={`candidate-chip ${isSelected ? 'selected' : ''}`}
                            onClick={() => setSelectedCandidates({ ...selectedCandidates, [p.id]: c })}
                          >
                            <strong>{c.name}</strong>
                            {c.role && <span className="chip-role">({c.role})</span>}
                            <span className="chip-score">{c.score > 0 ? `+${c.score.toFixed(1)}` : c.score.toFixed(1)}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Selected candidate card */}
                <div className="candidate-hero-card">
                  <div className="candidate-avatar">
                    <User size={22} />
                  </div>
                  <div className="candidate-info">
                    <div className="candidate-name-row">
                      <strong>{chosenCandidate?.name || 'Unassigned'}</strong>
                      {chosenCandidate?.role && <span className="role-badge">{chosenCandidate.role}</span>}
                      {chosenCandidate?.score !== undefined && (
                        <span className="score-badge">
                          <Award size={13} />
                          Fit Score: {chosenCandidate.score.toFixed(1)}
                        </span>
                      )}
                    </div>

                    <div className="candidate-integrations-row">
                      {chosenCandidate?.clickup_id ? (
                        <span className="integration-tag connected">
                          <ClickUpIcon size={13} />
                          ClickUp User ID: {chosenCandidate.clickup_id}
                        </span>
                      ) : (
                        <span className="integration-tag warning">
                          <AlertCircle size={12} />
                          No ClickUp ID mapped. (Task will be assigned in ClickUp if mapped in Team Roster)
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* FalkorDB Evidence Breakdown & Citations */}
                {chosenCandidate && (
                  <div className="evidence-panel">
                    <button
                      type="button"
                      className="evidence-toggle-btn"
                      onClick={() => toggleExpand(p.id)}
                    >
                      <Shield size={14} />
                      <span>
                        Why this person: {chosenCandidate.breakdown?.role_match ? 'Role matched · ' : ''}
                        {(chosenCandidate.evidence_ids?.length || 0)} evidence sources
                      </span>
                      {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                    </button>

                    {isExpanded && (
                      <div className="evidence-trail-body">
                        {chosenCandidate.path_ids && chosenCandidate.path_ids.length > 0 && (
                          <div className="evidence-excerpt-card">
                            <span className="small muted">Stored graph path · Person → Role → Responsibility</span>
                            <p className="small" style={{ overflowWrap: 'anywhere' }}>{chosenCandidate.path_ids.join(' → ')}</p>
                          </div>
                        )}
                        {chosenCandidate.breakdown && (
                          <div className="breakdown-grid">
                            <div className="breakdown-item">
                              <span className="breakdown-label">Role Alignment</span>
                              <span className="breakdown-value">
                                {chosenCandidate.breakdown.role_match ? '✅ Direct Match' : 'Neutral'}
                              </span>
                            </div>
                            <div className="breakdown-item">
                              <span className="breakdown-label">Responsibility Score</span>
                              <span className="breakdown-value">
                                +{chosenCandidate.breakdown.responsibility_score?.toFixed(1) || '0.0'}
                              </span>
                            </div>
                            <div className="breakdown-item">
                              <span className="breakdown-label">Past On-time Outcomes</span>
                              <span className="breakdown-value">
                                +{chosenCandidate.breakdown.completed_outcomes || 0} tasks
                              </span>
                            </div>
                            <div className="breakdown-item">
                              <span className="breakdown-label">Active Workload</span>
                              <span className="breakdown-value">
                                -{chosenCandidate.breakdown.active_load || 0} open
                              </span>
                            </div>
                          </div>
                        )}

                        {chosenCandidate.evidence_chunks && chosenCandidate.evidence_chunks.length > 0 && (
                          <div className="evidence-excerpts">
                            <span className="small muted">FalkorDB Verified Graph Evidence:</span>
                            {chosenCandidate.evidence_chunks.map((chk, i) => (
                              <div key={chk.id || i} className="evidence-excerpt-card">
                                <p className="excerpt-text preserve-lines">{chk.text}</p>
                                {chk.location && <span className="excerpt-location">{chk.location}</span>}
                              </div>
                            ))}
                          </div>
                        )}

                        {chosenCandidate.evidence_ids && chosenCandidate.evidence_ids.length > 0 && onCitation && (
                          <div className="citations-row">
                            <span className="small muted">View Source Docs:</span>
                            <div className="citations">
                              {chosenCandidate.evidence_ids.map((eid, idx) => (
                                <button
                                  key={eid}
                                  type="button"
                                  className="bracket-btn citation-btn"
                                  onClick={() => onCitation(eid)}
                                >
                                  Source {idx + 1}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Error warning if outbox failed */}
              {isOutboxFailed && (
                <div className="outbox-error-box">
                  <AlertCircle size={16} />
                  <div>
                    <strong>Delivery needs attention:</strong>
                    <p className="small">{p.outbox_error || 'Network or token error during task creation.'}</p>
                  </div>
                </div>
              )}

              {/* Action Bar */}
              <div className="proposal-actions">
                {p.state === 'pending' && (
                  <>
                    <button
                      className="primary approve-btn"
                      disabled={isActing || busy}
                      onClick={() => handleApprove(p)}
                    >
                      <Sparkles size={16} />
                      {isActing ? 'Approving...' : 'Approve & Create in ClickUp'}
                    </button>
                    <button
                      className="secondary reject-btn"
                      disabled={isActing || busy}
                      onClick={() => handleReject(p)}
                    >
                      <X size={16} />
                      Dismiss
                    </button>
                  </>
                )}

                {isCreating && (
                  <div className="in-progress-indicator">
                    <span className="loading-spinner" />
                    <span>Creating task in ClickUp and posting Slack confirmation...</span>
                  </div>
                )}

                {p.state === 'completed' && (
                  <div className="completed-actions">
                    {p.clickup_task_url && (
                      <a
                        href={p.clickup_task_url}
                        target="_blank"
                        rel="noreferrer"
                        className="button primary"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                      >
                        <ClickUpIcon size={16} />
                        Open Task in ClickUp
                        <ExternalLink size={14} />
                      </a>
                    )}
                    <span className="completed-confirmation">
                      <Check size={16} />
                      Confirmed in ClickUp & Slack thread notified
                    </span>
                  </div>
                )}

                {isOutboxFailed && (
                  <button
                    className="primary"
                    disabled={isActing || busy}
                    onClick={() => handleRetry(p)}
                  >
                    <RotateCcw size={16} />
                    Retry Creation
                  </button>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
