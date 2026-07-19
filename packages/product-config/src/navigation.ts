export interface NavigationItem {
  key: string
  slug: string
  icon: string
}

export interface NavigationSection {
  key: string
  slug: string
  icon: string
  items: NavigationItem[]
}

export const navigationSections: NavigationSection[] = [
  { key: 'command', slug: 'command', icon: 'space_dashboard', items: [
    { key: 'dashboard', slug: 'dashboard', icon: 'dashboard' },
    { key: 'journeys', slug: 'journeys', icon: 'conversion_path' },
    { key: 'architecture', slug: 'architecture', icon: 'account_tree' },
    { key: 'goals', slug: 'goals', icon: 'flag' },
    { key: 'decisions', slug: 'decisions', icon: 'psychology' },
    { key: 'plans', slug: 'plans', icon: 'route' },
    { key: 'approvals', slug: 'approvals', icon: 'task_alt' },
  ]},
  { key: 'brand', slug: 'brand', icon: 'diamond', items: [
    { key: 'brandRules', slug: 'rules', icon: 'palette' },
    { key: 'products', slug: 'products', icon: 'inventory_2' },
    { key: 'markets', slug: 'markets', icon: 'public' },
    { key: 'icp', slug: 'icp', icon: 'target' },
    { key: 'knowledge', slug: 'knowledge', icon: 'library_books' },
    { key: 'assets', slug: 'assets', icon: 'perm_media' },
  ]},
  { key: 'content', slug: 'content', icon: 'edit_note', items: [
    { key: 'contentFactory', slug: 'factory', icon: 'auto_awesome' },
    { key: 'sites', slug: 'sites', icon: 'web' },
    { key: 'seo', slug: 'seo', icon: 'search' },
    { key: 'geo', slug: 'geo', icon: 'travel_explore' },
    { key: 'video', slug: 'video', icon: 'movie' },
    { key: 'publish', slug: 'publish', icon: 'send' },
  ]},
  { key: 'channels', slug: 'channels', icon: 'hub', items: [
    { key: 'channelAccounts', slug: 'accounts', icon: 'lan' },
    { key: 'social', slug: 'social', icon: 'forum' },
    { key: 'ads', slug: 'ads', icon: 'campaign' },
  ]},
  { key: 'pipeline', slug: 'pipeline', icon: 'person_search', items: [
    { key: 'leads', slug: 'leads', icon: 'manage_search' },
    { key: 'email', slug: 'email', icon: 'mail' },
    { key: 'outbound', slug: 'outbound', icon: 'outgoing_mail' },
    { key: 'inbox', slug: 'inbox', icon: 'inbox' },
  ]},
  { key: 'revenue', slug: 'revenue', icon: 'payments', items: [
    { key: 'crm', slug: 'crm', icon: 'handshake' },
    { key: 'sales', slug: 'sales', icon: 'support_agent' },
    { key: 'commercial', slug: 'commercial', icon: 'request_quote' },
  ]},
  { key: 'customer', slug: 'customer', icon: 'loyalty', items: [
    { key: 'success', slug: 'success', icon: 'health_and_safety' },
    { key: 'retention', slug: 'retention', icon: 'autorenew' },
    { key: 'referral', slug: 'referral', icon: 'group_add' },
  ]},
  { key: 'data', slug: 'data', icon: 'monitoring', items: [
    { key: 'dataCenter', slug: 'center', icon: 'database' },
    { key: 'attribution', slug: 'attribution', icon: 'conversion_path' },
    { key: 'reports', slug: 'reports', icon: 'analytics' },
    { key: 'experiments', slug: 'experiments', icon: 'experiment' },
    { key: 'intelligence', slug: 'intelligence', icon: 'radar' },
  ]},
  { key: 'automation', slug: 'automation', icon: 'smart_toy', items: [
    { key: 'runs', slug: 'runs', icon: 'play_circle' },
    { key: 'workflows', slug: 'workflows', icon: 'schema' },
    { key: 'agents', slug: 'agents', icon: 'robot_2' },
    { key: 'marketplace', slug: 'marketplace', icon: 'storefront' },
    { key: 'connectors', slug: 'connectors', icon: 'extension' },
    { key: 'models', slug: 'models', icon: 'model_training' },
    { key: 'developer', slug: 'developer', icon: 'api' },
  ]},
  { key: 'governance', slug: 'governance', icon: 'admin_panel_settings', items: [
    { key: 'team', slug: 'team', icon: 'groups' },
    { key: 'compliance', slug: 'compliance', icon: 'verified_user' },
    { key: 'audit', slug: 'audit', icon: 'history' },
    { key: 'settings', slug: 'settings', icon: 'settings' },
  ]},
]

export const navigationItems = navigationSections.flatMap((section) =>
  section.items.map((item) => ({ ...item, sectionKey: section.key, sectionSlug: section.slug })),
)

export function findNavigationItem(sectionSlug: string, itemSlug: string) {
  return navigationItems.find((item) => item.sectionSlug === sectionSlug && item.slug === itemSlug)
}

export const sharedObjectsBySection: Record<string, string[]> = {
  command: ['Goal', 'Budget', 'Strategy', 'Campaign', 'Approval'],
  brand: ['Brand', 'Product', 'Offer', 'PriceBook', 'Market', 'ICP', 'CaseStudy', 'KnowledgeDocument', 'Asset'],
  content: ['Brief', 'Content', 'Page', 'Keyword', 'Claim', 'Citation', 'Publication'],
  channels: ['Channel', 'ChannelAccount', 'Publication', 'AdCampaign', 'Creative'],
  pipeline: ['Account', 'Contact', 'Lead', 'Message', 'Conversation', 'Consent'],
  revenue: ['Opportunity', 'Meeting', 'Quote', 'Contract', 'Order', 'Payment'],
  customer: ['OnboardingPlan', 'CustomerHealth', 'Renewal', 'Expansion', 'Referral'],
  data: ['MetricEvent', 'AttributionResult', 'Experiment', 'Report', 'Insight'],
  automation: ['Agent', 'Workflow', 'Run', 'Task', 'Connector', 'ModelConfig'],
  governance: ['Workspace', 'User', 'Role', 'Policy', 'Secret', 'AuditEvent'],
}
