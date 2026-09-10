import { ref } from 'vue'
import { defineStore } from 'pinia'

export type ToolRunStatus = 'idle' | 'running' | 'succeeded' | 'failed' | 'model_unavailable'

export interface ToolRunRecord {
  status: ToolRunStatus
  content: string | null
  error: string | null
  updatedAt: string
}

/** 每个 Block 实例的最近一次运行结果（key 为 creativeTools 的工具实例 ID）。 */
export const useToolRunsStore = defineStore('toolRuns', () => {
  const records = ref<Record<string, ToolRunRecord>>({})

  function setRecord(toolId: string, record: Omit<ToolRunRecord, 'updatedAt'>) {
    records.value[toolId] = { ...record, updatedAt: new Date().toISOString() }
  }

  function clearRecord(toolId: string) {
    delete records.value[toolId]
  }

  return { records, setRecord, clearRecord }
})
