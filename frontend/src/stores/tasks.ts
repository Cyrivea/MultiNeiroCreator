import { computed, onScopeDispose, ref, watch, type Ref, type WatchHandle } from 'vue'
import { defineStore } from 'pinia'
import {
  cancelAgentJob,
  getAgentDocuments,
  getAgentJobs,
  retryAgentJob,
  type AgentDocument,
  type JobItem,
} from '@/serve/agent'
import { ElNotification } from '@/utils/notification'
import { playTaskCompleteSound } from '@/utils/notifySound'
import {
  buildStatusSnapshot,
  detectTerminalTransitions,
  JOB_TERMINAL_EVENT,
  type JobTerminalTransition,
} from '@/utils/jobTransitions'

export const useTaskStore = defineStore('tasks', () => {
  const documents = ref<AgentDocument[]>([])
  const jobs = ref<JobItem[]>([])
  const isLoading = ref(false)
  const error = ref('')
  let pollingTimer: number | null = null
  let stopProjectWatch: WatchHandle | null = null
  let requestToken = 0
  // B28：上一轮的 job 状态快照，用来检出"活跃→终态"迁移并提醒用户
  let jobStatusSnapshot = new Map<string, JobItem['status']>()
  // 已由其他路径提醒过的 job（工具面板手动运行已有 toast+提示音），轮询不再重复提醒
  const handledTerminalJobIds = new Set<string>()

  const activeJobs = computed(() =>
    jobs.value.filter((job) => job.status === 'queued' || job.status === 'running'),
  )
  const hasActiveTasks = computed(
    () =>
      activeJobs.value.length > 0 || documents.value.some((item) => item.status === 'processing'),
  )

  async function load(projectId: number | null | undefined) {
    const token = ++requestToken
    if (projectId == null) {
      documents.value = []
      jobs.value = []
      return
    }
    isLoading.value = true
    error.value = ''
    try {
      const [nextDocuments, nextJobs] = await Promise.all([
        getAgentDocuments(projectId),
        getAgentJobs(projectId),
      ])
      if (token !== requestToken) return
      notifyTerminalTransitions(nextJobs)
      documents.value = nextDocuments
      jobs.value = nextJobs
    } catch (cause) {
      if (token !== requestToken) return
      error.value = formatTaskError(cause)
    } finally {
      if (token === requestToken) isLoading.value = false
    }
  }

  function formatTaskError(cause: unknown) {
    if (!(cause instanceof Error)) return '任务状态加载失败'

    const response = (
      cause as Error & {
        response?: { status?: number; data?: { detail?: unknown } }
      }
    ).response
    const detail = response?.data?.detail
    const message = typeof detail === 'string' ? detail : cause.message
    return response?.status ? `请求失败（HTTP ${response.status}）：${message}` : message
  }

  /** 对比上轮快照，为刚落地的 job 弹通知 + 播提示音 + 广播终态事件（B28） */
  function notifyTerminalTransitions(nextJobs: JobItem[]) {
    const transitions = detectTerminalTransitions(
      jobStatusSnapshot,
      nextJobs,
      handledTerminalJobIds,
    )
    jobStatusSnapshot = buildStatusSnapshot(nextJobs)
    // 顺便清出不再存在于列表中的旧标记，防止 handled 集合无限增长
    if (handledTerminalJobIds.size) {
      for (const id of handledTerminalJobIds) {
        if (!jobStatusSnapshot.has(id)) handledTerminalJobIds.delete(id)
      }
    }
    for (const transition of transitions) notifyJobTerminal(transition)
  }

  function jobTypeLabel(type: string): string {
    switch (type) {
      case 'workflow_run':
        return '工作流'
      case 'document_index':
        return '文档索引'
      default:
        return '后台任务'
    }
  }

  function notifyJobTerminal({ job, status }: JobTerminalTransition) {
    handledTerminalJobIds.add(job.id)
    const label = jobTypeLabel(job.type)
    if (status === 'succeeded') {
      ElNotification({
        title: `${label}已完成`,
        message: job.progress_message || '结果已写回画布，可在画布和任务面板查看',
        type: 'success',
        duration: 6000,
      })
      playTaskCompleteSound('success')
    } else if (status === 'failed') {
      ElNotification({
        title: `${label}失败`,
        message: job.error || '请打开任务面板查看详情并重试',
        type: 'error',
        duration: 0, // 失败不自动消失，确保用户看得到
      })
      playTaskCompleteSound('error')
    }
    // cancelled 是用户自己点的，不弹窗、不播音
    window.dispatchEvent(new CustomEvent(JOB_TERMINAL_EVENT, { detail: { job, status } }))
  }

  /**
   * 其他路径（工具面板手动运行）自己弹了 toast 提醒，这里登记轮询防重复提醒。
   */
  function markTerminalNotified(jobId: string | null | undefined) {
    if (jobId) handledTerminalJobIds.add(jobId)
  }

  function startPolling(projectId: Ref<number | null>) {
    stopPolling()
    jobStatusSnapshot.clear()
    void load(projectId.value)
    stopProjectWatch?.()
    stopProjectWatch = watch(projectId, (next) => void load(next))
    // B21 修复：不能只在“已知有活跃任务”时才轮询——聊天里助手可以随时提交新任务，
    // 面板闲着时老逻辑会陷入鸡生蛋死锁，永远显示“0 个运行中”。
    // 改为无条件固定节拍轮询（3s）：空闲时成本可忽略，运行时比 1.5s 略慢但绝不会停摆。
    pollingTimer = window.setInterval(() => {
      void load(projectId.value)
    }, 3000)
  }

  function stopPolling() {
    if (stopProjectWatch !== null) {
      stopProjectWatch()
      stopProjectWatch = null
    }
    if (pollingTimer !== null) {
      window.clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  async function cancel(jobId: string) {
    await cancelAgentJob(jobId)
    await load(jobs.value.find((job) => job.id === jobId)?.project_id)
  }

  async function retry(jobId: string) {
    await retryAgentJob(jobId)
    await load(jobs.value.find((job) => job.id === jobId)?.project_id)
  }

  onScopeDispose(stopPolling)

  return {
    documents,
    jobs,
    isLoading,
    error,
    activeJobs,
    hasActiveTasks,
    load,
    startPolling,
    stopPolling,
    cancel,
    retry,
    markTerminalNotified,
  }
})
