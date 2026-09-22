/**
 * 任务终态迁移检测（B28）。
 *
 * tasks store 每 3s 轮询一次 jobs 列表；本模块负责把"上一轮快照 vs 本轮列表"
 * 对比出哪些 job 刚从活跃（queued/running）落到终态（succeeded/failed/cancelled），
 * 是纯函数、无依赖，方便单测。
 */
import type { JobItem, JobStatus } from '@/serve/agent'

export const ACTIVE_JOB_STATUSES: ReadonlySet<JobStatus> = new Set(['queued', 'running'])
export const TERMINAL_JOB_STATUSES: ReadonlySet<JobStatus> = new Set([
  'succeeded',
  'failed',
  'cancelled',
])

/** job 终态广播事件名：tasks store 发出，WorkstationLayout 监听后刷新助手历史 */
export const JOB_TERMINAL_EVENT = 'neyria:job-terminal'

export interface JobTerminalTransition {
  job: JobItem
  status: Exclude<JobStatus, 'queued' | 'running'>
}

export function buildStatusSnapshot(jobs: JobItem[]): Map<string, JobStatus> {
  const snapshot = new Map<string, JobStatus>()
  for (const job of jobs) snapshot.set(job.id, job.status)
  return snapshot
}

/**
 * 检出终态迁移。
 * @param previous 上一轮快照；首轮加载时传空 Map（不通知——落地即终态的旧 job 不打扰用户）
 * @param nextJobs 本轮拉到的 jobs
 * @param suppressedIds 已由其他路径提醒过的 job（例：工具面板手动运行路径已有 toast+提示音），跳过防重复
 */
export function detectTerminalTransitions(
  previous: ReadonlyMap<string, JobStatus>,
  nextJobs: JobItem[],
  suppressedIds?: ReadonlySet<string>,
): JobTerminalTransition[] {
  const transitions: JobTerminalTransition[] = []
  for (const job of nextJobs) {
    if (!TERMINAL_JOB_STATUSES.has(job.status)) continue
    const prev = previous.get(job.id)
    // 只认"亲眼看它跑过"的 job：快照中不存在（新出现/漏帧）的不通知
    if (prev === undefined || !ACTIVE_JOB_STATUSES.has(prev)) continue
    if (suppressedIds?.has(job.id)) continue
    transitions.push({ job, status: job.status as JobTerminalTransition['status'] })
  }
  return transitions
}
