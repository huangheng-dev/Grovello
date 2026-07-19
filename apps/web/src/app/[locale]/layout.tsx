import type { Metadata } from 'next'
import { hasLocale, NextIntlClientProvider } from 'next-intl'
import { getMessages, setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'
import type { ReactNode } from 'react'
import 'material-symbols/outlined.css'
import '../globals.css'
import { routing } from '@/i18n/routing'

const descriptions = {
  en: 'Open-source, multi-agent Growth OS for global go-to-market and revenue orchestration.',
  'zh-CN': '面向全球市场拓展与营收增长的开源多智能体企业增长操作系统。',
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params
  const normalizedLocale = hasLocale(routing.locales, locale) ? locale : routing.defaultLocale
  return {
    title: { default: 'Grovello', template: '%s · Grovello' },
    description: descriptions[normalizedLocale],
  }
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params
  if (!hasLocale(routing.locales, locale)) notFound()
  setRequestLocale(locale)
  const messages = await getMessages()

  return (
    <html lang={locale} suppressHydrationWarning>
      <body>
        <NextIntlClientProvider messages={messages}>{children}</NextIntlClientProvider>
      </body>
    </html>
  )
}
