// 命令面板过滤纯逻辑测试（UI2 第二批④）
import { describe, expect, it } from 'vitest'
import { filterPaletteCommands, type PaletteCommand } from '@/utils/palette'

const COMMANDS: PaletteCommand[] = [
  { id: 'new', title: '新建项目', keywords: ['new', 'xinjian'] },
  { id: 'billing', title: 'Billing 面板', keywords: ['billing', '账单'], meta: '查看额度与用量' },
  { id: 'settings', title: 'Settings 面板', keywords: ['settings', 'shezhi'] },
]

describe('filterPaletteCommands', () => {
  it('空查询返回全部命令', () => {
    expect(filterPaletteCommands(COMMANDS, '')).toHaveLength(3)
    expect(filterPaletteCommands(COMMANDS, '   ')).toHaveLength(3)
  })

  it('按标题匹配（中文）', () => {
    expect(filterPaletteCommands(COMMANDS, '新建').map((c) => c.id)).toEqual(['new'])
  })

  it('按关键词与 meta 匹配，且不区分大小写', () => {
    expect(filterPaletteCommands(COMMANDS, 'BILLING').map((c) => c.id)).toEqual(['billing'])
    expect(filterPaletteCommands(COMMANDS, '额度').map((c) => c.id)).toEqual(['billing'])
    expect(filterPaletteCommands(COMMANDS, 'xinjian').map((c) => c.id)).toEqual(['new'])
  })

  it('无命中返回空数组（不抛错）', () => {
    expect(filterPaletteCommands(COMMANDS, '不存在的命令')).toEqual([])
  })
})
