import en from '@grovello/i18n/en.json'
import zhCN from '@grovello/i18n/zh-CN.json'
import { describe, expect, it } from 'vitest'

describe('web foundation', () => {
  it('ships the brand and both primary locales', () => {
    expect('Grovello').toMatch(/Grovello/)
    expect(en.common.productCategory).toBe('AI Growth OS')
    expect(zhCN.common.productCategory).toBe('AI 企业增长操作系统')
  })
})
