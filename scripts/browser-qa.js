async (page) => {
  const result = {}
  const screenshotPath = (filename) => process.cwd().replaceAll('\\', '/') + `/output/playwright/${filename}`
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('http://127.0.0.1:3100/en/command/dashboard')
  result.dashboardTitle = await page.getByRole('heading', { name: 'Good morning, Huang Heng.' }).isVisible()
  result.mainScroll = await page.getByRole('main').evaluate((element) => {
    element.style.scrollBehavior = 'auto'
    element.scrollTop = element.scrollHeight
    return { scrollTop: element.scrollTop, max: element.scrollHeight - element.clientHeight }
  })
  await page.getByRole('button', { name: 'Open profile menu' }).click()
  result.profileMenu = await page.getByText('Current workspace', { exact: true }).isVisible()
  result.workspaceOptions = await page.locator('.workspace-option').count()
  await page.getByRole('button', { name: 'Open profile menu' }).click()

  await page.goto('http://127.0.0.1:3100/en/content/seo')
  result.seoTitle = await page.getByRole('heading', { name: 'Search Growth (SEO)' }).isVisible()
  await page.getByRole('button', { name: 'Filters' }).click()
  result.filters = await page.locator('.filter-bar').isVisible()
  await page.getByRole('button', { name: 'Create record' }).click()
  const dialog = page.getByRole('dialog')
  result.dialog = await dialog.isVisible()
  await dialog.getByLabel('Name').fill('Industrial robotics topic cluster')
  result.approvalChecked = await dialog.getByRole('checkbox').isChecked()
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('button', { name: /Records/ }).click()
  result.recordRows = await page.locator('tbody tr').count()
  await page.locator('tbody input[type=checkbox]').first().check()
  result.recordChecked = await page.locator('tbody input[type=checkbox]').first().isChecked()
  await page.screenshot({ path: screenshotPath('seo-module.png'), fullPage: true })

  await page.goto('http://127.0.0.1:3100/en/command/architecture')
  result.architectureLayers = await page.locator('.architecture-layer').count()
  await page.screenshot({ path: screenshotPath('architecture.png'), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('http://127.0.0.1:3100/zh-CN/command/dashboard')
  await page.getByRole('button', { name: '打开导航' }).click()
  await page.waitForTimeout(300)
  result.mobileSidebar = await page.locator('.sidebar--mobile-open').isVisible()
  result.mobileSidebarGeometry = await page.locator('aside.sidebar').evaluate((element) => ({
    className: element.className,
    left: element.getBoundingClientRect().left,
    right: element.getBoundingClientRect().right,
    width: element.getBoundingClientRect().width,
    transform: getComputedStyle(element).transform,
    zIndex: getComputedStyle(element).zIndex,
  }))
  await page.screenshot({ path: screenshotPath('mobile-zh.png') })

  await page.goto('http://127.0.0.1:3100/en/login')
  await page.getByLabel('Work email').fill('owner@example.com')
  await page.locator('input[type="password"]').fill('correct-horse-battery-staple')
  await page.getByLabel('Remember me').check()
  await page.getByRole('button', { name: 'Sign in' }).click()
  result.authNotice = await page.getByText(/identity provider is not connected/).isVisible()
  await page.screenshot({ path: screenshotPath('login-mobile.png'), fullPage: true })
  return result
}
