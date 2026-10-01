// @vitest-environment jsdom
// Markdown 渲染管线测试（UI1）：功能正确性 + 消毒底线（C19 防线，模型输出属不可信文本）
// 环境用 jsdom 而非项目默认 happy-dom：DOMPurify 3.x 在 happy-dom 下会误剥
// h1/pre 等块级标签（DOM 实现差异），导致安全管线测不出真实浏览器行为。
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '@/utils/markdown'

describe('renderMarkdown 基础能力', () => {
  it('渲染标题、加粗、列表', () => {
    const html = renderMarkdown('# 标题\n\n- 甲\n- 乙\n\n**加粗**')
    expect(html).toContain('<h1>')
    expect(html).toContain('<li>')
    expect(html).toContain('<strong>')
  })

  it('breaks: true 下单行回车渲染为换行（聊天气泡场景）', () => {
    const html = renderMarkdown('第一行\n第二行')
    expect(html).toContain('<br')
  })

  it('空文本渲染为空串', () => {
    expect(renderMarkdown('')).toBe('')
  })
})

describe('renderMarkdown 代码块', () => {
  it('带语言标签与复制按钮', () => {
    const html = renderMarkdown('```python\nprint("hi")\n```')
    expect(html).toContain('md-codeblock')
    expect(html).toContain('md-codeblock-lang')
    expect(html).toContain('python')
    expect(html).toContain('md-code-copy')
  })

  it('已知语言做高亮（产出 hljs 词元 span）', () => {
    const html = renderMarkdown('```js\nconst a = 1\n```')
    expect(html).toContain('hljs')
  })

  it('未知语言不冒充高亮，走预格式化原文', () => {
    const html = renderMarkdown('```klingon\nQapla\n```')
    expect(html).toContain('<pre>')
    expect(html).not.toContain('md-codeblock')
  })

  it('语言别名归一化：sh 按 bash 高亮', () => {
    const html = renderMarkdown('```sh\nls -la\n```')
    expect(html).toContain('md-codeblock')
    expect(html).toContain('bash')
  })
})

describe('renderMarkdown 安全消毒（C19 防线）', () => {
  it('script 标签原样转义，绝不进 DOM', () => {
    const html = renderMarkdown('<script>alert(1)</script>')
    expect(html).not.toContain('<script>')
  })

  it('内嵌 HTML 事件属性绝不生成活标签', () => {
    // html:false 会把源文 HTML 转成纯文本实体（&lt;img ...&gt;），字符串里仍看得见
    // “onerror”字样，但它是死文本不是活 DOM。断言的是“无活标签”，而非字面量消失。
    const html = renderMarkdown('点击这里 <img src=x onerror="alert(1)">')
    expect(html).not.toMatch(/<img/i)
    expect(html).toContain('&lt;img')
  })

  it('链接强制 target=_blank + noopener，防反向标签劫持', () => {
    const html = renderMarkdown('[示例](https://example.com)')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('javascript: 伪协议绝不生成可点链接', () => {
    // markdown-it 的 validateLink 直接拒绝 javascript: 目标，源文按纯文本渲染；
    // 纵有漏网 HTML 也会被 html:false 转义、DOMPurify 兜底。断言的是“无危险 href”，
    // 而不是要求连字面量都消失（纯文本里出现这几个字符无害）。
    const html = renderMarkdown('[点我](javascript:alert(1))')
    expect(html).not.toMatch(/href="javascript:/i)
    expect(html).not.toContain('<a')
  })
})
