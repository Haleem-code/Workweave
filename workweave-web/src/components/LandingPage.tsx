'use client'

import React from 'react'
import {
  ArrowRight,
  Sparkles,
  Building2,
  Database,
  Layers,
  Shield,
  Workflow,
  FileSpreadsheet,
  FileText,
  Activity,
  Users,
  ChevronRight,
  CheckCircle2,
  Lock,
  Cpu
} from 'lucide-react'
import { Interactive3DAnimation } from './Interactive3DAnimation'

interface LandingPageProps {
  onGetStarted: () => void
  onSignIn: () => void
  onGoogleAuth: () => void
  googleAuthBusy: boolean
}

export function LandingPage({
  onGetStarted,
  onSignIn,
  onGoogleAuth,
  googleAuthBusy
}: LandingPageProps) {
  return (
    <div className="landing-container">
      {/* Navigation Topbar */}
      <header className="landing-nav">
        <div className="landing-brand">
          <span className="landing-brand-title">Workweave</span>
          <span className="landing-cluster-pill">
            <span className="live-dot" />
            Cluster us-east-1 · FalkorDB
          </span>
        </div>

        <nav className="landing-links">
          <a href="#overview">Overview</a>
          <a href="#architecture">Architecture</a>
          <a href="#workflows">Workflows</a>
          <a href="#security">Enclave</a>
        </nav>

        <div className="landing-actions">
          <button type="button" className="landing-signin-btn" onClick={onSignIn}>
            Sign in
          </button>
          <button type="button" className="landing-cta-pill" onClick={onGetStarted}>
            Get started <ArrowRight size={14} />
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="landing-hero" id="overview">
        <div className="hero-badge">
          <Sparkles size={13} />
          <span>Autonomous Operational Graph · FalkorDB Enclave</span>
        </div>

        <h1 className="hero-title">
          Turn company knowledge<br />into coordinated work.
        </h1>

        <p className="hero-subtitle">
          Workweave connects your spreadsheets, SOP documents, and teams into an active graph
          that investigates operational disruptions, explains affected commitments, and creates accountable review tasks.
        </p>

        <div className="hero-cta-group">
          <button type="button" className="hero-primary-pill" onClick={onGetStarted}>
            Get started free <ArrowRight size={15} />
          </button>

          <button
            type="button"
            className="hero-google-pill"
            disabled={googleAuthBusy}
            onClick={onGoogleAuth}
          >
            <svg width="16" height="16" viewBox="0 0 24 24">
              <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            <span>{googleAuthBusy ? 'Connecting to Google…' : 'Continue with Google'}</span>
          </button>

          <button type="button" className="hero-secondary-pill" onClick={onSignIn}>
            Sign in to workspace
          </button>
        </div>

        <div className="hero-trust-bar">
          <div className="trust-item">
            <CheckCircle2 size={14} />
            <span>Human confirmation required</span>
          </div>
          <div className="trust-item">
            <Lock size={14} />
            <span>Audit-locked graph enclave</span>
          </div>
          <div className="trust-item">
            <Cpu size={14} />
            <span>Multi-hop grounded reasoning</span>
          </div>
        </div>
      </section>

      {/* Interactive 3D Architecture Canvas */}
      <section className="landing-canvas-section" id="architecture">
        <div className="section-header">
          <span className="section-eyebrow">Interactive Knowledge Fabric</span>
          <h2>How company information connects in real-time</h2>
          <p>
            Documents connect to teams, dependencies anchor to graph entities, and completed review tasks become organizational memory.
          </p>
        </div>

        <div className="landing-3d-wrapper">
          <Interactive3DAnimation />
        </div>
      </section>

      {/* Operational Models & Capabilities Showcase (xAI Grok Console Style) */}
      <section className="landing-models-section" id="workflows">
        <div className="section-header">
          <span className="section-eyebrow">Operational Engines</span>
          <h2>Specialized agents for coordinated enterprise work</h2>
          <p>Autonomous workflows that investigate disruptions, ground citations, and coordinate human review.</p>
        </div>

        <div className="models-grid">
          {/* Card 1 */}
          <div className="model-card">
            <div className="model-card-top">
              <div>
                <div className="model-title-row">
                  <h3>Supplier Delay Engine</h3>
                  <span className="badge-new">Active SOP</span>
                </div>
                <span className="model-meta">Multi-hop schedule reconciliation</span>
              </div>
            </div>

            <p className="model-desc">
              When a vendor delays delivery, Workweave connects the slip to purchase orders, affected sales commitments, unallocated warehouse stock, and assigned order owners.
            </p>

            <div className="model-tags-row">
              <span className="agent-pill">Tool calling</span>
              <span className="agent-pill">Reasoning</span>
              <span className="agent-pill">Deterministic graph</span>
            </div>

            <div className="model-action-row">
              <button type="button" className="model-btn" onClick={onGetStarted}>
                Explore workflow <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {/* Card 2 */}
          <div className="model-card">
            <div className="model-card-top">
              <div>
                <div className="model-title-row">
                  <h3>Commitment Reconciliation Weaver</h3>
                  <span className="badge-new">Grounded</span>
                </div>
                <span className="model-meta">Continuous fulfillment monitoring</span>
              </div>
            </div>

            <p className="model-desc">
              Cross-references customer contract deadlines against inventory buffers and supplier arrivals to detect fulfillment risks before customer delivery dates are missed.
            </p>

            <div className="model-tags-row">
              <span className="agent-pill">Structured outputs</span>
              <span className="agent-pill">Audit locked</span>
              <span className="agent-pill">Source evidence</span>
            </div>

            <div className="model-action-row">
              <button type="button" className="model-btn" onClick={onGetStarted}>
                Inspect commitments <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {/* Card 3 */}
          <div className="model-card">
            <div className="model-card-top">
              <div>
                <div className="model-title-row">
                  <h3>Procedural Memory Agent</h3>
                  <span className="badge-new">FalkorDB Kernel</span>
                </div>
                <span className="model-meta">Organizational episodic retention</span>
              </div>
            </div>

            <p className="model-desc">
              Retains actual internal task outcomes, human supervisor resolutions, and procedure revisions to provide grounded historical memory for subsequent investigations.
            </p>

            <div className="model-tags-row">
              <span className="agent-pill">Long-term memory</span>
              <span className="agent-pill">Human confirmed</span>
              <span className="agent-pill">Local enclave</span>
            </div>

            <div className="model-action-row">
              <button type="button" className="model-btn" onClick={onGetStarted}>
                Browse memory <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 4-Step Process Section */}
      <section className="landing-steps-section">
        <div className="section-header">
          <span className="section-eyebrow">How It Works</span>
          <h2>From questionnaire to coordinated execution</h2>
          <p>Four transparent steps ensure Workweave understands your company before taking action.</p>
        </div>

        <div className="steps-cards-grid">
          <div className="step-card">
            <div className="step-number-pill">01</div>
            <h4>Answer Company Basics</h4>
            <p>
              Complete a guided 6-step questionnaire covering your business, responsibilities, process flow, dependencies, rules, and recurring operational headaches.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number-pill">02</div>
            <h4>Provide Tailored Documents</h4>
            <p>
              Upload spreadsheets (CSV, Excel), procedures (PDF, Word), or connect Google Drive. Workweave explains what each file helps it understand.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number-pill">03</div>
            <h4>Confirm Company Understanding</h4>
            <p>
              Review an editable operational summary covering workflow, rules, and missing information. You confirm this understanding before activation.
            </p>
          </div>

          <div className="step-card">
            <div className="step-number-pill">04</div>
            <h4>Coordinate Actions & Review Tasks</h4>
            <p>
              When changes occur, agents investigate the impact across your graph, explain why with source evidence, and create internal tasks for responsible owners.
            </p>
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="landing-cta-banner" id="security">
        <div className="cta-banner-content">
          <span className="section-eyebrow">Get Started</span>
          <h2>Ready to weave your company's operational graph?</h2>
          <p>
            Initialize your workspace in minutes. Connect your documents, confirm your company profile, and activate deterministic investigations.
          </p>

          <div className="cta-banner-buttons">
            <button type="button" className="hero-primary-pill" onClick={onGetStarted}>
              Get started now <ArrowRight size={15} />
            </button>
            <button
              type="button"
              className="hero-google-pill"
              disabled={googleAuthBusy}
              onClick={onGoogleAuth}
            >
              Continue with Google
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-left">
          <div className="landing-brand">
            <span className="landing-brand-title">Workweave</span>
          </div>
          <p>Autonomous knowledge orchestration for modern operations.</p>
        </div>

        <div className="footer-right">
          <div className="footer-meta-pill">
            <span className="live-dot" />
            FalkorDB Graph Enclave · Local-First Security
          </div>
          <p className="copyright">© {new Date().getFullYear()} Workweave. Human confirmation required for all graph actions.</p>
        </div>
      </footer>
    </div>
  )
}
