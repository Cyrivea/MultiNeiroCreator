/**
 * 项目状态唯一真源（D2，todo §8.2）。
 * - 当前项目（id / 名称 / 路径标签 / 保存模式 / 本地目录句柄）全部收进 Pinia；
 * - 路由 query 只承载 project id，页面进入后按 id 调服务端详情恢复元数据（B3 的修复结论）；
 * - localStorage 仅作为"本地未登记项目"的引导缓存（目录句柄本身无法持久化），
 *   不再当作跨路由传参通道。
 * - store 挂在 Pinia 上，跨 WorkstationLayout 重挂载存活：本会话内打开的目录句柄
 *   不再因为切换路由而丢失。
 */
import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { readScoped, removeScoped, writeScoped } from '@/utils/storageScope'
import { getRecentProjects, type ProjectPayload } from '@/serve/project'
import { formatProjectTime } from '@/utils/datetime'
import type { BrowserDirectoryHandle } from '@/utils/localProject'

export type AutoSaveMode = 'manual' | 'auto-1m' | 'auto-3m' | 'auto-5m' | 'auto-10m'

export interface ActiveProjectSnapshot {
  id: number | null
  name: string
  projectPath: string | null
  saveMode: AutoSaveMode
}

export interface RecentProjectItem {
  id: number
  title: string
  meta: string
  projectPath: string
  saveMode: AutoSaveMode
}

const ACTIVE_PROJECT_STORAGE_KEY = 'mnc-active-project'

export function normalizeSaveMode(value?: string): AutoSaveMode {
  if (value === 'auto-1m' || value === 'auto-3m' || value === 'auto-5m' || value === 'auto-10m') {
    return value
  }

  return 'manual'
}

export const useProjectStore = defineStore('project', () => {
  const id = ref<number | null>(null)
  const name = ref('当前未命名工程')
  const projectPath = ref<string | null>(null)
  const saveMode = ref<AutoSaveMode>('manual')
  // 目录句柄是浏览器原生对象，深度响应式没有意义，用 shallowRef 持有
  const directoryHandle = shallowRef<BrowserDirectoryHandle | null>(null)
  const recentProjects = ref<RecentProjectItem[]>([])
  // 本地未登记项目占位 id（负数递减，避免与服务端 id 冲突）
  let localRecentProjectId = -1

  const displayName = computed(() => name.value || '当前未命名工程')
  const tabLabel = computed(() => name.value?.trim() || '选择项目')

  function nextLocalProjectId() {
    return localRecentProjectId--
  }

  function setActiveProject(
    project: ActiveProjectSnapshot,
    handle: BrowserDirectoryHandle | null = null,
  ) {
    // 同一项目且没有传入新句柄时保留已有句柄：路由驱动的重挂载不应弄丢本会话内已授权的目录
    const keepHandle = handle === null && project.id !== null && project.id === id.value
    id.value = project.id
    name.value = project.name
    projectPath.value = project.projectPath
    saveMode.value = project.saveMode
    if (!keepHandle) {
      directoryHandle.value = handle
    }
    persist()
  }

  function setDirectoryHandle(handle: BrowserDirectoryHandle | null) {
    directoryHandle.value = handle
  }

  function setProjectPath(path: string | null) {
    projectPath.value = path
  }

  function setName(value: string) {
    name.value = value
  }

  function setSaveMode(mode: AutoSaveMode) {
    saveMode.value = mode
    persist()
  }

  function persist() {
    if (!name.value || !projectPath.value) {
      removeScoped(ACTIVE_PROJECT_STORAGE_KEY)
      return
    }

    writeScoped(
      ACTIVE_PROJECT_STORAGE_KEY,
      JSON.stringify({
        id: id.value,
        name: name.value,
        projectPath: projectPath.value,
        saveMode: saveMode.value,
      }),
    )
  }

  /** 兜底恢复：仅用于路由里没有可用项目 id 的场景（如本地未登记项目） */
  function restoreFromStorage(): boolean {
    const raw = readScoped(ACTIVE_PROJECT_STORAGE_KEY)
    if (!raw) return false

    try {
      const parsed = JSON.parse(raw) as {
        id?: number | null
        name?: string
        projectPath?: string
        saveMode?: string
      }
      if (!parsed.name || !parsed.projectPath) return false

      const restoredId = typeof parsed.id === 'number' ? parsed.id : null
      setActiveProject({
        id: restoredId,
        name: parsed.name,
        projectPath: parsed.projectPath,
        saveMode: normalizeSaveMode(parsed.saveMode),
      })
      return true
    } catch {
      removeScoped(ACTIVE_PROJECT_STORAGE_KEY)
      return false
    }
  }

  function formatRecentProject(item: ProjectPayload): RecentProjectItem {
    return {
      id: item.id ?? nextLocalProjectId(),
      title: item.name,
      meta: `最近打开 · ${formatProjectTime(item.last_opened_at || item.updated_at)} · ${item.project_path}`,
      projectPath: item.project_path,
      saveMode: normalizeSaveMode(item.save_mode),
    }
  }

  async function loadRecentProjects() {
    const { items } = await getRecentProjects(8)
    recentProjects.value = items.map(formatRecentProject)
  }

  /** 打开/新建项目后把它顶到最近列表首位 */
  function upsertRecentProject(item: RecentProjectItem) {
    recentProjects.value = [
      item,
      ...recentProjects.value.filter(
        (existing) =>
          existing.id !== item.id &&
          (existing.title !== item.title || existing.projectPath !== item.projectPath),
      ),
    ].slice(0, 8)
  }

  return {
    id,
    name,
    projectPath,
    saveMode,
    directoryHandle,
    recentProjects,
    displayName,
    tabLabel,
    nextLocalProjectId,
    setActiveProject,
    setDirectoryHandle,
    setProjectPath,
    setName,
    setSaveMode,
    persist,
    restoreFromStorage,
    loadRecentProjects,
    upsertRecentProject,
  }
})
