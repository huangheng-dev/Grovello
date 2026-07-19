'use client'

import { Icon } from '@grovello/ui'
import { useTranslations } from 'next-intl'

const layers = [
  ['sharedContext', 'sharedContextBody', 'database', ['sharedTagOne', 'sharedTagTwo', 'sharedTagThree']],
  ['controlPlane', 'controlPlaneBody', 'account_tree', ['controlTagOne', 'controlTagTwo', 'controlTagThree']],
  ['agentPlane', 'agentPlaneBody', 'psychology', ['agentTagOne', 'agentTagTwo', 'agentTagThree']],
  ['connectorPlane', 'connectorPlaneBody', 'extension', ['connectorTagOne', 'connectorTagTwo', 'connectorTagThree']],
  ['outcomePlane', 'outcomePlaneBody', 'monitoring', ['outcomeTagOne', 'outcomeTagTwo', 'outcomeTagThree']],
] as const

export function ArchitectureView() {
  const t = useTranslations('architecture')
  return <div className="page-stack architecture-page">
    <section className="architecture-hero"><span className="eyebrow">{t('eyebrow')}</span><h1>{t('title')}</h1><p>{t('intro')}</p><div className="architecture-tags"><span>Next.js + React</span><span>FastAPI</span><span>Temporal</span><span>LangGraph</span><span>PostgreSQL</span></div></section>
    <section className="positioning-strip" aria-label={t('positioningAria')}>
      <article><span>01</span><div><h2>{t('positionProduct')}</h2><p>{t('positionProductBody')}</p></div></article>
      <Icon name="arrow_forward" size={20} />
      <article><span>02</span><div><h2>{t('positionCapability')}</h2><p>{t('positionCapabilityBody')}</p></div></article>
      <Icon name="arrow_forward" size={20} />
      <article><span>03</span><div><h2>{t('positionJourney')}</h2><p>{t('positionJourneyBody')}</p></div></article>
    </section>
    <section className="architecture-map" aria-label={t('systemAria')}>{layers.map(([title, body, icon, tags], index) => <div className="architecture-layer" key={title}><div className="architecture-layer__number">0{index + 1}</div><span className="architecture-layer__icon"><Icon name={icon} size={24} /></span><div className="architecture-layer__copy"><h2>{t(title)}</h2><p>{t(body)}</p></div><div className="architecture-layer__tags">{tags.map((tag) => <span key={tag}>{t(tag)}</span>)}</div>{index < layers.length - 1 ? <span className="architecture-connector"><Icon name="south" size={20} /></span> : null}</div>)}</section>
    <section className="panel"><div className="panel-heading"><div><h2>{t('rules')}</h2><p>{t('rulesBody')}</p></div><span className="architecture-version">{t('version')}</span></div><div className="rules-grid">{[t('ruleOne'),t('ruleTwo'),t('ruleThree'),t('ruleFour')].map((rule, index) => <article key={rule}><span>0{index + 1}</span><p>{rule}</p></article>)}</div></section>
  </div>
}
