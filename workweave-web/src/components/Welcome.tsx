'use client'

import { ArrowRight, ArrowUpRight, Check, GitBranch, FileText, Users, RotateCcw } from 'lucide-react'

export function WeaveMark() {
  return <svg className="weave-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M6 4v14c0 6 4 10 10 10M16 4v24M26 4v14c0 6-4 10-10 10M4 9h24M4 16h24M7 23h18" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" /></svg>
}

export function Welcome({ onGetStarted, onSignIn }: { onGetStarted: () => void; onSignIn: () => void }) {
  return <main className="ww-landing">
    <header className="ww-site-header"><a className="ww-wordmark" href="#"><WeaveMark />Workweave<span className="wordmark-period">.</span></a><nav aria-label="Website navigation"><a href="#how-it-works">How it works</a><button className="text-button" onClick={onSignIn}>Sign in</button><button className="primary" onClick={onGetStarted}>Create workspace <ArrowUpRight size={15} /></button></nav></header>
    <section className="ww-hero">
      <div className="ww-hero-copy"><span className="ww-kicker"><span /> Company knowledge, connected</span><h1>Know what changed.<br /><em>Find the next move.</em></h1><p>Your documents hold the details. Workweave connects them to the people, commitments, and decisions that keep your company moving.</p><div className="ww-hero-actions"><button className="primary" onClick={onGetStarted}>Start with your company <ArrowRight size={17} /></button><button className="text-button" onClick={onSignIn}>Open your workspace <ArrowUpRight size={15} /></button></div><div className="ww-hero-note"><Check size={14} /> Your sources. Clear evidence. People in control.</div></div>
      <div className="ww-workflow-art" aria-label="Workflow illustration: changes connect to commitments, responsible teams, and remembered outcomes">
        <div className="ww-art-caption"><span>A connected workflow</span><span>01 — 04</span></div>
        <svg className="ww-thread" viewBox="0 0 400 470" fill="none" aria-hidden="true"><path d="M62 65C62 170 336 120 336 224C336 334 62 280 62 384" stroke="currentColor" strokeWidth="1.5" /><path d="M74 65C74 164 324 128 324 224C324 326 74 288 74 384" stroke="currentColor" strokeWidth="1.5" opacity=".25" /></svg>
        {[{ Icon: FileText, className: 'node-source', number: '01 / THE SIGNAL', title: 'Something changed.', text: 'A new source version starts the investigation.' }, { Icon: GitBranch, className: 'node-impact', number: '02 / THE CONNECTION', title: 'Follow the impact.', text: 'Find the commitments that depend on it.' }, { Icon: Users, className: 'node-owner', number: '03 / THE NEXT MOVE', title: 'Put work in the right hands.', text: 'Review the evidence. Resolve the task.' }, { Icon: RotateCcw, className: 'node-memory', number: '04 / THE MEMORY', title: 'Carry the context forward.', text: 'Keep the decision and its actual outcome.' }].map(({ Icon, className, number, title, text }) => <div className={'ww-art-node ' + className} key={className}><span className="ww-node-icon"><Icon size={19} /></span><div><small>{number}</small><strong>{title}</strong><p>{text}</p></div></div>)}
        <span className="ww-art-footnote">A workflow illustration, not live company data</span>
      </div>
    </section>
    <div className="ww-principle-strip"><span>Built around the way work connects.</span><div><span>Source → Evidence</span><span>Dependency → Impact</span><span>Owner → Action</span></div></div>
    <section className="ww-method" id="how-it-works"><div className="ww-section-intro"><span className="ww-kicker">From information to understanding</span><h2>A little context.<br /><em>A clearer company.</em></h2></div><div className="ww-method-list">{[['01', 'Bring what you already have.', 'Start with a spreadsheet, a company guide, or a procedure. Preview what was parsed and confirm what each column means.'], ['02', 'See the connections that matter.', 'Trace supported dependencies, inspect the source behind a finding, and identify the current team responsible.'], ['03', 'Make the next step accountable.', 'Create review tasks from findings and keep the investigation, its evidence, and the recorded outcome together.']].map(([number, title, text]) => <article key={number}><span>{number}</span><div><h3>{title}</h3><p>{text}</p></div></article>)}</div></section>
    <section className="ww-final-cta"><div><span className="ww-kicker">Begin with one useful workflow</span><h2>Your company has a story.<br /><em>Give the work its context.</em></h2></div><button className="primary" onClick={onGetStarted}>Create your workspace <ArrowUpRight size={18} /></button></section>
    <footer className="ww-site-footer"><span className="ww-wordmark"><WeaveMark />Workweave.</span><span>Connected knowledge. Accountable work.</span><span>Powered by FalkorDB</span></footer>
  </main>
}
