// workflow store 的后端 Draft 同步：AI 命令进画布、参数桥接到 Block 实例、本地编辑回写服务器。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCreativeToolsStore } from '@/stores/creativeTools'
import { useToolRunsStore } from '@/stores/toolRuns'
import { useWorkflowStore, WORKFLOW_INPUT_ID, WORKFLOW_OUTPUT_ID } from '@/stores/workflow'
import type { WorkflowDraft } from '@/serve/workflow'

// store 的服务器同步链会引入 element-plus，本测试不验证网络调用，统一 mock 掉
vi.mock('@/utils/toast', () => ({
  ElMessage: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))
vi.mock('@/serve/workflow', () => ({
  getWorkflowDraft: vi.fn(),
  saveWorkflowDraft: vi.fn(),
  runWorkflow: vi.fn(),
}))
vi.mock('@/serve/agent', () => ({
  waitForAgentJob: vi.fn(),
}))

const AI_DRAFT: WorkflowDraft = {
  nodes: [
    {
      id: WORKFLOW_INPUT_ID,
      kind: 'endpoint',
      endpoint: 'input',
      name: '输入',
      x: 36,
      y: 280,
    },
    {
      id: 'workflow-node-lyrics-abc',
      kind: 'tool',
      toolId: 'assistant-lyrics-abc',
      type: 'lyrics',
      capability_id: 'lyrics.generate',
      name: '歌词生成',
      badge: '文字创作',
      description: '根据主题、情绪和曲风生成完整歌词草稿。',
      color: '#b7b7b7',
      x: 320,
      y: 280,
      params: { theme: '夏夜城市', style: '城市民谣', mood: '温柔、克制', language: '中文' },
      runStatus: 'succeeded',
      result: { format: 'markdown', content: '# 夏夜城市\n主歌内容' },
      error: null,
    },
    {
      id: WORKFLOW_OUTPUT_ID,
      kind: 'endpoint',
      endpoint: 'output',
      name: '输出',
      x: 900,
      y: 280,
    },
  ],
  edges: [
    { source: WORKFLOW_INPUT_ID, target: 'workflow-node-lyrics-abc' },
    { source: 'workflow-node-lyrics-abc', target: WORKFLOW_OUTPUT_ID },
  ],
}

describe('workflow store：后端 Draft 同步', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('应用 AI 的 Draft：端点不进入工具节点，连线与 revision 正常落地', () => {
    const store = useWorkflowStore()
    store.applyWorkflowSnapshot(AI_DRAFT, 3, 42)

    expect(store.nodes).toHaveLength(1)
    expect(store.nodes[0]?.id).toBe('workflow-node-lyrics-abc')
    expect(store.nodes[0]?.capabilityId).toBe('lyrics.generate')
    expect(store.edges).toHaveLength(2)
    expect(store.revision).toBe(3)
    expect(store.workflowId).toBe(42)
  })

  it('AI 管理的节点桥接成 Block 实例：参数面板可打开，运行结果有归属', () => {
    const store = useWorkflowStore()
    store.applyWorkflowSnapshot(AI_DRAFT, 3, 42)

    const tools = useCreativeToolsStore()
    expect(tools.instances.some((item) => item.id === 'assistant-lyrics-abc')).toBe(true)
    expect(tools.instances.find((item) => item.id === 'assistant-lyrics-abc')?.params.theme).toBe(
      '夏夜城市',
    )

    const runs = useToolRunsStore()
    expect(runs.records['assistant-lyrics-abc']?.status).toBe('succeeded')
    expect(runs.records['assistant-lyrics-abc']?.content).toContain('夏夜城市')
  })

  it('回写服务器时端点恢复为节点，手动添加的歌词节点自动带上 capability_id', () => {
    const store = useWorkflowStore()
    const tools = useCreativeToolsStore()
    const instance = tools.addTool('lyrics')
    store.syncWithTools(tools.instances)
    store.addNode(instance)

    const payload = store.buildDraftPayload()
    const payloadNode = payload.nodes.find((node) => node.toolId === instance.id)
    expect(payloadNode?.capability_id).toBe('lyrics.generate')
    expect(payload.nodes.some((node) => node.kind === 'endpoint')).toBe(true)
    expect(payload.nodes.filter((node) => node.endpoint === 'input')).toHaveLength(1)
  })

  it('B19：运行期间画布编辑全部无效（isRunning 守卫）', () => {
    const store = useWorkflowStore()
    const runningDraft: WorkflowDraft = {
      ...AI_DRAFT,
      nodes: AI_DRAFT.nodes.map((node) =>
        node.id === 'workflow-node-lyrics-abc' ? { ...node, runStatus: 'running' as const } : node,
      ),
    }
    store.applyWorkflowSnapshot(runningDraft, 3, 42)
    expect(store.isRunning).toBe(true)

    const lyricsId = 'workflow-node-lyrics-abc'
    const beforeEdges = store.edges.length
    // 连线 / 拆除 / 删除 / 拖动 / 撤销都被拒绝
    expect(store.addConnection(WORKFLOW_INPUT_ID, lyricsId)).toBe(false)
    store.removeConnection(WORKFLOW_INPUT_ID, lyricsId)
    expect(store.edges).toHaveLength(beforeEdges)
    store.removeNode(lyricsId)
    expect(store.nodes.map((n) => n.id)).toContain(lyricsId)
    store.moveNode(lyricsId, 9999, 9999)
    expect(store.nodes.find((n) => n.id === lyricsId)?.x).not.toBe(9999)
    store.moveEndpoint('input', 1, 1)
    expect(store.endpointPositions.input?.x).not.toBe(1)
    store.undo()
    expect(store.nodes.map((n) => n.id)).toContain(lyricsId)

    // 运行结束（轮询拿到终态）后自动解锁
    store.applyWorkflowSnapshot(AI_DRAFT, 4, 42)
    expect(store.isRunning).toBe(false)
    store.removeConnection(WORKFLOW_INPUT_ID, lyricsId)
    expect(store.edges).toHaveLength(beforeEdges - 1)
  })

  it('syncWithTools 不会删除 AI 管理但暂无左侧实例的节点（防回归）', () => {
    const store = useWorkflowStore()
    store.applyWorkflowSnapshot(AI_DRAFT, 3, 42)

    // 左侧工具列表为空时，AI 建的节点也不能被同步误删
    store.syncWithTools([])
    expect(store.nodes).toHaveLength(1)
    expect(store.edges).toHaveLength(2)
  })
})
