'use client'

import React, { useState } from 'react'
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Sparkles,
  Building2,
  Shield,
  Layers,
  Compass,
  FileSpreadsheet,
  FileText,
  Upload,
  AlertCircle,
  HelpCircle,
  Users,
  Workflow,
  Clock,
  Database,
  CheckCircle2,
  X
} from 'lucide-react'
import { Interactive3DAnimation } from './Interactive3DAnimation'
import { api, Preview, Mapping } from '../api'

interface OnboardingFlowProps {
  onSuccess: (user: { id: string; username: string }) => void
  onSwitchToSignIn: () => void
  onGoogleAuth: () => void
  googleAuthBusy: boolean
}

type OnboardingPhase =
  | 'credentials'
  | 'questionnaire'
  | 'doc_requests'
  | 'mapping_review'
  | 'understanding_review'
  | 'telemetry'

export function OnboardingFlow({
  onSuccess,
  onSwitchToSignIn,
  onGoogleAuth,
  googleAuthBusy
}: OnboardingFlowProps) {
  const [phase, setPhase] = useState<OnboardingPhase>('credentials')
  const [qStep, setQStep] = useState<number>(1) // 1 to 6
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // 1. Account Credentials
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  // 2. Questionnaire Answers (6 Steps)
  // Step 1: Company basics
  const [companyName, setCompanyName] = useState('')
  const [description, setDescription] = useState('')
  const [productsServices, setProductsServices] = useState('')
  const [customers, setCustomers] = useState('')

  // Step 2: People and responsibilities
  const [responsibilities, setResponsibilities] = useState('')
  const [mainTeams, setMainTeams] = useState('Operations, Procurement, Customer Success, Warehouse Logistics')
  const [escalationLead, setEscalationLead] = useState('')

  // Step 3: How work happens
  const [processFlow, setProcessFlow] = useState('')
  const [slaTimelines, setSlaTimelines] = useState('')

  // Step 4: Dependencies and rules
  const [dependenciesRules, setDependenciesRules] = useState('')
  const [procedure, setProcedure] = useState('')
  const [keySuppliers, setKeySuppliers] = useState('')

  // Step 5: Priorities & First Workflow
  const [recurringProblems, setRecurringProblems] = useState('Supplier delivery slips and unexpected inventory reallocations')
  const [workflowPriority, setWorkflowPriority] = useState<'supplier_delays' | 'inventory_shortages' | 'compliance' | 'custom'>('supplier_delays')

  // Step 6: Existing information
  const [dataSources, setDataSources] = useState('Google Drive, Excel Spreadsheets (.xlsx), PDF Procedures')
  const [systemOfRecord, setSystemOfRecord] = useState('Shared cloud folders and weekly vendor spreadsheet exports')

  // 3. Tailored Document Requests state
  const [docStatuses, setDocStatuses] = useState<{ [key: string]: 'pending' | 'uploaded' | 'template' | 'unavailable' }>({
    purchase_orders: 'pending',
    customer_orders: 'pending',
    warehouse_stock: 'pending',
    delay_procedure: 'pending'
  })
  const [previews, setPreviews] = useState<Preview[]>([])
  const [mappings, setMappings] = useState<Mapping[]>([])

  // 4. Editable Understanding Summary
  const [summaryBusiness, setSummaryBusiness] = useState('')
  const [summaryWorkflow, setSummaryWorkflow] = useState('')
  const [summaryResponsibilities, setSummaryResponsibilities] = useState('')
  const [summaryDependencies, setSummaryDependencies] = useState('')
  const [summaryRules, setSummaryRules] = useState('')
  const [missingInfo, setMissingInfo] = useState<string[]>([])

  // Validation & Navigation handlers
  const handleCredentialsSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim()) {
      setError('Username or email is required')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setPhase('questionnaire')
    setQStep(1)
  }

  // Questionnaire navigation
  const nextQStep = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setError('')
    if (qStep === 1 && !companyName.trim()) {
      setError('Company / Workspace name is required to initialize')
      return
    }
    if (qStep < 6) {
      setQStep(qStep + 1)
    } else {
      // Completed all 6 steps of questionnaire:
      // Synthesize initial editable understanding summary
      buildInitialSummary()
      setPhase('doc_requests')
    }
  }

  const prevQStep = () => {
    setError('')
    if (qStep > 1) {
      setQStep(qStep - 1)
    } else {
      setPhase('credentials')
    }
  }

  const setUnknown = (setter: (val: string) => void) => {
    setter('Information not formalized yet — pending workspace review')
  }

  const buildInitialSummary = () => {
    const bus = description.trim()
      ? description
      : `${companyName} operates in commercial distribution. Offers ${productsServices || 'products and services'} to ${customers || 'commercial accounts'}.`
    setSummaryBusiness(bus)

    const wf = processFlow.trim()
      ? processFlow
      : `Orders are received and reconciled against incoming vendor deliveries. Target SLA: ${slaTimelines || 'Standard fulfillment turnaround'}.`
    setSummaryWorkflow(wf)

    const resp = responsibilities.trim()
      ? responsibilities
      : `Primary teams: ${mainTeams}. Operations manages schedule deviations; Procurement handles vendor disputes; Customer Success coordinates account updates.`
    setSummaryResponsibilities(resp)

    const dep = dependenciesRules.trim()
      ? dependenciesRules
      : `Commitments depend on purchase order deliveries from vendors (${keySuppliers || 'primary suppliers'}) and unallocated warehouse buffer stock.`
    setSummaryDependencies(dep)

    const rls = procedure.trim()
      ? procedure
      : `When a supplier delivery becomes late, investigate affected purchase orders, verify unallocated stock, and generate internal review tasks for order owners.`
    setSummaryRules(rls)

    const gaps: string[] = []
    if (!productsServices.trim() || productsServices.includes('not formalized')) gaps.push('Specific product catalog & SKUs')
    if (!customers.trim() || customers.includes('not formalized')) gaps.push('Customer account commitment registry')
    if (!keySuppliers.trim() || keySuppliers.includes('not formalized')) gaps.push('Vendor contact & lead time matrix')
    if (!slaTimelines.trim()) gaps.push('Explicit SLA breach notification thresholds')
    setMissingInfo(gaps)
  }

  // Sample file templates generator
  const useSampleTemplate = (docKey: string) => {
    setDocStatuses(prev => ({ ...prev, [docKey]: 'template' }))
  }

  const markUnavailable = (docKey: string) => {
    setDocStatuses(prev => ({ ...prev, [docKey]: 'unavailable' }))
    setMissingInfo(prev => [...new Set([...prev, `Document: ${docKey.replace('_', ' ').toUpperCase()}`])])
  }

  // Direct file parser for uploaded documents during onboarding
  const handleDocUpload = async (docKey: string, file: File) => {
    setBusy(true)
    setError('')
    try {
      setDocStatuses(prev => ({ ...prev, [docKey]: 'uploaded' }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // Final confirmation & launch
  const handleFinalActivation = async () => {
    setBusy(true)
    setError('')
    try {
      const fullDescription = `${summaryBusiness}\n\nWorkflow: ${summaryWorkflow}\n\nDependencies: ${summaryDependencies}`
      const fullProcedure = summaryRules

      const result = await api<{ id: string; username: string; company_id: string }>('/auth/signup', 'POST', {
        username: username.trim(),
        password,
        company_name: companyName.trim(),
        industry: 'Distribution & Operations',
        description: fullDescription,
        responsibilities: summaryResponsibilities,
        procedure: fullProcedure,
        workflow_priority: workflowPriority,
        products_services: productsServices,
        customers,
        process_flow: summaryWorkflow,
        dependencies_rules: summaryDependencies,
        data_sources: dataSources,
        missing_information: missingInfo.join(', ')
      })

      onSuccess(result)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="onboarding-modal">
      {/* Top Header */}
      <div className="onboarding-progress-header">
        <div className="onboarding-brand">
          <span className="brand-title">Workweave</span>
          <span className="prototype-label">Workspace Setup</span>
        </div>

        <div className="step-breadcrumbs">
          <div className={`step-pill ${phase === 'credentials' ? 'active' : 'completed'}`}>
            <span>1. Account</span>
          </div>
          <div className={`step-pill ${phase === 'questionnaire' ? 'active' : ['doc_requests', 'mapping_review', 'understanding_review', 'telemetry'].includes(phase) ? 'completed' : ''}`}>
            <span>2. Questionnaire {phase === 'questionnaire' ? `(${qStep}/6)` : ''}</span>
          </div>
          <div className={`step-pill ${phase === 'doc_requests' ? 'active' : ['mapping_review', 'understanding_review', 'telemetry'].includes(phase) ? 'completed' : ''}`}>
            <span>3. Tailored Sources</span>
          </div>
          <div className={`step-pill ${phase === 'understanding_review' ? 'active' : phase === 'telemetry' ? 'completed' : ''}`}>
            <span>4. Company Profile</span>
          </div>
          <div className={`step-pill ${phase === 'telemetry' ? 'active' : ''}`}>
            <span>5. Verification & Launch</span>
          </div>
        </div>

        <button type="button" className="bracket-btn text-button" onClick={onSwitchToSignIn}>
          Sign in instead
        </button>
      </div>

      {error && <div className="alert" role="alert">[ERROR] {error}</div>}

      {/* PHASE 1: OPERATOR CREDENTIALS */}
      {phase === 'credentials' && (
        <div className="onboarding-card">
          <div className="form-header">
            <span className="eyebrow">Phase 1 · Operator Identity</span>
            <h2>Establish your workspace account</h2>
            <p>Create your administrator credentials or continue with Google Single Sign-On.</p>
          </div>

          <div className="oauth-quick-box">
            <button
              type="button"
              className="google-sso-btn"
              disabled={googleAuthBusy}
              onClick={onGoogleAuth}
            >
              <svg width="18" height="18" viewBox="0 0 24 24">
                <path fill="#currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                <path fill="#currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
              </svg>
              <span>{googleAuthBusy ? 'Connecting to Google…' : 'Continue with Google OAuth'}</span>
            </button>
            <div className="divider-line">
              <span>Or create workspace credentials</span>
            </div>
          </div>

          <form onSubmit={handleCredentialsSubmit}>
            <label>
              <span className="field-label">Email or username</span>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                required
                placeholder="operator@company.com"
              />
            </label>
            <div className="two-column-inputs">
              <label>
                <span className="field-label">Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  placeholder="Minimum 6 characters"
                />
              </label>
              <label>
                <span className="field-label">Confirm password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  placeholder="Repeat password"
                />
              </label>
            </div>
            <div className="onboarding-actions">
              <button type="submit" className="primary">
                Proceed to company questionnaire →
              </button>
            </div>
          </form>
        </div>
      )}

      {/* =========================================================================
          PHASE 2: THE 6-STEP QUESTIONNAIRE
          ========================================================================= */}
      {phase === 'questionnaire' && (
        <div className="onboarding-card">
          <div className="questionnaire-header">
            <span className="eyebrow">Questionnaire · Step {qStep} of 6</span>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${(qStep / 6) * 100}%` }} />
            </div>
          </div>

          {/* Step 1: Company Basics */}
          {qStep === 1 && (
            <div className="q-step-content">
              <h2>Company Basics</h2>
              <p>Identify your company, core business operations, products or services, and customer segments.</p>
              <form onSubmit={nextQStep}>
                <label>
                  <span className="field-label">Company or workspace name *</span>
                  <input
                    value={companyName}
                    onChange={e => setCompanyName(e.target.value)}
                    required
                    placeholder="E.G. HARBOR SUPPLY, APEX LOGISTICS, SOLSTICE LABS"
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">What does your company do?</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setDescription)}>I do not know yet</button>
                  </div>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder="We distribute maintenance and packaging supplies to regional commercial accounts..."
                  />
                </label>
                <div className="two-column-inputs">
                  <label>
                    <div className="label-with-skip">
                      <span className="field-label">Products or services</span>
                      <button type="button" className="text-link" onClick={() => setUnknown(setProductsServices)}>Skip</button>
                    </div>
                    <input
                      value={productsServices}
                      onChange={e => setProductsServices(e.target.value)}
                      placeholder="Corrugated cartons, packaging tape, pallet wrap"
                    />
                  </label>
                  <label>
                    <div className="label-with-skip">
                      <span className="field-label">Primary customers</span>
                      <button type="button" className="text-link" onClick={() => setUnknown(setCustomers)}>Skip</button>
                    </div>
                    <input
                      value={customers}
                      onChange={e => setCustomers(e.target.value)}
                      placeholder="Regional logistics fulfillment hubs and local retailers"
                    />
                  </label>
                </div>
                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Next: People & Responsibilities →</button>
                </div>
              </form>
            </div>
          )}

          {/* Step 2: People and Responsibilities */}
          {qStep === 2 && (
            <div className="q-step-content">
              <h2>People & Responsibilities</h2>
              <p>Outline main teams and who handles each part of operational work, investigation, and review.</p>
              <form onSubmit={nextQStep}>
                <label>
                  <span className="field-label">Main teams & departments</span>
                  <input
                    value={mainTeams}
                    onChange={e => setMainTeams(e.target.value)}
                    placeholder="Operations, Procurement, Customer Success, Warehouse Logistics"
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Who handles each part of the work?</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setResponsibilities)}>I do not know yet</button>
                  </div>
                  <textarea
                    rows={4}
                    value={responsibilities}
                    onChange={e => setResponsibilities(e.target.value)}
                    placeholder="Operations investigates late deliveries; Procurement contacts suppliers; Customer Success notifies affected clients; Warehouse team recounts unallocated cartons..."
                  />
                </label>
                <label>
                  <span className="field-label">Lead escalation owner / point of contact (optional)</span>
                  <input
                    value={escalationLead}
                    onChange={e => setEscalationLead(e.target.value)}
                    placeholder="Director of Supply Chain / Lead Order Manager"
                  />
                </label>
                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Next: How work happens →</button>
                </div>
              </form>
            </div>
          )}

          {/* Step 3: How Work Happens */}
          {qStep === 3 && (
            <div className="q-step-content">
              <h2>How Work Happens (Process Flow)</h2>
              <p>Describe the end-to-end lifecycle from receiving an order or request to final delivery and completion.</p>
              <form onSubmit={nextQStep}>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Order-to-completion process flow</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setProcessFlow)}>I do not know yet</button>
                  </div>
                  <textarea
                    rows={4}
                    value={processFlow}
                    onChange={e => setProcessFlow(e.target.value)}
                    placeholder="1. Sales Order received from customer -> 2. PO placed with vendor -> 3. Vendor delivers cartons to warehouse -> 4. Order packed and dispatched..."
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Expected turnaround & SLA commitments</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setSlaTimelines)}>Skip</button>
                  </div>
                  <input
                    value={slaTimelines}
                    onChange={e => setSlaTimelines(e.target.value)}
                    placeholder="Standard delivery within 48 hours of required date"
                  />
                </label>
                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Next: Dependencies & rules →</button>
                </div>
              </form>
            </div>
          )}

          {/* Step 4: Dependencies and Rules */}
          {qStep === 4 && (
            <div className="q-step-content">
              <h2>Dependencies & Rules</h2>
              <p>Suppliers, partners, approval thresholds, deadlines, procedures, and important exceptions.</p>
              <form onSubmit={nextQStep}>
                <label>
                  <span className="field-label">Key suppliers & partners</span>
                  <input
                    value={keySuppliers}
                    onChange={e => setKeySuppliers(e.target.value)}
                    placeholder="Beacon Packaging, Acme Supplies, Freight Express"
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Dependency rules & commitments</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setDependenciesRules)}>I do not know yet</button>
                  </div>
                  <textarea
                    rows={3}
                    value={dependenciesRules}
                    onChange={e => setDependenciesRules(e.target.value)}
                    placeholder="Customer orders depend on purchase orders. If PO arrives after required date, unallocated stock must be verified before delay notification..."
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Approved procedure / SOP guidelines</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setProcedure)}>I do not know yet</button>
                  </div>
                  <textarea
                    rows={3}
                    value={procedure}
                    onChange={e => setProcedure(e.target.value)}
                    placeholder="When a delivery becomes late, investigate affected commitments, check unallocated stock, and create an internal review task for the current order owner."
                  />
                </label>
                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Next: Priorities & workflow →</button>
                </div>
              </form>
            </div>
          )}

          {/* Step 5: Priorities & First Workflow */}
          {qStep === 5 && (
            <div className="q-step-content">
              <h2>Priorities & Target Workflow</h2>
              <p>Identify recurring operational problems and select the first automated workflow to activate.</p>
              <form onSubmit={nextQStep}>
                <label>
                  <span className="field-label">Recurring operational headaches</span>
                  <input
                    value={recurringProblems}
                    onChange={e => setRecurringProblems(e.target.value)}
                    placeholder="Late supplier deliveries, unallocated inventory stockouts, communication delays"
                  />
                </label>

                <div className="workflow-selection">
                  <span className="field-label">Choose first automated workflow</span>
                  <div className="workflow-cards">
                    {[
                      {
                        id: 'supplier_delays',
                        title: 'SUPPLIER DELAYS & COMMITMENT RECONCILIATION',
                        desc: 'Detect supplier slips, traverse purchase orders and sales commitments, compute stock coverage, assign review tasks.',
                        tag: 'AUTOMATED PROTOTYPE READY'
                      },
                      {
                        id: 'inventory_shortages',
                        title: 'INVENTORY & ORDER SHORTAGE INVESTIGATION',
                        desc: 'Track warehouse SKU depletion against required reservation dates and propose proactive reallocations.',
                        tag: 'DATA EXTENSION'
                      },
                      {
                        id: 'compliance',
                        title: 'PROCEDURAL COMPLIANCE & ESCALATION AUDITING',
                        desc: 'Audit execution episodes against versioned company procedures with human confirmation gates.',
                        tag: 'AUDIT MESH'
                      },
                      {
                        id: 'custom',
                        title: 'CUSTOM OPERATIONAL KNOWLEDGE PROBING',
                        desc: 'General deterministic graph indexing across arbitrary business documents and spreadsheets.',
                        tag: 'CUSTOM SCHEMA'
                      }
                    ].map(wf => (
                      <div
                        key={wf.id}
                        className={`wf-option-card ${workflowPriority === wf.id ? 'chosen' : ''}`}
                        onClick={() => setWorkflowPriority(wf.id as any)}
                      >
                        <div className="wf-card-header">
                          <strong>{wf.title}</strong>
                          <span className="pill">[{wf.tag}]</span>
                        </div>
                        <p>{wf.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Next: Existing information →</button>
                </div>
              </form>
            </div>
          )}

          {/* Step 6: Existing Information */}
          {qStep === 6 && (
            <div className="q-step-content">
              <h2>Existing Information & Records</h2>
              <p>Where are your company documents and records currently stored?</p>
              <form onSubmit={nextQStep}>
                <label>
                  <span className="field-label">Data storage channels</span>
                  <input
                    value={dataSources}
                    onChange={e => setDataSources(e.target.value)}
                    placeholder="Google Drive, Excel Spreadsheets (.xlsx), CSV, PDF SOP manuals"
                  />
                </label>
                <label>
                  <div className="label-with-skip">
                    <span className="field-label">Primary system of record / ERP exports</span>
                    <button type="button" className="text-link" onClick={() => setUnknown(setSystemOfRecord)}>Skip</button>
                  </div>
                  <textarea
                    rows={3}
                    value={systemOfRecord}
                    onChange={e => setSystemOfRecord(e.target.value)}
                    placeholder="Weekly CSV export from warehouse ERP, Google Drive shared drive for customer contracts, SOP handbook in PDF..."
                  />
                </label>
                <div className="review-check-banner">
                  <CheckCircle2 size={16} />
                  <span>Questionnaire completed. Click next to generate tailored document requests.</span>
                </div>
                <div className="onboarding-actions-split">
                  <button type="button" className="secondary" onClick={prevQStep}>← Back</button>
                  <button type="submit" className="primary">Generate tailored document requests →</button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          PHASE 3: TAILORED DOCUMENT REQUESTS
          ========================================================================= */}
      {phase === 'doc_requests' && (
        <div className="onboarding-card wide-card">
          <div className="form-header">
            <span className="eyebrow">Phase 3 · Tailored Document Requests</span>
            <h2>Sources for workflow: {workflowPriority.replace('_', ' ')}</h2>
            <p>
              Based on your answers, Workweave requests specific documents to ground its deterministic graph.
              Each request explains what it helps the agent understand. You can upload files, use synthetic templates, or mark documents unavailable.
            </p>
          </div>

          <div className="doc-requests-grid">
            {/* 1. Open Purchase Orders */}
            <div className={`doc-request-card ${docStatuses.purchase_orders}`}>
              <div className="doc-card-top">
                <FileSpreadsheet size={20} />
                <div>
                  <strong>Open Purchase Orders (.xlsx / .csv)</strong>
                  <span className="pill">[{docStatuses.purchase_orders.toUpperCase()}]</span>
                </div>
              </div>
              <p className="doc-explanation">
                <strong>What it helps understand:</strong> Connects incoming supplier shipments, PO numbers, expected arrival dates, and SKU quantities.
              </p>
              <div className="doc-actions">
                <label className="bracket-btn file-upload-btn">
                  Upload file
                  <input
                    type="file"
                    accept=".xlsx,.csv"
                    style={{ display: 'none' }}
                    onChange={e => {
                      if (e.target.files?.[0]) handleDocUpload('purchase_orders', e.target.files[0])
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => useSampleTemplate('purchase_orders')}
                >
                  Use sample template
                </button>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => markUnavailable('purchase_orders')}
                >
                  Mark unavailable
                </button>
              </div>
            </div>

            {/* 2. Customer Commitments / Sales Orders */}
            <div className={`doc-request-card ${docStatuses.customer_orders}`}>
              <div className="doc-card-top">
                <FileSpreadsheet size={20} />
                <div>
                  <strong>Customer Sales Commitments (.xlsx / .csv)</strong>
                  <span className="pill">[{docStatuses.customer_orders.toUpperCase()}]</span>
                </div>
              </div>
              <p className="doc-explanation">
                <strong>What it helps understand:</strong> Maps order deadlines and required dates to detect affected client commitments when supplier delivery dates slip.
              </p>
              <div className="doc-actions">
                <label className="bracket-btn file-upload-btn">
                  Upload file
                  <input
                    type="file"
                    accept=".xlsx,.csv"
                    style={{ display: 'none' }}
                    onChange={e => {
                      if (e.target.files?.[0]) handleDocUpload('customer_orders', e.target.files[0])
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => useSampleTemplate('customer_orders')}
                >
                  Use sample template
                </button>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => markUnavailable('customer_orders')}
                >
                  Mark unavailable
                </button>
              </div>
            </div>

            {/* 3. Available Warehouse Stock */}
            <div className={`doc-request-card ${docStatuses.warehouse_stock}`}>
              <div className="doc-card-top">
                <FileSpreadsheet size={20} />
                <div>
                  <strong>Unallocated Warehouse Stock (.xlsx / .csv)</strong>
                  <span className="pill">[{docStatuses.warehouse_stock.toUpperCase()}]</span>
                </div>
              </div>
              <p className="doc-explanation">
                <strong>What it helps understand:</strong> Computes buffer inventory to see if unallocated units can cover commitments before alerting customer accounts.
              </p>
              <div className="doc-actions">
                <label className="bracket-btn file-upload-btn">
                  Upload file
                  <input
                    type="file"
                    accept=".xlsx,.csv"
                    style={{ display: 'none' }}
                    onChange={e => {
                      if (e.target.files?.[0]) handleDocUpload('warehouse_stock', e.target.files[0])
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => useSampleTemplate('warehouse_stock')}
                >
                  Use sample template
                </button>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => markUnavailable('warehouse_stock')}
                >
                  Mark unavailable
                </button>
              </div>
            </div>

            {/* 4. Delay-Handling Procedure SOP */}
            <div className={`doc-request-card ${docStatuses.delay_procedure}`}>
              <div className="doc-card-top">
                <FileText size={20} />
                <div>
                  <strong>Delay-Handling Procedure (.pdf / .docx / .txt)</strong>
                  <span className="pill">[{docStatuses.delay_procedure.toUpperCase()}]</span>
                </div>
              </div>
              <p className="doc-explanation">
                <strong>What it helps understand:</strong> Approved company guidelines governing task synthesis, ownership assignment, and escalation policies.
              </p>
              <div className="doc-actions">
                <label className="bracket-btn file-upload-btn">
                  Upload file
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    style={{ display: 'none' }}
                    onChange={e => {
                      if (e.target.files?.[0]) handleDocUpload('delay_procedure', e.target.files[0])
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => useSampleTemplate('delay_procedure')}
                >
                  Use default procedure
                </button>
                <button
                  type="button"
                  className="bracket-btn text-button"
                  onClick={() => markUnavailable('delay_procedure')}
                >
                  Mark unavailable
                </button>
              </div>
            </div>
          </div>

          <div className="onboarding-actions-split">
            <button type="button" className="secondary" onClick={() => setPhase('questionnaire')}>
              ← Back to questionnaire
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => setPhase('understanding_review')}
            >
              Proceed to company understanding review →
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          PHASE 4: EDITABLE COMPANY UNDERSTANDING SUMMARY
          ========================================================================= */}
      {phase === 'understanding_review' && (
        <div className="onboarding-card wide-card">
          <div className="form-header">
            <span className="eyebrow">Phase 4 · Understanding Review</span>
            <h2>Confirm Workweave's understanding of {companyName}</h2>
            <p>
              Review and refine the structured profile built from your answers and documents.
              Human confirmation is required before any automated investigation workflows are activated.
            </p>
          </div>

          <div className="understanding-sections-grid">
            <div className="understanding-box">
              <span className="field-label">01. Business Overview</span>
              <textarea
                rows={3}
                value={summaryBusiness}
                onChange={e => setSummaryBusiness(e.target.value)}
              />
            </div>

            <div className="understanding-box">
              <span className="field-label">02. Workflow & SLA Timelines</span>
              <textarea
                rows={3}
                value={summaryWorkflow}
                onChange={e => setSummaryWorkflow(e.target.value)}
              />
            </div>

            <div className="understanding-box">
              <span className="field-label">03. Responsibilities & Team Ownership</span>
              <textarea
                rows={3}
                value={summaryResponsibilities}
                onChange={e => setSummaryResponsibilities(e.target.value)}
              />
            </div>

            <div className="understanding-box">
              <span className="field-label">04. Dependencies & Commitments</span>
              <textarea
                rows={3}
                value={summaryDependencies}
                onChange={e => setSummaryDependencies(e.target.value)}
              />
            </div>

            <div className="understanding-box full-width">
              <span className="field-label">05. Approved Operational Rules & Procedures</span>
              <textarea
                rows={3}
                value={summaryRules}
                onChange={e => setSummaryRules(e.target.value)}
              />
            </div>

            {missingInfo.length > 0 && (
              <div className="missing-info-box full-width">
                <div className="missing-header">
                  <AlertCircle size={15} />
                  <strong>MISSING INFORMATION & GAPS IDENTIFIED:</strong>
                </div>
                <div className="missing-tags">
                  {missingInfo.map(gap => (
                    <span key={gap} className="missing-tag">
                      Gap: {gap}
                    </span>
                  ))}
                </div>
                <small>You can supply missing information anytime after activation from the Company screen.</small>
              </div>
            )}
          </div>

          <div className="onboarding-actions-split">
            <button type="button" className="secondary" onClick={() => setPhase('doc_requests')}>
              ← Back to documents
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => setPhase('telemetry')}
            >
              Confirm understanding & view 3D telemetry →
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          PHASE 5: 3D TELEMETRY & FINAL ACTIVATION
          ========================================================================= */}
      {phase === 'telemetry' && (
        <div className="onboarding-card wide-card">
          <div className="form-header">
            <span className="eyebrow">Phase 5 · System Architecture & Launch</span>
            <h2>How company information connects in Workweave</h2>
            <p>
              Documents connect to teams, dependencies, review tasks, and remembered outcomes.
              The 3D lattice below illustrates the deterministic graph architecture.
            </p>
          </div>

          {/* Interactive 3D Canvas */}
          <Interactive3DAnimation />

          {/* Clean Slate Guarantee Banner */}
          <div className="ready-slate-notice">
            <Shield size={18} />
            <div>
              <strong>Clean slate guarantee & human verification</strong>
              <p>
                Your workspace ({companyName.toUpperCase()}) will activate with a verified understanding.
                Questionnaire answers do not grant autonomous agents external permissions. Internal tasks are synthesized
                for human review with grounded evidence citations.
              </p>
            </div>
          </div>

          <div className="onboarding-actions-split">
            <button type="button" className="secondary" disabled={busy} onClick={() => setPhase('understanding_review')}>
              ← Back to understanding review
            </button>
            <button
              type="button"
              className="primary large-btn"
              disabled={busy}
              onClick={handleFinalActivation}
            >
              <Sparkles size={16} />
              {busy ? 'Initializing workspace…' : 'Initialize & activate workspace →'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
