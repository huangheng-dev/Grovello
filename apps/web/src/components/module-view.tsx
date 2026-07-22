import { sharedObjectsBySection, type NavigationItem } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import { useTranslations } from 'next-intl'

type LocatedNavigationItem = NavigationItem & { sectionKey: string; sectionSlug: string }

const statusTone = {
  active: 'positive',
  foundation: 'warning',
  reserved: 'neutral',
} as const

export function ModuleView({ item }: { item: LocatedNavigationItem }) {
  const t = useTranslations()
  const objects = sharedObjectsBySection[item.sectionKey] ?? []

  return <div className="page-stack module-page">
    <section className="module-hero">
      <div>
        <span className="eyebrow">{t(`sections.${item.sectionKey}`)} · {t(`capabilities.status.${item.status}`)}</span>
        <h1>{t(`pages.${item.key}.title`)}</h1>
        <p>{t(`pages.${item.key}.description`)}</p>
      </div>
      <StatusBadge tone={statusTone[item.status]}>{t(`capabilities.status.${item.status}`)}</StatusBadge>
    </section>

    <section className="readiness-grid">
      <Readiness icon="data_object" tone="positive" title={t('capabilities.domainContract')} body={t('capabilities.domainContractBody')} status={t('capabilities.defined')} />
      <Readiness icon="construction" tone="warning" title={t('capabilities.deliveryStage')} body={t('capabilities.deliveryStageBody', { phase: item.phase })} status={t(`capabilities.status.${item.status}`)} />
      <Readiness icon="verified_user" tone="neutral" title={t('capabilities.accessBoundary')} body={t('capabilities.accessBoundaryBody', { audience: t(`capabilities.audience.${item.audience}`) })} status={t(`capabilities.audience.${item.audience}`)} />
    </section>

    <div className="capability-boundary">
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('capabilities.currentBoundary')}</h2><p>{t('capabilities.currentBoundaryIntro')}</p></div></div>
        <p className="capability-boundary__copy">{t('capabilities.foundationBoundary')}</p>
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>{t('module.sharedObjects')}</h2><p>{t('module.sharedObjectsDescription')}</p></div></div>
        <div className="object-cloud">{objects.map((object) => <span key={object}><Icon name="data_object" size={17} />{object}</span>)}</div>
      </section>
    </div>
  </div>
}

function Readiness({ icon, tone, title, body, status }: { icon: string; tone: 'positive' | 'warning' | 'neutral'; title: string; body: string; status: string }) {
  return <article className={`readiness-card readiness-card--${tone}`}><div><span><Icon name={icon} size={21} /></span><StatusBadge tone={tone}>{status}</StatusBadge></div><h3>{title}</h3><p>{body}</p></article>
}
