/**
 * 自动保存（D1 拆分第 3 步，todo §8.4）。
 * 定时把工程元数据 + 备份写入用户本地项目文件夹（File System Access API）；
 * 没有目录句柄时降级回手动模式并提示，绝不回退到服务器写文件（solved.md 第 6 条）。
 */
import { onBeforeUnmount } from 'vue'
import { ElMessage } from '@/utils/toast'
import { getCurrentTimestampParts } from '@/utils/datetime'
import {
  buildAutoSaveProjectName,
  buildBackupFileName,
  PROJECT_SUBDIRS,
  readLocalProjectMeta,
  requestProjectDirectoryHandle,
  writeLocalJsonFile,
  USER_CANCELLED_DIRECTORY_PICKER,
  type ProjectFileContent,
} from '@/utils/localProject'
import { markProjectSaved } from '@/serve/project'
import { useProjectStore, type AutoSaveMode } from '@/stores/project'

export interface SaveModeOption {
  label: string
  value: Exclude<AutoSaveMode, 'manual'>
  intervalMs: number
}

export const saveModeOptions: SaveModeOption[] = [
  { label: '每一分钟保存一次', value: 'auto-1m', intervalMs: 60 * 1000 },
  { label: '每三分钟保存一次', value: 'auto-3m', intervalMs: 3 * 60 * 1000 },
  { label: '每五分钟保存一次', value: 'auto-5m', intervalMs: 5 * 60 * 1000 },
  { label: '每十分钟保存一次', value: 'auto-10m', intervalMs: 10 * 60 * 1000 },
]

export const saveModeLabels: Record<AutoSaveMode, string> = {
  manual: '选择保存模式',
  'auto-1m': '每一分钟',
  'auto-3m': '每三分钟',
  'auto-5m': '每五分钟',
  'auto-10m': '每十分钟',
}

export function useAutoSave() {
  const projectStore = useProjectStore()

  let autoSaveTimer: number | null = null

  function clearTimer() {
    if (autoSaveTimer !== null) {
      window.clearInterval(autoSaveTimer)
      autoSaveTimer = null
    }
  }

  function syncTimer(mode: AutoSaveMode) {
    clearTimer()

    const activeOption = saveModeOptions.find((item) => item.value === mode)
    if (!activeOption) return

    autoSaveTimer = window.setInterval(() => {
      void runAutoBackup()
    }, activeOption.intervalMs)
  }

  /** 确保项目文件夹结构完整并刷新 project.json，返回最新元数据 */
  async function ensureLocalProjectWorkspace(saveMode: Exclude<AutoSaveMode, 'manual'>) {
    const directoryHandle = projectStore.directoryHandle
    if (!directoryHandle) {
      throw new Error('当前项目没有可写入的本地目录')
    }

    for (const directoryName of PROJECT_SUBDIRS) {
      await directoryHandle.getDirectoryHandle(directoryName, { create: true })
    }

    const now = getCurrentTimestampParts()
    const currentMeta = (await readLocalProjectMeta(directoryHandle)) || {}
    const projectName =
      (typeof currentMeta.name === 'string' && currentMeta.name.trim()) ||
      projectStore.name ||
      buildAutoSaveProjectName()

    const nextMeta: ProjectFileContent = {
      name: projectName,
      created_at: currentMeta.created_at || now.display,
      updated_at: now.display,
      save_mode: saveMode,
      version: currentMeta.version || '0.1.0',
      last_backup_at: currentMeta.last_backup_at,
    }

    await writeLocalJsonFile(directoryHandle, 'project.json', nextMeta)
    projectStore.setName(projectName)
    projectStore.setProjectPath(
      projectStore.projectPath || directoryHandle.name || '已选择项目文件夹',
    )

    // B29：这是真实写盘的时刻——保存成立，向服务端打戳（面板准入）。
    // fire-and-forget：打戳失败不中断保存，下次 tick 自然重试。
    if (typeof projectStore.id === 'number' && projectStore.id > 0) {
      void markProjectSaved(projectStore.id).catch(() => undefined)
    }

    return nextMeta
  }

  async function createLocalProjectBackup(saveMode: Exclude<AutoSaveMode, 'manual'>) {
    const directoryHandle = projectStore.directoryHandle
    if (!directoryHandle) {
      throw new Error('当前项目没有可写入的本地目录')
    }

    const now = getCurrentTimestampParts()
    const projectMeta = await ensureLocalProjectWorkspace(saveMode)
    const backupDirectoryHandle = await directoryHandle.getDirectoryHandle('backup', {
      create: true,
    })
    const backupPayload = {
      ...projectMeta,
      updated_at: now.display,
      save_mode: saveMode,
      last_backup_at: now.display,
      backup_created_at: now.display,
      backup_source_path: projectStore.projectPath || directoryHandle.name || '已选择项目文件夹',
    }

    await writeLocalJsonFile(directoryHandle, 'project.json', backupPayload)
    await writeLocalJsonFile(
      backupDirectoryHandle,
      buildBackupFileName(projectMeta.name, now.file),
      backupPayload,
    )
  }

  async function runAutoBackup() {
    const activeMode = projectStore.saveMode
    if (activeMode === 'manual') return

    if (!projectStore.directoryHandle) {
      clearTimer()
      projectStore.setSaveMode('manual')
      ElMessage.warning(
        '自动保存需要本地项目文件夹，请通过「打开项目」重新选择文件夹后再开启自动保存',
      )
      return
    }

    try {
      await createLocalProjectBackup(activeMode)
    } catch (error) {
      clearTimer()
      projectStore.setSaveMode('manual')

      if (error instanceof Error) {
        ElMessage.error(`自动备份失败：${error.message}`)
        return
      }

      ElMessage.error('自动备份失败，已停止当前保存模式')
    }
  }

  /** 用户切换保存模式：无句柄先弹目录选择器；成功后启动定时器 */
  async function selectSaveMode(option: SaveModeOption): Promise<boolean> {
    try {
      if (!projectStore.directoryHandle) {
        const handle = await requestProjectDirectoryHandle()
        projectStore.setDirectoryHandle(handle)
        projectStore.setProjectPath(handle?.name || projectStore.projectPath || '已选择项目文件夹')
      }

      await ensureLocalProjectWorkspace(option.value)
      projectStore.setSaveMode(option.value)
      syncTimer(option.value)
      ElMessage.success(`已切换为：${option.label}`)
      return true
    } catch (error) {
      if (error instanceof Error && error.message !== USER_CANCELLED_DIRECTORY_PICKER) {
        ElMessage.error(error.message || '设置自动保存模式失败')
      }
      return false
    }
  }

  onBeforeUnmount(() => {
    clearTimer()
  })

  return {
    syncTimer,
    clearTimer,
    selectSaveMode,
    ensureLocalProjectWorkspace,
  }
}
