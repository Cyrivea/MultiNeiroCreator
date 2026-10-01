// chat store 尾轮截断测试（UI1 重生成模式）：镜像后端 pop_last_turn 的同态规则
import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore, type AgentMessage } from '@/stores/chat'

function makeMessage(role: AgentMessage['role'], content: string): AgentMessage {
  return { id: `m-${Math.random()}`, role, content }
}

describe('useChatStore.truncateTailForRegenerate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('常规尾轮：截掉最后一条 user 之后的 assistant，保留原问', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage('user', '第一问'),
      makeMessage('assistant', '第一答'),
      makeMessage('user', '第二问'),
      makeMessage('assistant', '旧答案'),
    ]
    expect(store.truncateTailForRegenerate()).toBe(true)
    expect(store.messages.map((m) => m.content)).toEqual(['第一问', '第一答', '第二问'])
  })

  it('尾巴是连续多条 assistant（错误重试残留）也能截净', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage('user', '问'),
      makeMessage('assistant', '答'),
      makeMessage('assistant', '错误重试'),
    ]
    expect(store.truncateTailForRegenerate()).toBe(true)
    expect(store.messages).toHaveLength(1)
  })

  it('尾轮混有 system-notice 时拒绝截断（镜像后端 409 规则）', () => {
    const store = useChatStore()
    store.messages = [
      makeMessage('user', '问'),
      makeMessage('assistant', '答'),
      makeMessage('system-notice', '工作流已完成'),
    ]
    expect(store.truncateTailForRegenerate()).toBe(false)
    expect(store.messages).toHaveLength(3)
  })

  it('最后一条 user 之后没有回复时拒绝截断', () => {
    const store = useChatStore()
    store.messages = [makeMessage('user', '刚问还没答')]
    expect(store.truncateTailForRegenerate()).toBe(false)
  })

  it('完全没有 user 消息时拒绝截断', () => {
    const store = useChatStore()
    store.messages = [makeMessage('assistant', '无主之言')]
    expect(store.truncateTailForRegenerate()).toBe(false)
    expect(store.messages).toHaveLength(1)
  })
})
