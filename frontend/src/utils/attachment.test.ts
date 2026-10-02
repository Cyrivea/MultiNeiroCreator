// 附件识别纯函数测试（F2：todo §4.3 "附件"纯逻辑）
import { describe, expect, it } from 'vitest'
import {
  renamePastedFile,
  getAttachmentBadge,
  getAttachmentExtension,
  resolveAttachmentKind,
} from '@/utils/attachment'

describe('getAttachmentExtension', () => {
  it('取最后一个点后的小写扩展名', () => {
    expect(getAttachmentExtension('Report.Final.PDF')).toBe('pdf')
  })

  it('无扩展名返回空串', () => {
    expect(getAttachmentExtension('README')).toBe('')
  })

  it('点结尾返回空串', () => {
    expect(getAttachmentExtension('weird.')).toBe('')
  })
})

describe('resolveAttachmentKind', () => {
  it('MIME 优先识别图片（扩展名不标准也认）', () => {
    expect(resolveAttachmentKind({ name: 'photo.xyz', type: 'image/png' })).toBe('image')
  })

  it('MIME 缺失时按扩展名识别', () => {
    expect(resolveAttachmentKind({ name: 'pic.webp', type: '' })).toBe('image')
    expect(resolveAttachmentKind({ name: 'doc.pdf', type: '' })).toBe('pdf')
    expect(resolveAttachmentKind({ name: 'a.docx', type: '' })).toBe('word')
    expect(resolveAttachmentKind({ name: 'a.csv', type: '' })).toBe('excel')
    expect(resolveAttachmentKind({ name: 'a.pptx', type: '' })).toBe('ppt')
    expect(resolveAttachmentKind({ name: 'a.md', type: '' })).toBe('text')
  })

  it('Office MIME（officedocument.*）正确归类', () => {
    expect(
      resolveAttachmentKind({
        name: 'x.bin',
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }),
    ).toBe('word')
  })

  it('未知类型落到 file', () => {
    expect(resolveAttachmentKind({ name: 'archive.tar.zst', type: '' })).toBe('file')
  })
})

describe('getAttachmentBadge', () => {
  it('按 kind + 扩展名给出徽标文本', () => {
    expect(getAttachmentBadge('pdf', 'pdf')).toBe('PDF')
    expect(getAttachmentBadge('word', 'doc')).toBe('DOC')
    expect(getAttachmentBadge('word', 'docx')).toBe('DOCX')
    expect(getAttachmentBadge('excel', 'csv')).toBe('CSV')
    expect(getAttachmentBadge('text', '')).toBe('TXT')
    expect(getAttachmentBadge('file', '')).toBe('FILE')
    expect(getAttachmentBadge('file', 'zip')).toBe('ZIP')
  })
})

// UI2 第二批①：粘贴改名的边界（截图无名/通用名才改，本地拖拽来的正常文件不动）
describe('renamePastedFile', () => {
  it('剪贴板通用名（image.png）改名成带时间戳的独立名', () => {
    const file = new File(['x'], 'image.png', { type: 'image/png' })
    const renamed = renamePastedFile(file, new Date('2026-10-03T10:20:30Z'))
    expect(renamed.name).toMatch(/^pasted-\d{8}-\d{6}-[a-z0-9]{4}\.png$/)
    expect(renamed.type).toBe('image/png')
  })

  it('无名 blob 也给出可读名，两个连续粘贴不同名', () => {
    const a = renamePastedFile(new File(['1'], 'blob', { type: 'image/jpeg' }))
    const b = renamePastedFile(new File(['2'], 'blob', { type: 'image/jpeg' }))
    expect(a.name).toMatch(/\.jpg$/)
    expect(b.name).not.toBe(a.name)
  })

  it('已经有正常名字的文件（本地拖入）保持原样', () => {
    const file = new File(['x'], '设计稿-封面.png', { type: 'image/png' })
    expect(renamePastedFile(file).name).toBe('设计稿-封面.png')
  })
})
