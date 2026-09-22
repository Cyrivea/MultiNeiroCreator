import { describe, expect, it } from 'vitest'
import { buildStatusSnapshot, detectTerminalTransitions } from '@/utils/jobTransitions'
import type { JobItem, JobStatus } from '@/serve/agent'

function makeJob(id: string, status: JobStatus, type = 'workflow_run'): JobItem {
  return {
    id,
    type,
    status,
    user_id: 1,
    project_id: 1,
    payload: {},
    result: null,
    error: null,
    progress: 0,
    progress_message: null,
    attempts: 1,
    max_attempts: 1,
    cancel_requested: false,
    created_at: '2026-09-22T00:00:00Z',
    started_at: null,
    finished_at: null,
  }
}

describe('detectTerminalTransitions（B28 任务终态提醒）', () => {
  it('首轮加载（空快照）落地即终态的 job 不打扰用户', () => {
    const result = detectTerminalTransitions(new Map(), [makeJob('j1', 'succeeded')])
    expect(result).toEqual([])
  })

  it('亲眼看过 running → succeeded 的 job 会被检出', () => {
    const previous = buildStatusSnapshot([makeJob('j1', 'running')])
    const result = detectTerminalTransitions(previous, [makeJob('j1', 'succeeded')])
    expect(result).toEqual([{ job: expect.objectContaining({ id: 'j1' }), status: 'succeeded' }])
  })

  it('queued → failed 也会被检出', () => {
    const previous = buildStatusSnapshot([makeJob('j1', 'queued')])
    const result = detectTerminalTransitions(previous, [makeJob('j1', 'failed')])
    expect(result).toHaveLength(1)
    expect(result[0].status).toBe('failed')
  })

  it('中途出现（快照没有）直接是终态的 job 不通知——漏帧不会是用户关心的对象', () => {
    const previous = buildStatusSnapshot([makeJob('other', 'running')])
    const result = detectTerminalTransitions(previous, [makeJob('j1', 'succeeded')])
    expect(result).toEqual([])
  })

  it('终态 → 终态（重试失败重出现等）不重复通知', () => {
    const previous = buildStatusSnapshot([makeJob('j1', 'succeeded')])
    const result = detectTerminalTransitions(previous, [makeJob('j1', 'failed')])
    expect(result).toEqual([])
  })

  it('suppressedIds（手动运行路径已自己提醒）会跳过对应 job', () => {
    const previous = buildStatusSnapshot([makeJob('j1', 'running'), makeJob('j2', 'running')])
    const result = detectTerminalTransitions(
      previous,
      [makeJob('j1', 'succeeded'), makeJob('j2', 'succeeded')],
      new Set(['j1']),
    )
    expect(result).toHaveLength(1)
    expect(result[0].job.id).toBe('j2')
  })

  it('仍在跑的 job 不产生终态迁移', () => {
    const previous = buildStatusSnapshot([makeJob('j1', 'queued')])
    const result = detectTerminalTransitions(previous, [makeJob('j1', 'running')])
    expect(result).toEqual([])
  })
})
