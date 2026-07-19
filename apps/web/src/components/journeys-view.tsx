'use client'

import { Icon, StatusBadge } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'

const stages = [
  ['domain_add', 'stage1'],
  ['inventory_2', 'stage2'],
  ['public', 'stage3'],
  ['psychology', 'stage4'],
  ['campaign', 'stage5'],
  ['person_search', 'stage6'],
  ['handshake', 'stage7'],
  ['payments', 'stage8'],
  ['loyalty', 'stage9'],
  ['model_training', 'stage10'],
] as const

const rules = ['rule1', 'rule2', 'rule3'] as const
const decisions = [
  ['extension', 'decisionConnectors', 'decisionConnectorsBody'],
  ['license', 'decisionLicense', 'decisionLicenseBody'],
] as const

export function JourneysView() {
  const locale = useLocale()
  const t = useTranslations('journeys')

  return <div className="page-stack journeys-page">
    <section className="journey-hero">
      <div>
        <span className="eyebrow">{t('eyebrow')}</span>
        <h1>{t('title')}</h1>
        <p>{t('intro')}</p>
        <div className="journey-tags"><span>{t('productScope')}</span><span>{t('capability')}</span><span>{t('reference')}</span></div>
      </div>
      <div className="button-row">
        <Link className="button button--secondary" href={`/${locale}/brand/markets`}><Icon name="public" size={19} />{t('configureMarkets')}</Link>
        <Link className="button button--primary" href={`/${locale}/command/plans`}><Icon name="route" size={19} />{t('openPlans')}</Link>
      </div>
    </section>

    <section className="panel">
      <div className="panel-heading"><div><h2>{t('progress')}</h2><p>{t('progressBody')}</p></div><StatusBadge tone="warning">{t('operationalCount')}</StatusBadge></div>
      <div className="journey-stages">{stages.map(([icon, key], index) => <article key={key}>
        <div className="journey-stage__top"><span>{String(index + 1).padStart(2, '0')}</span><Icon name={icon} size={21} /></div>
        <h3>{t(key)}</h3>
        <StatusBadge tone={index < 4 ? 'warning' : 'neutral'}>{index < 4 ? t('foundation') : t('blocked')}</StatusBadge>
      </article>)}</div>
    </section>

    <div className="journey-columns">
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('acceptance')}</h2><p>{t('acceptanceBody')}</p></div><Icon name="verified" size={23} /></div>
        <div className="acceptance-list">{rules.map((rule, index) => <div key={rule}><span><Icon name="check" size={17} /></span><p><strong>0{index + 1}</strong>{t(rule)}</p></div>)}</div>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('decisions')}</h2><p>{t('decisionsBody')}</p></div><StatusBadge tone="warning">{t('openCount')}</StatusBadge></div>
        <div className="decision-list">{decisions.map(([icon, title, body]) => <article key={title}><span><Icon name={icon} size={19} /></span><div><h3>{t(title)}</h3><p>{t(body)}</p></div><Icon name="chevron_right" size={19} /></article>)}</div>
      </section>
    </div>
  </div>
}
