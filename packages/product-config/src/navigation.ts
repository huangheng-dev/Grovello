export type CapabilityStatus = 'active' | 'foundation' | 'reserved'
export type CapabilityAudience = 'operator' | 'admin' | 'developer'
export type CapabilityPlacement = 'primary' | 'advanced' | 'help'

export interface NavigationItem {
  key: string
  slug: string
  icon: string
  status: CapabilityStatus
  phase: number
  audience: CapabilityAudience
  placement: CapabilityPlacement
}

export interface NavigationSection {
  key: string
  slug: string
  icon: string
  items: NavigationItem[]
}

/**
 * Canonical capability catalog. Reserved capabilities stay here so routes,
 * permissions, translations, and shared-object ownership can remain stable
 * without presenting unfinished controls as operational product features.
 */
export const navigationSections: NavigationSection[] = [
  { key: 'command', slug: 'command', icon: 'space_dashboard', items: [
    { key: 'dashboard', slug: 'dashboard', icon: 'dashboard', status: 'active', phase: 1, audience: 'operator', placement: 'primary' },
    { key: 'journeys', slug: 'journeys', icon: 'conversion_path', status: 'active', phase: 1, audience: 'operator', placement: 'primary' },
    { key: 'deliveryRoadmap', slug: 'delivery-roadmap', icon: 'timeline', status: 'active', phase: 1, audience: 'operator', placement: 'primary' },
    { key: 'goals', slug: 'goals', icon: 'flag', status: 'reserved', phase: 3, audience: 'operator', placement: 'primary' },
    { key: 'plans', slug: 'plans', icon: 'route', status: 'reserved', phase: 3, audience: 'operator', placement: 'primary' },
    { key: 'decisions', slug: 'decisions', icon: 'fact_check', status: 'reserved', phase: 3, audience: 'operator', placement: 'primary' },
    { key: 'architecture', slug: 'architecture', icon: 'account_tree', status: 'active', phase: 1, audience: 'developer', placement: 'help' },
  ]},
  { key: 'brand', slug: 'brand', icon: 'diamond', items: [
    { key: 'brandRules', slug: 'business-brand', icon: 'palette', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'products', slug: 'products-offers', icon: 'inventory_2', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'markets', slug: 'markets', icon: 'public', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'icp', slug: 'ideal-customers', icon: 'target', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'knowledge', slug: 'knowledge-evidence', icon: 'library_books', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'assets', slug: 'assets', icon: 'perm_media', status: 'foundation', phase: 2, audience: 'operator', placement: 'primary' },
    { key: 'businessSetup', slug: 'business-setup', icon: 'checklist', status: 'foundation', phase: 2, audience: 'operator', placement: 'advanced' },
    { key: 'imports', slug: 'imports', icon: 'upload_file', status: 'foundation', phase: 2, audience: 'operator', placement: 'advanced' },
  ]},
  { key: 'content', slug: 'content', icon: 'edit_note', items: [
    { key: 'contentFactory', slug: 'studio', icon: 'auto_awesome', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
    { key: 'sites', slug: 'sites-pages', icon: 'web', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
    { key: 'seo', slug: 'seo', icon: 'search', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
    { key: 'geo', slug: 'ai-search', icon: 'travel_explore', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
    { key: 'video', slug: 'video', icon: 'movie', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
    { key: 'publish', slug: 'publishing', icon: 'send', status: 'reserved', phase: 4, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'channels', slug: 'channels', icon: 'hub', items: [
    { key: 'channelAccounts', slug: 'connections', icon: 'lan', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
    { key: 'social', slug: 'social', icon: 'forum', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
    { key: 'ads', slug: 'paid-media', icon: 'campaign', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'pipeline', slug: 'pipeline', icon: 'person_search', items: [
    { key: 'leads', slug: 'intelligence', icon: 'manage_search', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
    { key: 'outbound', slug: 'sequences', icon: 'outgoing_mail', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
    { key: 'inbox', slug: 'inbox', icon: 'inbox', status: 'reserved', phase: 5, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'revenue', slug: 'revenue', icon: 'payments', items: [
    { key: 'crm', slug: 'crm-pipeline', icon: 'handshake', status: 'reserved', phase: 6, audience: 'operator', placement: 'primary' },
    { key: 'sales', slug: 'sales-workspace', icon: 'support_agent', status: 'reserved', phase: 6, audience: 'operator', placement: 'primary' },
    { key: 'commercial', slug: 'quote-to-cash', icon: 'request_quote', status: 'reserved', phase: 6, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'customer', slug: 'customer', icon: 'loyalty', items: [
    { key: 'success', slug: 'onboarding-success', icon: 'health_and_safety', status: 'reserved', phase: 7, audience: 'operator', placement: 'primary' },
    { key: 'retention', slug: 'health-retention', icon: 'autorenew', status: 'reserved', phase: 7, audience: 'operator', placement: 'primary' },
    { key: 'referral', slug: 'expansion-advocacy', icon: 'group_add', status: 'reserved', phase: 7, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'data', slug: 'data', icon: 'monitoring', items: [
    { key: 'dataCenter', slug: 'unified-data', icon: 'database', status: 'reserved', phase: 8, audience: 'operator', placement: 'primary' },
    { key: 'intelligence', slug: 'market-intelligence', icon: 'radar', status: 'reserved', phase: 8, audience: 'operator', placement: 'primary' },
    { key: 'reports', slug: 'analytics', icon: 'analytics', status: 'reserved', phase: 8, audience: 'operator', placement: 'primary' },
    { key: 'attribution', slug: 'attribution', icon: 'conversion_path', status: 'reserved', phase: 8, audience: 'operator', placement: 'primary' },
    { key: 'experiments', slug: 'experiments', icon: 'experiment', status: 'reserved', phase: 8, audience: 'operator', placement: 'primary' },
  ]},
  { key: 'automation', slug: 'automation', icon: 'smart_toy', items: [
    { key: 'runs', slug: 'runs', icon: 'play_circle', status: 'reserved', phase: 3, audience: 'operator', placement: 'primary' },
    { key: 'workflows', slug: 'workflows', icon: 'schema', status: 'reserved', phase: 3, audience: 'admin', placement: 'primary' },
    { key: 'agents', slug: 'agents-templates', icon: 'robot_2', status: 'reserved', phase: 3, audience: 'admin', placement: 'primary' },
    { key: 'connectors', slug: 'integrations', icon: 'extension', status: 'reserved', phase: 3, audience: 'admin', placement: 'primary' },
    { key: 'models', slug: 'model-routing', icon: 'model_training', status: 'reserved', phase: 3, audience: 'developer', placement: 'advanced' },
    { key: 'developer', slug: 'developer', icon: 'api', status: 'reserved', phase: 3, audience: 'developer', placement: 'advanced' },
    { key: 'marketplace', slug: 'marketplace', icon: 'storefront', status: 'reserved', phase: 9, audience: 'admin', placement: 'advanced' },
  ]},
  { key: 'governance', slug: 'governance', icon: 'admin_panel_settings', items: [
    { key: 'team', slug: 'workspaces-access', icon: 'groups', status: 'foundation', phase: 1, audience: 'admin', placement: 'primary' },
    { key: 'compliance', slug: 'compliance-security', icon: 'verified_user', status: 'foundation', phase: 1, audience: 'admin', placement: 'primary' },
    { key: 'audit', slug: 'audit', icon: 'history', status: 'foundation', phase: 1, audience: 'admin', placement: 'primary' },
    { key: 'settings', slug: 'settings', icon: 'settings', status: 'foundation', phase: 1, audience: 'admin', placement: 'primary' },
  ]},
]

export const navigationItems = navigationSections.flatMap((section) =>
  section.items.map((item) => ({ ...item, sectionKey: section.key, sectionSlug: section.slug })),
)

export function getPrimaryNavigationItems(section: NavigationSection) {
  return section.items.filter((item) => item.placement === 'primary' && item.status !== 'reserved')
}

export function isNavigationItemRoutable(item: NavigationItem) {
  return item.status !== 'reserved'
}

export function findNavigationSection(sectionSlug: string) {
  return navigationSections.find((section) => section.slug === sectionSlug)
}

export function findNavigationItem(sectionSlug: string, itemSlug: string) {
  return navigationItems.find((item) => item.sectionSlug === sectionSlug && item.slug === itemSlug)
}

export const sharedObjectsBySection: Record<string, string[]> = {
  command: ['Goal', 'Budget', 'Strategy', 'Campaign', 'Approval'],
  brand: ['Brand', 'Product', 'Offer', 'PriceBook', 'Market', 'ICP', 'CaseStudy', 'KnowledgeDocument', 'Asset'],
  content: ['Brief', 'Content', 'Page', 'Keyword', 'Claim', 'Citation', 'Publication'],
  channels: ['Channel', 'ChannelAccount', 'Publication', 'AdCampaign', 'Creative'],
  pipeline: ['Account', 'Contact', 'Lead', 'Message', 'Conversation', 'Consent'],
  revenue: ['Opportunity', 'Meeting', 'Quote', 'Contract', 'Order', 'Invoice', 'Payment'],
  customer: ['OnboardingPlan', 'CustomerHealth', 'Renewal', 'Expansion', 'Referral'],
  data: ['MetricEvent', 'AttributionResult', 'Experiment', 'Report', 'Insight'],
  automation: ['Agent', 'Workflow', 'Run', 'Task', 'Connector', 'ModelConfig'],
  governance: ['Workspace', 'User', 'Role', 'Policy', 'Consent', 'Secret', 'AuditEvent'],
}
