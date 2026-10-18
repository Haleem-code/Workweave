'use client'

import { useEffect, useState } from 'react'
import { ArrowRight, Check, Copy, ExternalLink, Hash, Link2, Lock, LockKeyhole, RefreshCw, Shield, Sparkles, Unplug, X } from 'lucide-react'
import { api, Preview } from '../api'
import { ImportReview } from './ImportReview'
import { SlackIcon, ClickUpIcon } from './BrandIcons'

type ConnectionStatus = {
  slack: { configured: boolean; request_url?: string; channels?: string[]; team_name?: string; team_id?: string; app_id?: string }
  clickup: { configured: boolean; list_id?: string; list_name?: string }
}

type SlackChannel = { id: string; name: string; is_private: boolean; is_member: boolean; watched: boolean }

export function Connections({ base, onDocuments, onInbox, onRoster }: { base: string; onDocuments: () => void; onInbox?: () => void; onRoster?: () => void }) {
  const [status, setStatus] = useState<ConnectionStatus | null>(null)
  const [active, setActive] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [copied, setCopied] = useState(false)

  // Slack setup state
  const [slackToken, setSlackToken] = useState('')
  const [slackSecret, setSlackSecret] = useState('')
  const [slackAppId, setSlackAppId] = useState('')
  const [channels, setChannels] = useState<SlackChannel[]>([])
  const [loadingChannels, setLoadingChannels] = useState(false)

  // ClickUp setup state
  const [clickupToken, setClickupToken] = useState('')
  const [clickupListId, setClickupListId] = useState('')

  // Snapshot preview state
  const [preview, setPreview] = useState<Preview | null>(null)

  const reload = async () => {
    try {
      const data = await api<ConnectionStatus>(base + '/integrations/status')
      setStatus(data)
      if (data.clickup?.list_id && !clickupListId) {
        setClickupListId(data.clickup.list_id)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  useEffect(() => {
    void reload()
  }, [base])

  const loadChannels = async () => {
    setLoadingChannels(true)
    try {
      const chs = await api<SlackChannel[]>(base + '/integrations/slack/channels')
      setChannels(chs)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingChannels(false)
    }
  }

  useEffect(() => {
    if (active === 'slack' && status?.slack?.configured) {
      void loadChannels()
    }
  }, [active, status?.slack?.configured])

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const handleCopyUrl = () => {
    if (status?.slack?.request_url) {
      void navigator.clipboard.writeText(status.slack.request_url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const toggleChannel = async (channelId: string, currentWatched: boolean) => {
    const currentList = status?.slack?.channels || []
    const updated = currentWatched
      ? currentList.filter(id => id !== channelId)
      : [...currentList, channelId]

    await run(async () => {
      await api(base + '/integrations/slack/channels', 'PUT', { channels: updated })
      setChannels(prev => prev.map(c => c.id === channelId ? { ...c, watched: !currentWatched } : c))
      await reload()
      setNotice(currentWatched ? `Stopped watching channel` : `Now watching channel for tasks`)
    })
  }

  return (
    <div className="connections-page">
      <header className="page-heading">
        <span className="eyebrow">WORKPLACE INTEGRATIONS</span>
        <h1>Connect Slack and ClickUp.</h1>
        <p>Listen for Slack requests in real time, extract tasks with AI, and assign them to ClickUp members after review.</p>
      </header>

      <div className="connection-promise">
        <LockKeyhole size={20} />
        <div>
          <strong>Company-isolated credentials · Human approval before write · Deduplicated</strong>
          <p>Each company retains its own encrypted credentials, dedicated Slack webhook route, and ClickUp destination.</p>
        </div>
      </div>

      {error && <div className="alert" role="alert">{error}</div>}
      {notice && <div className="notice" role="status">{notice}</div>}

      <div className="connection-grid">
        {/* Slack Card */}
        <article className="connection-card">
          <div className="connection-card-heading">
            <span className="connection-brand slack" aria-hidden="true">
              <SlackIcon size={28} />
            </span>
            <span className={'connection-state ' + (status?.slack?.configured ? 'is-connected' : '')}>
              {status?.slack?.configured ? 'Live Events Connected' : 'Not configured'}
            </span>
          </div>
          <h2>Slack Real-Time Events</h2>
          <p>Receive messages from selected public and private channels via the Slack Events API verified with your signing secret.</p>
          {status?.slack?.configured && (
            <small>
              Workspace: <strong>{status.slack.team_name || status.slack.team_id || 'Connected'}</strong><br />
              Watching: <strong>{status.slack.channels?.length || 0} channel(s)</strong>
            </small>
          )}
          <button
            className={status?.slack?.configured ? 'secondary' : 'primary'}
            disabled={busy}
            onClick={() => {
              setActive('slack')
              setError('')
              setNotice('')
            }}
          >
            {status?.slack?.configured ? <RefreshCw size={16} /> : <Link2 size={16} />}
            {status?.slack?.configured ? 'Manage Slack Settings' : 'Configure Slack'}
            <ArrowRight size={16} />
          </button>
        </article>

        {/* ClickUp Card */}
        <article className="connection-card">
          <div className="connection-card-heading">
            <span className="connection-brand clickup" aria-hidden="true">
              <ClickUpIcon size={28} />
            </span>
            <span className={'connection-state ' + (status?.clickup?.configured ? 'is-connected' : '')}>
              {status?.clickup?.configured ? 'Connected' : 'Not configured'}
            </span>
          </div>
          <h2>ClickUp Task Assignment</h2>
          <p>Create tasks in your designated ClickUp list, assigned to the qualified team member picked by company knowledge and approved by you.</p>
          {status?.clickup?.configured && (
            <small>
              Target list ID: <strong>{status.clickup.list_id}</strong><br />
              Status: <strong>Ready for task dispatch</strong>
            </small>
          )}
          <button
            className={status?.clickup?.configured ? 'secondary' : 'primary'}
            disabled={busy}
            onClick={() => {
              setActive('clickup')
              setError('')
              setNotice('')
            }}
          >
            {status?.clickup?.configured ? <RefreshCw size={16} /> : <Link2 size={16} />}
            {status?.clickup?.configured ? 'Manage ClickUp' : 'Configure ClickUp'}
            <ArrowRight size={16} />
          </button>
        </article>
      </div>

      {/* Modal Popup for Slack or ClickUp Configuration */}
      {active && (
        <div className="modal-backdrop" onClick={() => setActive('')}>
          <section
            className="modal connection-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="connection-modal-title"
            onClick={e => e.stopPropagation()}
            onKeyDown={e => {
              if (e.key === 'Escape') setActive('')
            }}
          >
            <button
              className="icon-button close-button"
              aria-label="Close dialog"
              onClick={() => setActive('')}
            >
              <X size={18} />
            </button>

            {active === 'slack' && (
              <div className="connection-form-modal-content" aria-label="Configure Slack">
                <div className="connection-modal-header">
                  <div>
                    <span className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <SlackIcon size={14} /> SLACK · EVENTS & BOT SETUP
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                      <SlackIcon size={26} />
                      <h2 id="connection-modal-title" style={{ margin: 0 }}>
                        {status?.slack?.configured ? 'Slack Workspace Configuration' : 'Connect Your Slack App'}
                      </h2>
                    </div>
                  </div>
                </div>

                {status?.slack?.configured && status.slack.request_url && (
                  <div className="webhook-url-banner">
                    <label>
                      <strong>Slack Events API Request URL</strong>
                      <small>Copy and paste this into your Slack App &gt; Event Subscriptions &gt; Request URL:</small>
                      <div className="url-copy-box">
                        <code>{status.slack.request_url}</code>
                        <button type="button" className="secondary" onClick={handleCopyUrl}>
                          {copied ? <Check size={14} /> : <Copy size={14} />}
                          {copied ? 'Copied' : 'Copy URL'}
                        </button>
                      </div>
                    </label>
                  </div>
                )}

                <form onSubmit={e => {
                  e.preventDefault()
                  void run(async () => {
                    const res = await api<{ request_url: string }>(base + '/integrations/slack', 'PUT', {
                      token: slackToken,
                      signing_secret: slackSecret,
                      app_id: slackAppId.trim(),
                    })
                    setSlackToken('')
                    setSlackSecret('')
                    await reload()
                    setNotice('Slack connected successfully! Paste the Request URL below into api.slack.com')
                  })
                }}>
                  <div className="connection-fields">
                    <label>
                      Bot User OAuth Token (xoxb-...)
                      {status?.slack?.configured && <small>Leave blank to keep existing saved token.</small>}
                      <input
                        type="password"
                        autoComplete="off"
                        value={slackToken}
                        onChange={e => setSlackToken(e.target.value)}
                        required={!status?.slack?.configured}
                        placeholder={status?.slack?.configured ? 'Saved encrypted on server' : 'xoxb-...'}
                        disabled={busy}
                      />
                    </label>

                    <label>
                      Signing Secret
                      {status?.slack?.configured && <small>Leave blank to keep existing saved secret.</small>}
                      <input
                        type="password"
                        autoComplete="off"
                        value={slackSecret}
                        onChange={e => setSlackSecret(e.target.value)}
                        required={!status?.slack?.configured}
                        placeholder={status?.slack?.configured ? 'Saved encrypted on server' : 'From Basic Information'}
                        disabled={busy}
                      />
                    </label>

                    <label>
                      App ID (Optional)
                      <input
                        type="text"
                        value={slackAppId}
                        onChange={e => setSlackAppId(e.target.value)}
                        placeholder="A0123456789"
                        disabled={busy}
                      />
                    </label>
                  </div>

                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="primary" disabled={busy || (!slackToken && !status?.slack?.configured)}>
                      {busy ? 'Saving...' : 'Save Slack Credentials'}
                      <ArrowRight size={16} />
                    </button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => setActive('')}>
                      Cancel
                    </button>
                  </div>
                </form>

                {/* Channels Selector if configured */}
                {status?.slack?.configured && (
                  <div className="channels-section" style={{ marginTop: '24px', borderTop: '1px solid var(--outline-variant)', paddingTop: '18px' }}>
                    <div className="panel-heading" style={{ marginBottom: '12px' }}>
                      <div>
                        <h3>Select Watched Channels</h3>
                        <p className="small muted">Choose which public or private channels Workweave should monitor. (Invite the bot first with <code>/invite @YourBot</code>).</p>
                      </div>
                      <button type="button" className="secondary" disabled={loadingChannels} onClick={() => void loadChannels()}>
                        <RefreshCw size={14} /> Refresh channels
                      </button>
                    </div>

                    {loadingChannels && <p className="muted">Loading channels from Slack...</p>}
                    {!loadingChannels && channels.length === 0 && (
                      <p className="empty-inline">No channels found. Verify bot permissions and make sure bot is added to your workspace.</p>
                    )}

                    {channels.length > 0 && (
                      <div className="channels-grid">
                        {channels.map(ch => (
                          <label key={ch.id} className={'channel-chip ' + (ch.watched ? 'is-watched' : '')}>
                            <input
                              type="checkbox"
                              checked={ch.watched}
                              disabled={busy}
                              onChange={() => void toggleChannel(ch.id, ch.watched)}
                            />
                            {ch.is_private ? <Lock size={13} /> : <Hash size={13} />}
                            <span>{ch.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {status?.slack?.configured && (
                  <div className="connection-disconnect" style={{ marginTop: '24px' }}>
                    <p>Disconnecting removes the saved credentials and deactivates the webhook route.</p>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => {
                        void run(async () => {
                          await api(base + '/integrations/slack', 'DELETE')
                          await reload()
                          setActive('')
                          setNotice('Slack disconnected.')
                        })
                      }}
                    >
                      <Unplug size={15} /> Disconnect Slack
                    </button>
                  </div>
                )}
              </div>
            )}

            {active === 'clickup' && (
              <div className="connection-form-modal-content" aria-label="Configure ClickUp">
                <div className="connection-modal-header">
                  <div>
                    <span className="eyebrow" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <ClickUpIcon size={14} /> CLICKUP · TASK DISPATCH
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                      <ClickUpIcon size={26} />
                      <h2 id="connection-modal-title" style={{ margin: 0 }}>
                        {status?.clickup?.configured ? 'ClickUp Workspace Configuration' : 'Connect ClickUp Account'}
                      </h2>
                    </div>
                  </div>
                </div>

                <p className="small muted">
                  Enter your ClickUp personal API token and the destination list ID where tasks should be created upon your approval.
                  <a href="https://developer.clickup.com/docs/authentication" target="_blank" rel="noreferrer"> ClickUp setup guide ↗</a>
                </p>

                <form onSubmit={e => {
                  e.preventDefault()
                  void run(async () => {
                    await api(base + '/integrations/clickup', 'PUT', {
                      token: clickupToken,
                      list_id: clickupListId.trim(),
                    })
                    setClickupToken('')
                    await reload()
                    setActive('')
                    setNotice('ClickUp configured successfully!')
                  })
                }}>
                  <div className="connection-fields">
                    <label>
                      ClickUp Personal API Token (pk_...)
                      {status?.clickup?.configured && <small>Leave blank to keep existing token.</small>}
                      <input
                        type="password"
                        autoComplete="off"
                        value={clickupToken}
                        onChange={e => setClickupToken(e.target.value)}
                        required={!status?.clickup?.configured}
                        placeholder={status?.clickup?.configured ? 'Saved encrypted on server' : 'pk_...'}
                        disabled={busy}
                      />
                    </label>

                    <label>
                      Target ClickUp List ID
                      <input
                        type="text"
                        value={clickupListId}
                        onChange={e => setClickupListId(e.target.value)}
                        required
                        placeholder="e.g. 9012345678"
                        disabled={busy}
                      />
                    </label>
                  </div>

                  <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <button className="primary" disabled={busy || (!clickupToken && !status?.clickup?.configured)}>
                      {busy ? 'Saving...' : 'Save ClickUp Settings'}
                      <ArrowRight size={16} />
                    </button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => setActive('')}>
                      Cancel
                    </button>
                  </div>
                </form>

                {status?.clickup?.configured && (
                  <div className="connection-disconnect" style={{ marginTop: '24px' }}>
                    <p>Disconnecting removes the saved ClickUp token and list ID.</p>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => {
                        void run(async () => {
                          await api(base + '/integrations/clickup', 'DELETE')
                          await reload()
                          setActive('')
                          setNotice('ClickUp disconnected.')
                        })
                      }}
                    >
                      <Unplug size={15} /> Disconnect ClickUp
                    </button>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}


      {/* Snapshot Preview section (Import Review) */}
      {preview && (
        <ImportReview
          preview={preview}
          mappings={[]}
          onChange={() => {}}
          busy={busy}
          onConfirm={() => {
            void run(async () => {
              await api(base + '/imports/' + preview.id + '/confirm', 'POST', { mappings: [] })
              setPreview(null)
              setNotice('Snapshot imported into company knowledge.')
            })
          }}
        />
      )}

      <footer className="connection-footnote">
        <Check size={17} />
        <p>Live messages from Slack undergo AI task triage. Verified task proposals appear in your Task Inbox for human review and assignment to ClickUp.</p>
        <div style={{ display: 'flex', gap: '8px' }}>
          {onRoster && <button className="secondary" onClick={onRoster}><Shield size={14} />Team Roster</button>}
          {onInbox && <button className="primary" onClick={onInbox}><Sparkles size={14} />Open Task Inbox</button>}
        </div>
      </footer>
    </div>
  )
}
