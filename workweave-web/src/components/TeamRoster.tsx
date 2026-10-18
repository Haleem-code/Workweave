'use client'

import { useEffect, useState } from 'react'
import { ArrowRight, Check, Plus, RefreshCw, Shield, Trash2, User, Users } from 'lucide-react'
import { api } from '../api'
import { SlackIcon, ClickUpIcon } from './BrandIcons'

type RosterMember = {
  id: string
  name: string
  role: string
  responsibility: string
  clickup_id: string
  slack_id: string
  evidence_ids: string[]
  confirmed: boolean
}

type ClickUpMember = {
  id: string
  username: string
  email: string
}

export function TeamRoster({
  base,
  onConnections,
  onPeople,
  onCitation,
}: {
  base: string
  onConnections: () => void
  onPeople: () => void
  onCitation: (id: string) => void
}) {
  const [members, setMembers] = useState<RosterMember[]>([])
  const [clickupUsers, setClickupUsers] = useState<ClickUpMember[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // Form state
  const [formName, setFormName] = useState('')
  const [formRole, setFormRole] = useState('')
  const [formResp, setFormResp] = useState('')
  const [formClickupId, setFormClickupId] = useState('')
  const [formSlackId, setFormSlackId] = useState('')
  const [formEvidence, setFormEvidence] = useState<string[]>([])

  const loadData = async () => {
    setBusy(true)
    setError('')
    try {
      const [roster, cuMembers] = await Promise.all([
        api<RosterMember[]>(base + '/roster'),
        api<ClickUpMember[]>(base + '/clickup/members').catch(() => []),
      ])
      setMembers(roster)
      setClickupUsers(cuMembers)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [base])

  const startEdit = (m: RosterMember) => {
    setEditingId(m.id)
    setFormName(m.name)
    setFormRole(m.role || '')
    setFormResp(m.responsibility || '')
    setFormClickupId(m.clickup_id || '')
    setFormSlackId(m.slack_id || '')
    setFormEvidence(m.evidence_ids || [])
  }

  const startNew = () => {
    setEditingId('new')
    setFormName('')
    setFormRole('')
    setFormResp('')
    setFormClickupId('')
    setFormSlackId('')
    setFormEvidence([])
  }

  const cancelEdit = () => {
    setEditingId(null)
  }

  const saveMember = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api(base + '/roster', 'PUT', {
        id: editingId === 'new' ? null : editingId,
        name: formName.trim(),
        role: formRole.trim(),
        responsibility: formResp.trim(),
        clickup_id: formClickupId.trim(),
        slack_id: formSlackId.trim(),
        evidence_ids: formEvidence,
      })
      setEditingId(null)
      await loadData()
      setNotice(`Saved ${formName} to Team Roster.`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="team-roster-page">
      <header className="page-heading">
        <span className="eyebrow">YOUR COMPANY · TEAM ROSTER</span>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>Who works on what.</h1>
            <p>Define roles, responsibilities, and link ClickUp and Slack identities so FalkorDB can route incoming tasks accurately.</p>
          </div>
          <button className="primary" onClick={startNew} disabled={busy || editingId === 'new'}>
            <Plus size={16} /> Add Team Member
          </button>
        </div>
      </header>

      {error && <div className="alert" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}

      {/* Editor Modal / Panel */}
      {editingId && (
        <section className="panel roster-edit-form" aria-label="Edit Member">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{editingId === 'new' ? 'NEW PERSON' : 'EDIT MEMBER'}</span>
              <h2>{editingId === 'new' ? 'Add Person to Roster' : `Edit ${formName}`}</h2>
            </div>
            <button className="text-button" onClick={cancelEdit}>Cancel</button>
          </div>

          <form onSubmit={saveMember}>
            <div className="connection-fields">
              <label>
                Full Name
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  placeholder="e.g. Ada Bello"
                />
              </label>

              <label>
                Role Title
                <input
                  type="text"
                  value={formRole}
                  onChange={e => setFormRole(e.target.value)}
                  placeholder="e.g. Finance Manager"
                />
              </label>
            </div>

            <label>
              Responsibilities & Domain Expertise
              <small>Keywords in this description are matched when AI triages Slack messages to assign tasks.</small>
              <textarea
                rows={4}
                value={formResp}
                onChange={e => setFormResp(e.target.value)}
                placeholder="e.g. Invoicing, purchase orders, client billing, supplier reconciliations..."
              />
            </label>

            <div className="connection-fields">
              <label>
                ClickUp Member
                {clickupUsers.length > 0 ? (
                  <select value={formClickupId} onChange={e => setFormClickupId(e.target.value)}>
                    <option value="">-- Select ClickUp member --</option>
                    {clickupUsers.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.username} ({u.email || u.id})
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formClickupId}
                    onChange={e => setFormClickupId(e.target.value)}
                    placeholder="ClickUp user ID"
                  />
                )}
                {clickupUsers.length === 0 && (
                  <small>
                    Connect ClickUp in Connections to populate members automatically.
                  </small>
                )}
              </label>

              <label>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <SlackIcon size={14} /> Slack Username or ID
                </span>
                <input
                  type="text"
                  value={formSlackId}
                  onChange={e => setFormSlackId(e.target.value)}
                  placeholder="e.g. @ada or U0123456"
                />
              </label>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
              <button className="primary" disabled={busy}>
                <Check size={16} /> Save Member
              </button>
              <button type="button" className="secondary" onClick={cancelEdit}>
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Roster Grid */}
      <div className="roster-grid">
        {members.map(member => (
          <article className="roster-card panel" key={member.id}>
            <div className="roster-card-header">
              <div className="avatar-circle">
                <User size={18} />
              </div>
              <div>
                <h3>{member.name}</h3>
                <span className="roster-role">{member.role || 'Unspecified Role'}</span>
              </div>
            </div>

            <div className="roster-body">
              <p className="roster-resp">
                <strong>Responsibilities:</strong>{' '}
                {member.responsibility || 'No detailed responsibilities listed yet.'}
              </p>

              <div className="roster-identities">
                <span
                  className={'badge ' + (member.clickup_id ? 'ready' : '')}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                >
                  <ClickUpIcon size={13} />
                  ClickUp: {member.clickup_id ? (clickupUsers.find(u => u.id === member.clickup_id)?.username || member.clickup_id) : 'Not linked'}
                </span>
                <span
                  className={'badge ' + (member.slack_id ? 'ready' : '')}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                >
                  <SlackIcon size={13} />
                  Slack: {member.slack_id || 'Not linked'}
                </span>
              </div>

              {member.evidence_ids && member.evidence_ids.length > 0 && (
                <div className="roster-evidence">
                  <small>Document sources:</small>
                  <div className="citations-inline">
                    {member.evidence_ids.map(eid => (
                      <button
                        key={eid}
                        type="button"
                        className="citation-tag"
                        onClick={() => onCitation(eid)}
                      >
                        [{eid.slice(0, 8)}]
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="roster-card-footer">
              <button className="secondary" onClick={() => startEdit(member)} disabled={busy}>
                Edit
              </button>
            </div>
          </article>
        ))}

        {members.length === 0 && !busy && (
          <div className="empty-panel">
            <Users size={32} />
            <h3>No team members yet</h3>
            <p>Add people to your roster or import from document suggestions so tasks can be automatically assigned.</p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              <button className="primary" onClick={startNew}>
                <Plus size={16} /> Add First Member
              </button>
              <button className="secondary" onClick={onPeople}>
                Review Extracted People
              </button>
            </div>
          </div>
        )}
      </div>

      <footer className="connection-footnote">
        <Shield size={17} />
        <p>
          FalkorDB uses each member's responsibilities and past task completion rates to rank assignees when messages arrive in Slack.
        </p>
        <button className="text-button" onClick={onConnections}>
          Configure Integrations <ArrowRight size={15} />
        </button>
      </footer>
    </div>
  )
}
