'use client'

import { Icon, StatusBadge } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import { deliveryStageCounts, deliveryStages, type DeliveryStageStatus } from './delivery-roadmap-model'

const statusTone: Record<DeliveryStageStatus, 'positive' | 'warning' | 'info' | 'neutral'> = {
  verified: 'positive',
  inProgress: 'warning',
  current: 'info',
  planned: 'neutral',
}

export function DeliveryRoadmapView() {
  const locale = useLocale()
  const t = useTranslations('deliveryRoadmap')
  const counts = deliveryStageCounts()

  return <div className="page-stack delivery-roadmap-page">
    <section className="journey-hero delivery-roadmap-hero">
      <div>
        <span className="eyebrow">{t('eyebrow')}</span>
        <h1>{t('title')}</h1>
        <p>{t('intro')}</p>
        <div className="journey-tags"><span>{t('totalTag')}</span><span>{t('verifiedTag')}</span><span>{t('currentTag')}</span></div>
      </div>
      <div className="button-row">
        <Link className="button button--secondary" href={`/${locale}/command/journeys`}><Icon name="conversion_path" size={19} />{t('businessJourney')}</Link>
        <Link className="button button--primary" href={`/${locale}/brand`}><Icon name="database" size={19} />{t('openCurrentPhase')}</Link>
      </div>
    </section>

    <section className="roadmap-summary" aria-label={t('summaryLabel')}>
      <RoadmapSummary icon="format_list_numbered" value={deliveryStages.length} label={t('totalStages')} />
      <RoadmapSummary icon="verified" value={counts.verified} label={t('verifiedGates')} tone="positive" />
      <RoadmapSummary icon="construction" value={counts.inProgress + counts.current} label={t('buildingStages')} tone="warning" />
      <RoadmapSummary icon="event_upcoming" value={counts.planned} label={t('plannedStages')} />
    </section>

    <section className="panel roadmap-sequence-panel">
      <div className="panel-heading"><div><h2>{t('sequenceTitle')}</h2><p>{t('sequenceBody')}</p></div><StatusBadge tone="info">{t('gateProgress')}</StatusBadge></div>
      <nav className="roadmap-track" aria-label={t('sequenceLabel')}>
        {deliveryStages.map((stage) => <a className={`roadmap-node roadmap-node--${stage.status}`} href={`#delivery-phase-${stage.phase}`} key={stage.phase} aria-label={t('phaseLabel', { phase: stage.phase })}>
          <span>{stage.phase}</span><Icon name={stage.icon} size={17} />
        </a>)}
      </nav>
    </section>

    <section className="roadmap-boundary">
      <article><span><Icon name="verified" size={20} /></span><div><small>{t('verifiedBoundaryLabel')}</small><strong>{t('verifiedBoundary')}</strong><p>{t('verifiedBoundaryBody')}</p></div></article>
      <article><span><Icon name="lock_open" size={20} /></span><div><small>{t('earliestGateLabel')}</small><strong>{t('earliestGate')}</strong><p>{t('earliestGateBody')}</p></div></article>
      <article className="roadmap-boundary--current"><span><Icon name="my_location" size={20} /></span><div><small>{t('currentFocusLabel')}</small><strong>{t('currentFocus')}</strong><p>{t('currentFocusBody')}</p></div></article>
    </section>

    <section className="panel">
      <div className="panel-heading"><div><h2>{t('stagesTitle')}</h2><p>{t('stagesBody')}</p></div></div>
      <div className="roadmap-stage-list">
        {deliveryStages.map((stage) => <details className={`roadmap-stage roadmap-stage--${stage.status}`} id={`delivery-phase-${stage.phase}`} open={stage.status === 'current'} key={stage.phase}>
          <summary>
            <span className="roadmap-stage__phase"><Icon name={stage.icon} size={20} /><b>{String(stage.phase).padStart(2, '0')}</b></span>
            <span className="roadmap-stage__identity"><strong>{t(`stages.${stage.phase}.title`)}</strong><small>{t(`stages.${stage.phase}.outcome`)}</small></span>
            <StatusBadge tone={statusTone[stage.status]}>{t(`statuses.${stage.status}`)}</StatusBadge>
            <Icon name="expand_more" size={20} />
          </summary>
          <div className="roadmap-stage__body">
            <div><span><Icon name="inventory_2" size={17} />{t('deliverablesLabel')}</span><p>{t(`stages.${stage.phase}.deliverables`)}</p></div>
            <div><span><Icon name="door_open" size={17} />{t('gateLabel')}</span><p>{t(`stages.${stage.phase}.gate`)}</p></div>
            <footer><Icon name="account_tree" size={16} />{stage.phase === 0 ? t('dependencyNone') : t('dependencyPhase', { phase: stage.phase - 1 })}</footer>
          </div>
        </details>)}
      </div>
    </section>

    <section className="roadmap-principle" role="note"><Icon name="gavel" size={22} /><div><strong>{t('principleTitle')}</strong><p>{t('principleBody')}</p></div></section>
  </div>
}

function RoadmapSummary({ icon, value, label, tone = 'neutral' }: { icon: string; value: number; label: string; tone?: 'neutral' | 'positive' | 'warning' }) {
  return <article className={`roadmap-summary--${tone}`}><span><Icon name={icon} size={20} /></span><div><strong>{value}</strong><small>{label}</small></div></article>
}
