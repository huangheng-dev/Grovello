import { isNavigationItemRoutable, type NavigationSection } from '@grovello/product-config'
import { Icon, StatusBadge } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'

const statusTone = {
  active: 'positive',
  foundation: 'warning',
  reserved: 'neutral',
} as const

export function DomainOverview({ section }: { section: NavigationSection }) {
  const locale = useLocale()
  const t = useTranslations()
  const counts = section.items.reduce((result, item) => ({ ...result, [item.status]: result[item.status] + 1 }), { active: 0, foundation: 0, reserved: 0 })

  return <div className="page-stack">
    <section className="module-hero">
      <div>
        <span className="eyebrow">{t('capabilities.capabilityMap')}</span>
        <h1>{t(`sections.${section.key}`)}</h1>
        <p>{t(`sectionDescriptions.${section.key}`)}</p>
      </div>
    </section>

    <section className="capability-summary" aria-label={t('capabilities.deliverySummary')}>
      <Summary icon="check_circle" count={counts.active} label={t('capabilities.status.active')} />
      <Summary icon="construction" count={counts.foundation} label={t('capabilities.status.foundation')} />
      <Summary icon="event_upcoming" count={counts.reserved} label={t('capabilities.status.reserved')} />
    </section>

    <section className="panel">
      <div className="panel-heading"><div><h2>{t('capabilities.capabilitiesTitle')}</h2><p>{t('capabilities.capabilitiesIntro')}</p></div></div>
      <div className="capability-map">
        {section.items.map((item) => {
          const content = <>
            <div className="capability-card__heading">
              <div className="capability-card__identity"><span><Icon name={item.icon} size={19} /></span><h2>{t(`pages.${item.key}.title`)}</h2></div>
              <StatusBadge tone={statusTone[item.status]}>{t(`capabilities.status.${item.status}`)}</StatusBadge>
            </div>
            <p>{t(`pages.${item.key}.description`)}</p>
            <footer><span><Icon name="calendar_today" size={14} />{t('capabilities.phase', { phase: item.phase })}</span><span><Icon name="person" size={14} />{t(`capabilities.audience.${item.audience}`)}</span></footer>
          </>
          return isNavigationItemRoutable(item)
            ? <Link className="capability-card capability-card--link" href={`/${locale}/${section.slug}/${item.slug}`} key={item.key}>{content}</Link>
            : <article className="capability-card" key={item.key}>{content}</article>
        })}
      </div>
    </section>
  </div>
}

function Summary({ icon, count, label }: { icon: string; count: number; label: string }) {
  return <article><span><Icon name={icon} size={20} /></span><div><strong>{count}</strong><small>{label}</small></div></article>
}
