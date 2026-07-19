import en from '@grovello/i18n/en.json'
import zhCN from '@grovello/i18n/zh-CN.json'
import { hasLocale } from 'next-intl'
import { getRequestConfig } from 'next-intl/server'
import { routing } from './routing'

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale
  return { locale, messages: locale === 'zh-CN' ? zhCN : en }
})
