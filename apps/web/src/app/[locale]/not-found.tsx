import { Icon } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'

export default function NotFound() {
  const locale = useLocale()
  const t = useTranslations('notFound')
  return <main className="standalone-state"><span className="state-icon"><Icon name="explore_off" size={30} /></span><h1>{t('title')}</h1><p>{t('body')}</p><Link className="button button--primary" href={`/${locale}/command/dashboard`}>{t('action')}</Link></main>
}
