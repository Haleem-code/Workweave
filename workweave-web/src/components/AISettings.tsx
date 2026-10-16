import { useState } from 'react'
import { api, ProviderSettings } from '../api'

interface Props {
  settings: ProviderSettings
  onChange: (settings: ProviderSettings) => void
  onNotice: (message: string) => void
  perform: (action: () => Promise<void>) => Promise<void>
  base: string
  busy: boolean
  platformAdmin: boolean
}

export function AISettings({ settings, onChange, onNotice, perform, base, busy, platformAdmin }: Props) {
  const [customSelected, setCustomSelected] = useState(false)
  const policy = settings.policy
  const defaultProviders = ['ollama_cloud', 'groq', 'gemini', 'ollama']
  const mode = customSelected ? 'custom' : policy.local_only && !policy.cloud_consent ? 'local' : policy.cloud_consent && !policy.local_only && policy.allowed.length === defaultProviders.length && defaultProviders.every(id => policy.allowed.includes(id)) ? 'cloud' : 'custom'
  const choose = (value: string) => {
    setCustomSelected(value === 'custom')
    onChange({ ...settings, policy: value === 'cloud'
      ? { allowed: defaultProviders, cloud_consent: true, local_only: false }
      : value === 'local'
      ? { allowed: ['ollama'], cloud_consent: false, local_only: true }
      : { ...policy, local_only: false } })
  }
  const cloud = settings.providers.find(p => p.id === 'ollama_cloud')
  return <>
    <section className="panel settings-section">
      <h2>AI answers</h2>
      <p>Choose where questions and relevant document excerpts are processed.</p>
      <fieldset className="ai-processing-options" disabled={busy}>
        <legend className="sr-only">Answer processing</legend>
        {[
          { id: 'cloud', title: 'Ollama Cloud', text: 'Production default. Ollama Cloud first, with configured providers as fallbacks.' },
          { id: 'local', title: 'Self-hosted Ollama', text: 'Uses your configured Ollama server for answers. Cloud answer providers are excluded.' },
          { id: 'custom', title: 'Custom providers', text: 'Choose permitted providers and cloud-processing preferences yourself.' },
        ].map(option => <label className={'ai-processing-option ' + (mode === option.id ? 'selected' : '')} key={option.id}>
          <input type="radio" name="answer-processing" value={option.id} checked={mode === option.id} onChange={() => choose(option.id)} />
          <span><strong>{option.title}</strong><small>{option.text}</small></span>
        </label>)}
      </fieldset>
      {mode === 'cloud' && <p className="ai-processing-note">{cloud?.ready ? 'An Ollama Cloud key is configured.' : 'An Ollama Cloud key is needed to use the primary provider.'} Answers try Ollama Cloud → Groq → Gemini → self-hosted Ollama. Only configured providers are used. Enabled cloud providers receive the question and relevant excerpts; Gemini free-tier inputs may be used to improve Google products.</p>}
      {mode === 'custom' && <div className="ai-custom-options">
        <label className="toggle-label"><input type="checkbox" checked={policy.cloud_consent} disabled={busy} onChange={e => onChange({ ...settings, policy: { ...policy, cloud_consent: e.target.checked, local_only: false } })} /><span>Allow selected company context to be processed by enabled cloud providers</span></label>
        <p className="muted small">Only enabled providers are tried, in this order: Ollama Cloud, Groq, Gemini, self-hosted Ollama. Cloud providers are skipped when cloud processing is off.</p>
        {policy.allowed.includes('gemini') && <p className="muted small">Gemini free-tier inputs may be used to improve Google's products. Check your provider's data terms before allowing company context.</p>}
        {settings.providers.map(provider => <label className="toggle-label" key={provider.id}><input type="checkbox" disabled={busy} checked={policy.allowed.includes(provider.id)} onChange={e => onChange({ ...settings, policy: { ...policy, local_only: false, allowed: e.target.checked ? [...policy.allowed, provider.id] : policy.allowed.filter(id => id !== provider.id) } })} /><span>{provider.label || provider.id}</span></label>)}
      </div>}
      <button className="primary" disabled={busy} onClick={() => { void perform(async () => {
        await api(base + '/providers/policy', 'PUT', policy)
        onChange(await api<ProviderSettings>(base + '/providers'))
        onNotice('AI preferences saved.')
      }) }}>Save preferences</button>
      <p className="ai-processing-note">Document search still uses your separate embedding service. This choice changes the answer provider.</p>
    </section>
    <section className="panel settings-section">
      <h2>Provider connections</h2>
      <p>Connection details are managed by the platform administrator.</p>
      {settings.providers.map(provider => <div className="provider-row" key={provider.id}>
        <div>
          <h3>{provider.label || provider.id} <span className="badge">{provider.disabled ? 'authentication failed' : provider.ready ? 'configured' : 'needs setup'}</span></h3>
          <span className="muted">{provider.model} · {provider.destination}</span>
          {provider.configuration_warning && <p className="ai-processing-note" role="status">{provider.configuration_warning}</p>}
        </div>
        {provider.id !== 'ollama' && platformAdmin && <form onSubmit={e => {
          e.preventDefault()
          const form = e.currentTarget
          const key = new FormData(form).get('key')
          void perform(async () => {
            await api(base + '/providers/' + provider.id + '/key', 'PUT', { key })
            form.reset()
            onChange(await api<ProviderSettings>(base + '/providers'))
            onNotice('API key saved.')
          })
        }}><input name="key" type="password" aria-label={(provider.label || provider.id) + ' API key'} placeholder="Paste API key" autoComplete="off" required /><button className="secondary" disabled={busy}>Save key</button></form>}
      </div>)}
    </section>
  </>
}
