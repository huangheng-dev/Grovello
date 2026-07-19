'use client'

import { Icon } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'

type AuthMode = 'login' | 'register' | 'forgot'

export function AuthForm({ mode }: { mode: AuthMode }) {
  const locale = useLocale()
  const t = useTranslations('auth')
  const pathname = usePathname()
  const router = useRouter()
  const [submitted, setSubmitted] = useState(false)
  const [passwordVisible, setPasswordVisible] = useState(false)
  const titleKey = mode === 'login' ? 'loginTitle' : mode === 'register' ? 'registerTitle' : 'forgotTitle'
  const bodyKey = mode === 'login' ? 'loginBody' : mode === 'register' ? 'registerBody' : 'forgotBody'
  const submitKey = mode === 'login' ? 'signIn' : mode === 'register' ? 'createAccount' : 'sendReset'

  function switchLocale(nextLocale: 'en' | 'zh-CN') {
    router.replace(pathname.replace(/^\/(en|zh-CN)/, `/${nextLocale}`))
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link className="auth-brand" href={`/${locale}/command/dashboard`}><span className="brand-mark">G</span><span><strong>Grovello</strong><small>{t('kicker')}</small></span></Link>
        <div className="auth-story__content"><span className="eyebrow">{t('kicker')}</span><h1>{t('title')}</h1><p>{t('body')}</p><div className="auth-loop">{['radar','psychology','campaign','handshake','payments','autorenew'].map((icon) => <span key={icon}><Icon name={icon} size={23} /></span>)}</div></div>
        <small>© 2026 Grovello · Foundation build</small>
      </section>
      <section className="auth-form-side">
        <div className="auth-language segmented-control"><button className={locale === 'en' ? 'active' : ''} onClick={() => switchLocale('en')}>EN</button><button className={locale === 'zh-CN' ? 'active' : ''} onClick={() => switchLocale('zh-CN')}>中文</button></div>
        <form className="auth-card" onSubmit={(event) => { event.preventDefault(); setSubmitted(true) }}>
          <div className="auth-card__heading"><h2>{t(titleKey)}</h2><p>{t(bodyKey)}</p></div>
          {mode === 'register' ? <label className="field-label"><span>{t('fullName')}</span><input required autoComplete="name" type="text" placeholder="Huang Heng" /></label> : null}
          {mode === 'register' ? <label className="field-label"><span>{t('workspaceName')}</span><input required type="text" placeholder="Northstar Industrial" /></label> : null}
          <label className="field-label"><span>{t('email')}</span><input required autoComplete="email" type="email" placeholder="you@company.com" /></label>
          {mode !== 'forgot' ? <label className="field-label"><span>{t('password')}</span><div className="password-field"><input required minLength={8} type={passwordVisible ? 'text' : 'password'} autoComplete="current-password" placeholder="••••••••••••" /><button type="button" aria-label={passwordVisible ? 'Hide password' : 'Show password'} onClick={() => setPasswordVisible(!passwordVisible)}><Icon name={passwordVisible ? 'visibility_off' : 'visibility'} size={19} /></button></div></label> : null}
          {mode === 'login' ? <div className="auth-options"><label><input type="checkbox" />{t('remember')}</label><Link href={`/${locale}/forgot-password`}>{t('forgot')}</Link></div> : null}
          <button className="button button--primary button--full auth-submit" type="submit">{t(submitKey)}<Icon name="arrow_forward" size={19} /></button>
          {submitted ? <p className="auth-notice"><Icon name="info" size={18} />{t('authPending')}</p> : null}
          {mode === 'login' ? <p className="auth-switch">{t('noAccount')} <Link href={`/${locale}/register`}>{t('createAccount')}</Link></p> : <p className="auth-switch">{t('hasAccount')} <Link href={`/${locale}/login`}>{t('signIn')}</Link></p>}
          <small className="auth-terms">{t('terms')}</small>
        </form>
      </section>
    </main>
  )
}
