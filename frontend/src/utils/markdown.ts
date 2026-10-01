/**
 * 对话 Markdown 渲染管线（UI1)：markdown-it 解析 → highlight.js 按需高亮
 * → DOMPurify 消毒。模型输出是不可信文本（C19 防注入面），渲染成 HTML
 * 必须过三关：md 层关闭 inline html（原样转义）→ highlight 只处理 fence 内容
 * → DOMPurify 剥掉一切事件属性/危险标签。
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/core'
import DOMPurify from 'dompurify'

// D4 教训（分包体积）：只注册聊天场景常见语言，避免全量 highlight.js 进包
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('css', css)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('python', python)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('yaml', yaml)

/** 常见别名归一化（模型常写 js/sh/html 这类简称） */
const LANG_ALIASES: Record<string, string> = {
  cjs: 'javascript',
  html: 'xml',
  js: 'javascript',
  mjs: 'javascript',
  py: 'python',
  sh: 'bash',
  shell: 'bash',
  text: 'plaintext',
  ts: 'typescript',
  vue: 'xml',
  yml: 'yaml',
  zsh: 'bash',
}

function normalizeLang(info: string): string {
  const raw = info.trim().split(/\s+/)[0].toLowerCase()
  return LANG_ALIASES[raw] ?? raw
}

const md = new MarkdownIt({
  // html: false —— 源文里的 HTML 标签一律按文本转义（第一道防线）
  html: false,
  linkify: true,
  // breaks: true —— 聊天习惯单行回车即换行，贴进 bubble 才不吞换行
  breaks: true,
})

// fence 渲染外挂：语言标签 + 一键复制按钮（open-webui 设计，Vue 重写）
const defaultFence = md.renderer.rules.fence!.bind(md.renderer.rules)
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const lang = normalizeLang(token.info)
  let code: string
  if (lang && hljs.getLanguage(lang)) {
    try {
      code = hljs.highlight(token.content, { language: lang }).value
    } catch {
      code = md.utils.escapeHtml(token.content)
    }
  } else {
    // 未知语言：纯文本转义，不冒充高亮
    return defaultFence(tokens, idx, options, env, self)
  }
  const label = md.utils.escapeHtml(lang || 'code')
  return (
    `<div class="md-codeblock">` +
    `<div class="md-codeblock-head">` +
    `<span class="md-codeblock-lang">${label}</span>` +
    `<button type="button" class="md-code-copy" aria-label="复制代码">复制</button>` +
    `</div>` +
    `<pre><code class="hljs language-${label}">${code}</code></pre>` +
    `</div>`
  )
}

// 消毒后统一外链姿态：新窗口打开 + 防反向标签劫持
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

/** 模型输出 → 安全 HTML。任何进入气泡的富文本只走这一个出口。 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  const html = md.render(text)
  return DOMPurify.sanitize(html, {
    // button 不在 DOMPurify 默认标签白名单里，显式放行（复制按钮是我们自产的）
    ADD_TAGS: ['button'],
    // class 默认即允许；这里显式禁掉一切 form/action 面，收紧外壳
    FORBID_TAGS: ['style', 'form', 'input', 'textarea', 'select'],
  })
}
