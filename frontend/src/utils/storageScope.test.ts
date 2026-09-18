// B26：同一浏览器多账号时，本地缓存必须按账号隔开。
import { describe, expect, it, beforeEach } from 'vitest'
import { readScoped, removeScoped, scopedKey, writeScoped } from '@/utils/storageScope'
import { USERNAME_KEY } from '@/constants'

describe('storageScope：账号隔离', () => {
  beforeEach(() => localStorage.clear())

  it('不同账号的键不同', () => {
    localStorage.setItem(USERNAME_KEY, 'alice@x.com')
    const a = scopedKey('mnc-workflow-draft:11')
    localStorage.setItem(USERNAME_KEY, 'bob@x.com')
    const b = scopedKey('mnc-workflow-draft:11')
    expect(a).not.toBe(b)
    expect(a).toContain('alice')
    expect(b).toContain('bob')
  })

  it('写读都在隔离键上，另一条账号读不到', () => {
    localStorage.setItem(USERNAME_KEY, 'alice@x.com')
    writeScoped('mnc-demo', 'alice-data')
    expect(readScoped('mnc-demo')).toBe('alice-data')

    localStorage.setItem(USERNAME_KEY, 'bob@x.com')
    // 老全局键不存在 → null，绝不串回 alice 的数据
    expect(readScoped('mnc-demo')).toBeNull()
    expect(localStorage.getItem('mnc-demo')).toBeNull()
  })

  it('老全局键数据一次性回退迁移，写进隔离键后不再读老键', () => {
    localStorage.setItem(USERNAME_KEY, 'alice@x.com')
    localStorage.setItem('mnc-legacy', 'legacy-data')
    expect(readScoped('mnc-legacy')).toBe('legacy-data')
    writeScoped('mnc-legacy', 'migrated')
    expect(readScoped('mnc-legacy')).toBe('migrated')

    removeScoped('mnc-legacy')
    expect(readScoped('mnc-legacy')).toBeNull()
    expect(localStorage.getItem('mnc-legacy')).toBeNull()
  })
})
