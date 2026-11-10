'use client'

import { Check, ChevronDown, CircleAlert, Clock3, Database, FileText, HelpCircle, MoreHorizontal, Play, Search, Sparkles, TrendingDown } from 'lucide-react'

const steps = [
  { number: '01', title: 'Compare periods', detail: 'Q2 2024 vs Q1 2024 · Net revenue', status: 'complete' },
  { number: '02', title: 'Break down by product', detail: 'Identifying segments with the largest change', status: 'complete' },
  { number: '03', title: 'Check regional changes', detail: 'Comparing performance across 5 regions', status: 'complete' },
  { number: '04', title: 'Validate contributing factors', detail: 'Reviewing discounting and churn signals', status: 'attention' },
]

function StatusIcon({ status }: { status: string }) {
  if (status === 'complete') return <span className="status-icon complete"><Check size={13} strokeWidth={3} /></span>
  if (status === 'attention') return <span className="status-icon attention"><CircleAlert size={14} /></span>
  return <span className="status-icon pending"><Clock3 size={14} /></span>
}

function InvestigationSteps() {
  return (
    <div className="steps-list">
      {steps.map((step) => (
        <div className="step-row" key={step.number}>
          <div className="step-index">{step.number}</div>
          <StatusIcon status={step.status} />
          <div className="step-copy"><strong>{step.title}</strong><span>{step.detail}</span></div>
          {step.status === 'attention' && <span className="step-note">Partial evidence</span>}
        </div>
      ))}
    </div>
  )
}

function RevenueChart() {
  return (
    <div className="chart-wrap" aria-label="Bar chart comparing quarterly net revenue">
      <div className="chart-legend"><span><i className="legend-dot q1" />Q1 2024</span><span><i className="legend-dot q2" />Q2 2024</span></div>
      <div className="chart-area">
        <div className="y-axis"><span>$4.0M</span><span>$3.0M</span><span>$2.0M</span><span>$1.0M</span><span>$0</span></div>
        <div className="bars-area">
          <div className="gridline g1" /><div className="gridline g2" /><div className="gridline g3" /><div className="gridline g4" />
          <div className="bar-group"><div className="bar q1-bar" style={{ height: '87%' }} /><div className="bar q2-bar" style={{ height: '70%' }} /><small>Net revenue</small></div>
        </div>
      </div>
      <div className="chart-values"><span>$3.42M</span><span>$2.76M</span></div>
    </div>
  )
}

export function RevenueInvestigation() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><Sparkles size={14} /></span><span>Revenue Intelligence</span><span className="slash">/</span><span className="muted">Investigation</span></div>
        <div className="top-actions"><span className="saved"><span className="saved-dot" />UI preview</span><button className="icon-button" aria-label="More options"><MoreHorizontal size={18} /></button><div className="avatar" aria-label="Analyst profile">AW</div></div>
      </header>

      <div className="workspace">
        <div className="workspace-heading">
          <div><p className="eyebrow">SAMPLE INVESTIGATION  /  PREVIEW</p><h1>Revenue Investigation</h1><p className="lede">Ask a question about your revenue data and review the evidence behind the answer.</p></div>
          <button className="share-button"><FileText size={15} /> Export brief</button>
        </div>

        <section className="question-section" aria-labelledby="question-title">
          <div className="section-label"><span className="label-number">01</span><div><h2 id="question-title">Question</h2><p>What would you like to understand?</p></div></div>
          <div className="question-card"><div className="question-icon"><Search size={18} /></div><p>Why did net revenue decline in Q2 compared with Q1?</p><button className="question-menu" aria-label="Question options"><MoreHorizontal size={18} /></button></div>
          <div className="question-meta"><span><Database size={13} /> Sample dataset</span><span className="meta-divider" /><span>Illustrative preview content</span></div>
        </section>

        <div className="content-grid">
          <section className="investigation-section" aria-labelledby="investigation-title">
            <div className="section-label"><span className="label-number">02</span><div><h2 id="investigation-title">Investigation</h2><p>How we looked into it</p></div><span className="complete-pill"><Check size={12} /> Preview</span></div>
            <div className="panel investigation-panel"><div className="panel-top"><span className="panel-caption"><Play size={12} fill="currentColor" /> Example investigation path</span><span className="duration">Static preview</span></div><InvestigationSteps /><div className="query-detail"><div className="query-top"><span><Database size={13} /> Example data check</span><span className="query-state">Illustrative</span></div><code>net_revenue(q2) - net_revenue(q1) grouped by product, region</code></div></div>
          </section>

          <section className="findings-section" aria-labelledby="findings-title">
            <div className="section-label"><span className="label-number">03</span><div><h2 id="findings-title">Findings</h2><p>Illustrative preview — values are sample content</p></div></div>
            <div className="panel findings-panel"><div className="finding-head"><div><span className="finding-kicker"><TrendingDown size={14} /> Example finding</span><h3>Net revenue fell <strong>19.3%</strong></h3><p>from <b>$3.42M</b> in Q1 to <b>$2.76M</b> in Q2</p></div><span className="confidence">Sample values</span></div><RevenueChart /><div className="divider" /><div className="contributors"><div className="contributors-title">Example contributors <HelpCircle size={14} /></div><div className="contributor-row"><span className="rank">01</span><span className="contributor-name">Enterprise plan</span><span className="contributor-detail">−$382k <em>· 58% of decline</em></span><span className="contributor-bar"><i style={{ width: '82%' }} /></span></div><div className="contributor-row"><span className="rank">02</span><span className="contributor-name">North America</span><span className="contributor-detail">−$241k <em>· 36% of decline</em></span><span className="contributor-bar"><i style={{ width: '52%' }} /></span></div><div className="contributor-row"><span className="rank">03</span><span className="contributor-name">Discounting</span><span className="contributor-detail">−$96k <em>· 14% of decline</em></span><span className="contributor-bar"><i style={{ width: '25%' }} /></span></div></div><div className="caveat"><CircleAlert size={15} /><span><strong>Interpretation note:</strong> This preview uses invented sample values. A future report should distinguish observed contributors from proven causes.</span></div></div>
          </section>
        </div>
      </div>
    </main>
  )
}

export default RevenueInvestigation
        
