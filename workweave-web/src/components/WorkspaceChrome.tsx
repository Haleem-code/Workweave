'use client'

import { ReactNode, useEffect, useRef, useState } from 'react'
import { Building2, Check, ChevronDown, LogOut, Settings2, UserRound, Users, X } from 'lucide-react'
import { Company } from '../api'

export type Account = { id?: string; username: string; name?: string; email?: string; avatar_url?: string | null }

function Popover({ label, trigger, children, align = 'left' }: { label: string; trigger: ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const close = () => { setOpen(false); button.current?.focus() }
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', outside)
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"], [role="menuitemradio"]')?.focus()
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  return <div className={'ww-popover ' + align} ref={root} onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); close() }
    if (event.key === 'Tab') setOpen(false)
    if (!open || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const items = Array.from(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"], [role="menuitemradio"]') || [])
    const current = items.indexOf(document.activeElement as HTMLButtonElement)
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowUp' ? -1 : 1) + items.length) % items.length
    items[next]?.focus()
  }}>
    <button className={align === 'right' ? 'account-trigger' : 'workspace-trigger'} ref={button} aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true) } }}>{trigger}</button>
    {open && <div className="ww-menu" role="menu" aria-label={label}>{children(close)}</div>}
  </div>
}

function Avatar({ user, large = false }: { user: Account; large?: boolean }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [user.avatar_url])
  const initials = (user.name || user.username).split(/[\s@._-]+/).filter(Boolean).map(part => part[0]).slice(0, 2).join('').toUpperCase()
  return <span className={'account-photo ' + (large ? 'large' : '')}>{user.avatar_url && !failed ? <img src={user.avatar_url} alt="" width={large ? 64 : 36} height={large ? 64 : 36} referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : initials}</span>
}

export function WorkspaceSwitcher({ company, companies, onChange }: { company: Company; companies: Company[]; onChange: (company: Company) => void }) {
  return <Popover label="Switch workspace" trigger={<><Building2 size={15} /><span>{company.name}</span><ChevronDown size={14} /></>}>
    {close => <><div className="menu-caption">Your workspaces</div>{companies.map(item => <button role="menuitemradio" aria-checked={item.id === company.id} key={item.id} onClick={() => { if (item.id !== company.id) onChange(item); close() }}><span className="workspace-monogram">{item.name.slice(0, 1).toUpperCase()}</span><span className="menu-item-text"><strong>{item.name}</strong><small>{item.id === company.id ? 'Current workspace' : 'Open workspace'}</small></span>{item.id === company.id && <Check size={15} />}</button>)}</>}
  </Popover>
}

export function AccountMenu({ user, company, onNavigate, onSignOut, busy }: { user: Account; company: Company; onNavigate: (screen: string) => void; onSignOut: () => void; busy: boolean }) {
  const [profile, setProfile] = useState(false)
  const closeButton = useRef<HTMLButtonElement>(null)
  const priorFocus = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!profile) return
    priorFocus.current = document.activeElement as HTMLElement
    closeButton.current?.focus()
    return () => priorFocus.current?.focus()
  }, [profile])
  return <>
    <Popover label="Account menu" align="right" trigger={<Avatar user={user} />}>
      {close => <><div className="account-menu-heading"><Avatar user={user} /><div><strong>{user.name || user.username}</strong><small>{user.email || 'Workweave account'}</small></div></div><div className="menu-rule" /><button role="menuitem" onClick={() => { close(); setProfile(true) }}><UserRound size={16} />My profile</button><button role="menuitem" onClick={() => { close(); onNavigate('Settings') }}><Settings2 size={16} />Settings</button><button role="menuitem" onClick={() => { close(); onNavigate('People') }}><Users size={16} />People & workspace access</button><div className="menu-rule" /><button className="menu-signout" role="menuitem" disabled={busy} onClick={() => { close(); onSignOut() }}><LogOut size={16} />Sign out</button></>}
    </Popover>
    {profile && <div className="modal-backdrop" onClick={() => setProfile(false)}><section className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="account-heading" onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') setProfile(false); if (event.key === 'Tab') { event.preventDefault(); closeButton.current?.focus() } }}><button className="icon-button" ref={closeButton} aria-label="Close profile" onClick={() => setProfile(false)}><X size={18} /></button><Avatar user={user} large /><h2 id="account-heading">{user.name || user.username}</h2><p>{user.email || user.username}</p><dl><div><dt>Workspace</dt><dd>{company.name}</dd></div><div><dt>Profile photo</dt><dd>{user.avatar_url ? 'Your email’s Gravatar, when available' : 'Sign in with an email address to use its Gravatar'}</dd></div></dl><small>If no photo is available, we show your initials.</small></section></div>}
  </>
}
