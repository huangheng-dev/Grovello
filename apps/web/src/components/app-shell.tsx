'use client'

import { navigationSections } from '@grovello/product-config'
import { Icon } from '@grovello/ui'
import Link from 'next/link'
import { useLocale, useTranslations } from 'next-intl'
import { usePathname, useRouter } from 'next/navigation'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'

const collapsedKey = 'grovello.sidebar.collapsed'
const groupsKey = 'grovello.sidebar.groups'

export function AppShell({ children }: { children: ReactNode }) {
  const locale = useLocale()
  const t = useTranslations()
  const pathname = usePathname()
  const router = useRouter()
  const profileRef = useRef<HTMLDivElement>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setCollapsed(window.localStorage.getItem(collapsedKey) === 'true')
      try {
        setOpenGroups(JSON.parse(window.localStorage.getItem(groupsKey) ?? '{}') as Record<string, boolean>)
      } catch {
        setOpenGroups({})
      }
    })
    return () => window.cancelAnimationFrame(frame)
  }, [])

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) setProfileOpen(false)
    }
    document.addEventListener('mousedown', closeProfile)
    return () => document.removeEventListener('mousedown', closeProfile)
  }, [])

  const routeState = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean)
    const sectionSlug = segments[1] ?? 'command'
    const itemSlug = segments[2] ?? 'dashboard'
    const section = navigationSections.find((candidate) => candidate.slug === sectionSlug) ?? navigationSections[0]
    const item = section?.items.find((candidate) => candidate.slug === itemSlug) ?? section?.items[0]
    return { section, item }
  }, [pathname])

  function toggleCollapsed() {
    const next = !collapsed
    setCollapsed(next)
    window.localStorage.setItem(collapsedKey, String(next))
  }

  function toggleGroup(key: string) {
    const next = { ...openGroups, [key]: !(openGroups[key] ?? true) }
    setOpenGroups(next)
    window.localStorage.setItem(groupsKey, JSON.stringify(next))
  }

  function switchLocale(nextLocale: 'en' | 'zh-CN') {
    const segments = pathname.split('/')
    segments[1] = nextLocale
    window.localStorage.setItem('grovello.locale', nextLocale)
    setProfileOpen(false)
    router.replace(segments.join('/') || `/${nextLocale}/command/dashboard`)
  }

  return (
    <div className={`app-shell ${collapsed ? 'app-shell--collapsed' : ''}`}>
      {mobileOpen ? <button className="sidebar-scrim" aria-label={t('common.closeMenu')} onClick={() => setMobileOpen(false)} /> : null}
      <aside className={`sidebar ${mobileOpen ? 'sidebar--mobile-open' : ''}`}>
        <div className="brand-lockup">
          <Link className="brand-lockup__link" href={`/${locale}/command/dashboard`} onClick={() => setMobileOpen(false)}>
            <span className="brand-mark">G</span>
            {!collapsed ? <span className="brand-copy"><strong>Grovello</strong><small>{t('common.productCategory')}</small></span> : null}
          </Link>
          <button className="icon-button sidebar-collapse" aria-label={collapsed ? t('common.expand') : t('common.collapse')} onClick={toggleCollapsed}>
            <Icon name={collapsed ? 'right_panel_open' : 'left_panel_close'} />
          </button>
          <button className="icon-button sidebar-mobile-close" aria-label={t('common.closeMenu')} onClick={() => setMobileOpen(false)}><Icon name="close" /></button>
        </div>

        <nav className="sidebar-nav" aria-label={t('common.primaryNavigation')}>
          {navigationSections.map((section) => {
            const open = openGroups[section.key] ?? true
            return (
              <section className="nav-section" key={section.key}>
                <button className={`nav-section__header ${routeState.section?.key === section.key ? 'nav-section__header--active' : ''}`} aria-expanded={open} onClick={() => toggleGroup(section.key)}>
                  <Icon name={section.icon} size={19} />
                  {!collapsed ? <><span>{t(`sections.${section.key}`)}</span><Icon className="nav-section__chevron" name={open ? 'expand_less' : 'expand_more'} size={18} /></> : null}
                </button>
                {(open || collapsed) ? (
                  <div className="nav-section__items">
                    {section.items.map((item) => (
                      <Link
                        className={`nav-item ${routeState.item?.key === item.key ? 'nav-item--active' : ''}`}
                        href={`/${locale}/${section.slug}/${item.slug}`}
                        key={item.key}
                        title={collapsed ? t(`pages.${item.key}.title`) : undefined}
                        onClick={() => setMobileOpen(false)}
                      >
                        <Icon name={item.icon} size={19} />
                        {!collapsed ? <span>{t(`pages.${item.key}.title`)}</span> : null}
                      </Link>
                    ))}
                  </div>
                ) : null}
              </section>
            )
          })}
        </nav>
        <div className={`sidebar-footer ${collapsed ? 'sidebar-footer--collapsed' : ''}`}>
          <span className="system-pulse" />
          {!collapsed ? <div><strong>{t('common.foundationBuild')}</strong><small>v0.1.0 · local</small></div> : null}
        </div>
      </aside>

      <div className="workspace-shell">
        <header className="topbar">
          <div className="topbar__left">
            <button className="icon-button mobile-menu-button" aria-label={t('common.openMenu')} onClick={() => setMobileOpen(true)}><Icon name="menu" /></button>
            <div className="page-identity"><span>{t(`sections.${routeState.section?.key ?? 'command'}`)}</span><strong>{t(`pages.${routeState.item?.key ?? 'dashboard'}.title`)}</strong></div>
          </div>
          <div className="topbar__right">
            <label className="global-search"><Icon name="search" size={19} /><input type="search" placeholder={t('common.search')} /><kbd>⌘ K</kbd></label>
            <button className="icon-button topbar-action" aria-label={t('common.help')}><Icon name="help" /></button>
            <button className="icon-button topbar-action notification-button" aria-label={t('common.notifications')}><Icon name="notifications" /><span className="notification-dot" /></button>
            <div className="profile-menu-wrap" ref={profileRef}>
              <button className="profile-button" aria-label={t('common.profile')} aria-expanded={profileOpen} onClick={() => setProfileOpen(!profileOpen)}>
                <span className="avatar">HH</span>
                <span className="profile-button__copy"><strong>Huang Heng</strong><small>{t('common.workspace')}</small></span>
                <Icon name="expand_more" size={18} />
              </button>
              {profileOpen ? (
                <div className="profile-popover">
                  <div className="profile-popover__identity"><span className="avatar avatar--large">HH</span><div><strong>Huang Heng</strong><small>owner@localhost</small></div></div>
                  <div className="profile-popover__section">
                    <span className="popover-label">{t('common.currentWorkspace')}</span>
                    <button className="workspace-option workspace-option--active"><span className="workspace-logo">NI</span><span><strong>{t('common.workspaceA')}</strong><small>{t('common.ownerWorkspace')}</small></span><Icon name="check" size={18} /></button>
                    <button className="workspace-option"><span className="workspace-logo workspace-logo--muted">GS</span><span><strong>{t('common.workspaceB')}</strong><small>{t('common.developerSandbox')}</small></span></button>
                  </div>
                  <div className="profile-popover__section profile-popover__language"><span className="popover-label">{t('common.language')}</span><div className="segmented-control"><button className={locale === 'en' ? 'active' : ''} onClick={() => switchLocale('en')}>English</button><button className={locale === 'zh-CN' ? 'active' : ''} onClick={() => switchLocale('zh-CN')}>简体中文</button></div></div>
                  <div className="profile-popover__actions"><Link href={`/${locale}/governance/settings`} onClick={() => setProfileOpen(false)}><Icon name="manage_accounts" size={19} />{t('common.accountSettings')}</Link><Link className="danger-link" href={`/${locale}/login`}><Icon name="logout" size={19} />{t('common.signOut')}</Link></div>
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  )
}
