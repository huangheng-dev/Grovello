'use client'

import { Icon, StatusBadge } from '@grovello/ui'
import { useTranslations } from 'next-intl'

const stages = [
  ['radar', 'stageSignal', '128'], ['target', 'stageStrategy', '6'], ['auto_awesome', 'stageCreate', '84'],
  ['send', 'stageDistribute', '31'], ['person_search', 'stageConvert', '19'], ['payments', 'stageRevenue', '$86k'], ['autorenew', 'stageRetain', '94%'],
] as const

const runs = [
  ['runOne', 'runOneDomain', 'running', '64%'],
  ['runTwo', 'runTwoDomain', 'approval', '42'],
  ['runThree', 'runThreeDomain', 'completed', '18'],
] as const

const performanceRows = [
  ['motionOrganic', '$18,420', '$182,000', '$74,800', '4.1×', 'confidenceHigh'],
  ['motionOutbound', '$22,800', '$236,000', '$86,200', '3.8×', 'confidenceMedium'],
  ['motionPaid', '$41,500', '$198,000', '$92,100', '2.2×', 'confidenceHigh'],
  ['motionExpansion', '$8,600', '$104,000', '$33,320', '3.9×', 'confidenceHigh'],
] as const

export function DashboardView() {
  const t = useTranslations('dashboard')
  return <div className="page-stack">
    <section className="welcome-panel">
      <div><span className="eyebrow">{t('eyebrow')}</span><h1>{t('welcome')}</h1><p>{t('summary')}</p></div>
      <div className="button-row"><button className="button button--secondary"><Icon name="psychology" size={19} />{t('reviewDecisions')}<span className="button-count">2</span></button><button className="button button--primary"><Icon name="add" size={19} />{t('newPlan')}</button></div>
    </section>
    <section className="metrics-grid">
      <Metric icon="payments" label={t('revenue')} value="$286,420" note={`+18.4% ${t('vsPrevious')}`} tone="positive" />
      <Metric icon="conversion_path" label={t('pipeline')} value="$1.24M" note={`63% ${t('targetProgress')}`} />
      <Metric icon="verified" label={t('qualifiedLeads')} value="348" note={`27 ${t('needsReview')}`} tone="warning" />
      <Metric icon="play_circle" label={t('activeRuns')} value="23" note={t('acrossWorkflows')} />
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>{t('growthLoop')}</h2><p>{t('growthLoopDescription')}</p></div><StatusBadge tone="neutral">{t('seedData')}</StatusBadge></div>
      <div className="growth-loop">{stages.map(([icon, name, value], index) => <div className="growth-stage" key={name}><span><Icon name={icon} size={21} /></span><small>{t(name)}</small><strong>{value}</strong>{index < stages.length - 1 ? <Icon className="growth-arrow" name="arrow_forward" size={18} /> : null}</div>)}</div>
    </section>
    <div className="dashboard-columns">
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('aiDecisions')}</h2><p>{t('decisionDescription')}</p></div><button className="text-button">{t('viewAll')} <Icon name="arrow_forward" size={17} /></button></div>
        <Decision icon="travel_explore" title={t('decisionOne')} body={t('decisionOneBody')} impact={t('impactOne')} />
        <Decision icon="bolt" title={t('decisionTwo')} body={t('decisionTwoBody')} impact={t('impactTwo')} />
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('execution')}</h2><p>{t('executionDescription')}</p></div><button className="icon-button" aria-label={t('moreActions')}><Icon name="more_horiz" /></button></div>
        <div className="run-list">{runs.map(([name, domain, status, result]) => <div className="run-row" key={name}><span className={`run-dot run-dot--${status}`} /><div><strong>{t(name)}</strong><small>{t(domain)}</small></div><StatusBadge tone={status === 'completed' ? 'positive' : status === 'approval' ? 'warning' : 'info'}>{t(status)}</StatusBadge><b>{result}{name === 'runTwo' ? ` ${t('accountsUnit')}` : name === 'runThree' ? ` ${t('risksUnit')}` : ''}</b></div>)}</div>
      </section>
    </div>
    <section className="panel">
      <div className="panel-heading"><div><h2>{t('performance')}</h2><p>{t('performanceDescription')}</p></div><div className="segmented-control compact"><button className="active">{t('period30')}</button><button>{t('period90')}</button><button>{t('periodQuarter')}</button></div></div>
      <div className="channel-table table-scroll"><table><thead><tr><th>{t('growthMotion')}</th><th>{t('spend')}</th><th>{t('qualifiedPipeline')}</th><th>{t('revenueColumn')}</th><th>ROI</th><th>{t('confidence')}</th></tr></thead><tbody>{performanceRows.map((row) => <tr key={row[0]}>{row.map((cell, index) => <td key={cell}>{index === 0 ? <strong>{t(cell)}</strong> : index === 5 ? t(cell) : cell}</td>)}</tr>)}</tbody></table></div>
    </section>
  </div>
}

function Metric({ icon, label, value, note, tone = 'default' }: { icon: string; label: string; value: string; note: string; tone?: string }) {
  return <article className="metric-card"><div className="metric-card__top"><span className="metric-icon"><Icon name={icon} size={21} /></span><button className="icon-button"><Icon name="more_horiz" size={20} /></button></div><small>{label}</small><strong>{value}</strong><p className={`metric-note metric-note--${tone}`}>{note}</p></article>
}

function Decision({ icon, title, body, impact }: { icon: string; title: string; body: string; impact: string }) {
  const t = useTranslations('dashboard')
  return <article className="decision-card"><span className="decision-icon"><Icon name={icon} /></span><div className="decision-card__body"><div><StatusBadge tone="info">{t('opportunity')}</StatusBadge><small>{t('evidenceSources')}</small></div><h3>{title}</h3><p>{body}</p><footer><span><small>{t('impact')}</small><strong>{impact}</strong></span><button className="button button--secondary button--small">{t('review')}<Icon name="arrow_forward" size={17} /></button></footer></div></article>
}
