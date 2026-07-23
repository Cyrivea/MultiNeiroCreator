<template>
  <div class="workstation-layout">
    <div class="app-shell">
      <div class="app-frame">
        <header class="topbar">
          <div class="topbar-left">
            <div class="title-row">
              <div class="app-title">MultiNeiroCreator</div>
            </div>
          </div>

          <div class="topbar-center">
            <div ref="topbarCombinedRef" class="topbar-combined">
              <div
                class="combined-left"
                :aria-expanded="isProjectOpen"
                @click.stop="toggleProjectPanel"
              >
                <span class="combined-label">{{ currentProjectTabLabel }}</span>
              </div>
              <div class="combined-divider" aria-hidden="true"></div>
              <div
                class="combined-right"
                :aria-expanded="isSearchOpen"
                @click.stop="toggleSearchPanel"
              >
                <span class="combined-right-text">搜索</span>
                <span class="search-signal" :class="{ active: isSearchOpen }" aria-hidden="true"></span>
              </div>

              <Transition name="panel-float">
                <div v-if="isProjectOpen" class="topbar-panel project-panel">
                  <div class="project-switcher-group">
                    <button class="project-switcher-option" type="button" @click="handleCreateProject">
                      <div class="project-option-title">新建项目</div>
                      <div class="project-option-meta">创建一个新的工程文件，并进入新的工作站界面。</div>
                    </button>
                    <button class="project-switcher-option" type="button" @click="handleOpenProjectPicker">
                      <div class="project-option-title">选择项目打开</div>
                      <div class="project-option-meta">从本地工程列表中选择一个已有项目继续创作。</div>
                    </button>
                  </div>

                  <div v-if="showRecentProjectsSection" class="project-switcher-group-label">最近打开</div>
                  <div v-if="showRecentProjectsSection" class="project-history-list">
                    <button
                      v-for="item in displayedRecentProjects"
                      :key="item.id"
                      class="project-switcher-option"
                      type="button"
                      @click="handleOpenRecentProject(item)"
                    >
                      <div class="project-option-title">{{ item.title }}</div>
                      <div class="project-option-meta">{{ item.meta }}</div>
                    </button>
                    <div v-if="showRecentProjectsEllipsis" class="project-history-ellipsis">...</div>
                  </div>
                </div>
              </Transition>

              <Transition name="panel-float">
                <div v-if="isSearchOpen" class="topbar-panel search-panel">
                  <div class="search-panel-title">{{ searchPanelTitle }}</div>
                  <input
                    v-model="searchQuery"
                    type="text"
                    placeholder=""
                    @focus="openSearchPanel"
                    @click.stop="openSearchPanel"
                  />
                  <div class="search-result-list">
                    <button
                      v-for="item in filteredSearchResults"
                      :key="`${item.title}-${item.meta}`"
                      class="search-result-item"
                      type="button"
                    >
                      <div>{{ item.title }}</div>
                      <div class="search-result-meta">{{ item.meta }}</div>
                    </button>
                  </div>
                  <div v-if="showSearchEllipsis" class="search-result-ellipsis">...</div>
                </div>
              </Transition>
            </div>
          </div>

          <div class="topbar-right">
            <div class="status-row">
              <div ref="saveModeWrapRef" class="status-button-wrap">
                <button
                  class="status-button"
                  type="button"
                  :aria-expanded="isSaveModeOpen"
                  @click.stop="toggleSaveMode"
                >
                  <Transition name="save-mode-label" mode="out-in">
                    <span :key="currentSaveModeLabel" class="status-button-label">{{ currentSaveModeLabel }}</span>
                  </Transition>
                  <span>▾</span>
                </button>
                <Transition name="panel-float">
                  <div v-if="isSaveModeOpen" class="status-panel">
                    <button
                      v-for="item in saveModeOptions"
                      :key="item.value"
                      class="status-panel-option"
                      type="button"
                      :disabled="isSaveModeApplying"
                      @click="handleSelectSaveMode(item)"
                    >
                      {{ item.label }}
                    </button>
                  </div>
                </Transition>
              </div>
            </div>
            <div class="window-controls" aria-hidden="true">
              <div class="window-dot"></div>
              <div class="window-dot"></div>
              <div class="window-dot"></div>
            </div>
          </div>
        </header>

        <main class="main-grid">
          <aside class="left-column">
            <div class="icon-rail" aria-label="Side navigation">
              <button class="icon-button active" title="Explorer" type="button">☰</button>
              <div class="rail-spacer"></div>
              <button class="icon-button" title="Settings" type="button">⚙</button>
            </div>

            <div class="sidebar-stack">
              <div class="sidebar-workspace">
                <section class="section-card">
                  <div class="section-body">
                    <button class="add-tool-large" type="button" @click="openToolModal">
                      添加创作工具 +
                    </button>
                  </div>
                </section>
              </div>
            </div>
          </aside>

          <section class="center-column">
            <div class="canvas-surface">
              <div class="canvas-area">
                <div class="canvas-center">
                  <div class="canvas-callout">创作区，等待加载工具。</div>
                </div>
              </div>
            </div>
          </section>

          <aside class="right-column">
            <div class="assistant-panel">
              <div class="assistant-head">
                <div class="assistant-head-top">
                  <div class="assistant-head-copy">
                    <div class="assistant-title-row">
                      <div class="assistant-title">Neyria</div>
                      <div class="assistant-presence" aria-hidden="true"></div>
                    </div>
                    <div class="assistant-meta">为音乐续写篇章</div>
                  </div>
                  <div class="window-controls" aria-hidden="true">
                    <div class="window-dot"></div>
                    <div class="window-dot"></div>
                    <div class="window-dot"></div>
                  </div>
                </div>
                <div class="assistant-head-divider" aria-hidden="true"></div>
              </div>

              <div ref="assistantBodyRef" class="assistant-body">
                <div v-if="!agentMessages.length" class="agent-empty">
                  <div class="agent-empty-orbit" aria-hidden="true"></div>
                  <div class="agent-empty-title">Neyria 已就绪</div>
                  <div class="agent-empty-meta">现在可以直接描述你的创作目标、风格、结构或具体问题。</div>
                </div>

                <TransitionGroup v-else name="agent-message-float" tag="div" class="agent-message-list">
                  <div
                    v-for="message in agentMessages"
                    :key="message.id"
                    class="agent-message"
                    :class="[`is-${message.role}`, { 'is-error': message.isError }]"
                  >
                    <div class="agent-message-meta">
                      <div v-if="message.toolName" class="agent-tool-chip">{{ formatToolName(message.toolName) }}</div>
                    </div>
                    <div
                      class="agent-message-bubble"
                      :class="{ 'is-pending': message.isPending && !message.content }"
                    >
                      <template v-if="message.isPending && !message.content">
                        <span class="agent-thinking-wave" aria-label="Thinking">
                          <span
                            v-for="(letter, index) in thinkingLetters"
                            :key="`${message.id}-${index}`"
                            class="agent-thinking-letter"
                            :style="{ animationDelay: `${index * 0.06}s` }"
                          >
                            {{ letter }}
                          </span>
                        </span>
                      </template>
                      <template v-else>{{ message.content }}</template>
                    </div>
                  </div>
                </TransitionGroup>

                <div v-if="isAgentSending" class="agent-status-line">
                  <span class="agent-status-pulse" aria-hidden="true"></span>
                  {{ agentThinkingStatusText }}
                </div>
              </div>

              <div class="composer-wrap">
                <div class="input-composer">
                  <textarea
                    v-model="agentInput"
                    placeholder="我来帮你实现想法！"
                    :disabled="isAgentSending"
                    @keydown="handleComposerKeydown"
                  ></textarea>
                  <div class="input-composer-toolbar">
                    <div class="composer-toolbar-left">
                      <button class="composer-tool" title="附件功能暂未开放" aria-label="附件" type="button">
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          aria-hidden="true"
                        >
                          <path d="M21.44 11.05 12.2 20.29a5 5 0 0 1-7.07-7.07l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.48-8.49" />
                        </svg>
                      </button>
                    </div>
                    <div class="composer-toolbar-right">
                      <button class="composer-tool" title="语音功能暂未开放" type="button">◉</button>
                      <button class="composer-model-button" title="当前模型占位" type="button">
                        Auto ▾
                      </button>
                      <button
                        class="composer-action primary"
                        title="Send"
                        type="button"
                        :disabled="isAgentSending || !agentInput.trim()"
                        @click="sendAgentMessage"
                      >
                        <span class="composer-action-icon">{{ isAgentSending ? '...' : '↑' }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </main>
      </div>
    </div>

    <Transition name="modal-fade">
      <div
        v-if="isToolModalOpen"
        class="modal-overlay"
        :aria-hidden="!isToolModalOpen"
        @click.self="closeToolModal"
      >
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
          <div class="modal-head">
            <div>
              <div id="modalTitle" class="modal-title">添加工具</div>
              <div class="modal-caption">为当前项目追加新的创作模块或 Agent 插件。</div>
            </div>
            <button class="modal-close" type="button" aria-label="Close" @click="closeToolModal">
              ✕
            </button>
          </div>
          <div class="modal-body">
            <button
              v-for="item in toolModalOptions"
              :key="item.title"
              class="modal-option"
              type="button"
            >
              <div class="message-title">{{ item.title }}</div>
              <div class="modal-option-sub">{{ item.description }}</div>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="modal-fade">
      <div
        v-if="isCreateProjectModalOpen"
        class="modal-overlay"
        :aria-hidden="!isCreateProjectModalOpen"
        @click.self="closeCreateProjectFlow"
      >
        <div class="modal-card project-create-modal" role="dialog" aria-modal="true" aria-labelledby="createProjectTitle">
          <div class="modal-head">
            <div>
              <div id="createProjectTitle" class="modal-title">
                {{ createProjectStep === 1 ? '新建项目' : '保存当前工程' }}
              </div>
              <div class="modal-caption">
                {{ createProjectStep === 1 ? '先为新的工程文件命名。' : '在进入新项目之前，先确认当前工程的保存方式。' }}
              </div>
            </div>
          </div>

          <Transition name="modal-swap" mode="out-in">
            <div v-if="createProjectStep === 1" key="create-step-1" class="modal-body project-create-body">
              <label class="project-create-label" for="newProjectName">项目名称</label>
              <input
                id="newProjectName"
                v-model="newProjectName"
                class="project-create-input"
                type="text"
                maxlength="120"
                placeholder="请输入新项目名称"
              />
              <div class="project-create-actions">
                <button class="project-secondary-button" type="button" @click="closeCreateProjectFlow">取消</button>
                <button class="project-primary-button" type="button" @click="goToCreateProjectStepTwo">确定</button>
              </div>
            </div>

            <div v-else key="create-step-2" class="modal-body project-create-body">
              <div class="project-create-summary">
                <div class="project-summary-title">是否保存当前工程</div>
                <div class="project-summary-meta">
                  当前工程：{{ currentProjectDisplayName }}
                </div>
              </div>
              <div class="project-create-actions project-create-actions--three">
                <button class="project-secondary-button" type="button" @click="backToCreateProjectStepOne">取消</button>
                <button class="project-danger-button" type="button" @click="openDiscardProjectConfirm">不保存</button>
                <button class="project-primary-button" type="button" :disabled="isCreatingProject" @click="saveCurrentProjectAndCreate">
                  {{ isCreatingProject ? '处理中...' : '确定' }}
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </Transition>

    <Transition name="modal-fade">
      <div
        v-if="isDiscardProjectConfirmOpen"
        class="modal-overlay"
        :aria-hidden="!isDiscardProjectConfirmOpen"
        @click.self="closeDiscardProjectConfirm"
      >
        <div class="modal-card project-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="discardProjectTitle">
          <div class="modal-head">
            <div>
              <div id="discardProjectTitle" class="modal-title">确认不保存</div>
            </div>
          </div>
          <div class="modal-body project-create-body">
            <div class="warning-callout">
              <div class="warning-icon" aria-hidden="true">!</div>
              <div class="warning-content">
                <div class="warning-title">此操作将不保存当前项目所有操作</div>
                <div class="warning-message">确认后将直接进入新项目，当前未落盘内容不会被保留。</div>
              </div>
            </div>
            <div class="project-create-actions">
              <button class="project-secondary-button" type="button" @click="closeDiscardProjectConfirm">取消</button>
              <button class="project-danger-button" type="button" :disabled="isCreatingProject" @click="discardCurrentProjectAndCreate">
                {{ isCreatingProject ? '处理中...' : '确定' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="modal-fade">
      <div
        v-if="isProjectWarningOpen"
        class="modal-overlay"
        :aria-hidden="!isProjectWarningOpen"
        @click.self="closeProjectWarning"
      >
        <div class="modal-card project-warning-modal" role="alertdialog" aria-modal="true" aria-labelledby="projectWarningTitle">
          <div class="modal-head">
            <div>
              <div id="projectWarningTitle" class="modal-title">{{ projectWarningTitle }}</div>
            </div>
          </div>
          <div class="modal-body project-create-body">
            <div class="warning-callout">
              <div class="warning-icon" aria-hidden="true">!</div>
              <div class="warning-content">
                <div class="warning-title">{{ projectWarningTitle }}</div>
                <div class="warning-message">{{ projectWarningMessage }}</div>
              </div>
            </div>
            <div class="project-warning-actions">
              <button class="project-danger-button" type="button" @click="closeProjectWarning">确定</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAgentHistory, streamAgentChat, type AgentHistoryItem } from '@/serve/agent'
import { createAutoBackup, createProject, ensureAutoSaveProject, getRecentProjects, type ProjectPayload } from '@/serve/project'
import { useLoadingStore } from '@/stores/loading'

// 真实进度接管：让工作站初始化阶段能推动 loadingStore.setProgress()，
// 覆盖层在 realProgress > 0 时无缝从内置 rAF 切到真实进度。
const loadingStore = useLoadingStore()
const route = useRoute()
const router = useRouter()

// emit:ready —— 核心资源初始化完成时通知外层淡出覆盖层。
// 该事件与"是否加载成功"解耦（成功/失败都会发出），由父级 Workstation.vue 负责真正收起。
const emit = defineEmits<{ (e: 'ready'): void }>()

interface SearchItem {
  title: string
  meta: string
}

interface ToolModalOption {
  title: string
  description: string
}

interface AgentMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolName?: string | null
  isError?: boolean
  isPending?: boolean
}

interface RecentProjectItem {
  id: number
  title: string
  meta: string
  projectPath: string
  saveMode: AutoSaveMode
}

interface ProjectFileContent {
  id?: number
  name: string
  save_mode?: string
  created_at?: string
  created_at?: string
  updated_at?: string
  version?: string
  last_backup_at?: string
}

interface BrowserDirectoryHandle {
  name?: string
  getFileHandle: (name: string, options?: { create?: boolean }) => Promise<BrowserFileHandle>
  getDirectoryHandle: (name: string, options?: { create?: boolean }) => Promise<BrowserDirectoryHandle>
}

interface BrowserFileHandle {
  getFile: () => Promise<File>
  createWritable: () => Promise<BrowserWritableFileStream>
}

interface BrowserWritableFileStream {
  write: (data: string) => Promise<void>
  close: () => Promise<void>
}

type AutoSaveMode = 'manual' | 'auto-1m' | 'auto-3m' | 'auto-5m' | 'auto-10m'

interface SaveModeOption {
  label: string
  value: Exclude<AutoSaveMode, 'manual'>
  intervalMs: number
}

const isToolModalOpen = ref(false)
const isProjectOpen = ref(false)
const isSearchOpen = ref(false)
const isSaveModeOpen = ref(false)
const isCreateProjectModalOpen = ref(false)
const isDiscardProjectConfirmOpen = ref(false)
const isProjectWarningOpen = ref(false)
const searchQuery = ref('')
const createProjectStep = ref<1 | 2>(1)
const newProjectName = ref('')
const isCreatingProject = ref(false)
const currentProjectId = ref<number | null>(null)
const currentProjectName = ref('当前未命名工程')
const currentProjectPath = ref<string | null>(null)
const currentProjectDirectoryHandle = ref<BrowserDirectoryHandle | null>(null)
const currentSaveMode = ref<AutoSaveMode>('manual')
const projectWarningTitle = ref('')
const projectWarningMessage = ref('')
const assistantBodyRef = ref<HTMLElement | null>(null)
const agentInput = ref('')
const agentMessages = ref<AgentMessage[]>([])
const isAgentSending = ref(false)
const activeToolName = ref('')
const isAgentThinking = ref(false)
const hasAgentStartedReplying = ref(false)
const agentThinkingSeconds = ref(0)
const isSaveModeApplying = ref(false)
const AGENT_FIRST_TOKEN_TIMEOUT_MS = 10000
const thinkingLetters = 'THINKING'.split('')
const ACTIVE_PROJECT_STORAGE_KEY = 'mnc-active-project'
let localRecentProjectId = -1
let localAgentMessageId = 0
let agentPanelLoadToken = 0
let chatAbortController: AbortController | null = null
let autoSaveTimer: number | null = null
let agentThinkingTimer: number | null = null
let agentFirstTokenTimeout: number | null = null

const topbarCombinedRef = ref<HTMLElement | null>(null)
const saveModeWrapRef = ref<HTMLElement | null>(null)

const saveModeOptions: SaveModeOption[] = [
  { label: '每一分钟保存一次', value: 'auto-1m', intervalMs: 60 * 1000 },
  { label: '每三分钟保存一次', value: 'auto-3m', intervalMs: 3 * 60 * 1000 },
  { label: '每五分钟保存一次', value: 'auto-5m', intervalMs: 5 * 60 * 1000 },
  { label: '每十分钟保存一次', value: 'auto-10m', intervalMs: 10 * 60 * 1000 },
]
const recentProjects = ref<RecentProjectItem[]>([])
const toolModalOptions: ToolModalOption[] = [
  {
    title: 'Plugin Module',
    description: '挂载新的创作能力，例如编曲、混音、PV 或 Live2D Agent。',
  },
  {
    title: 'Import Workflow',
    description: '导入已有工作流模板，把当前项目接入新的流水线。',
  },
  {
    title: 'Create Sandbox',
    description: '建立独立实验区，用于测试新模型、新参数和新模块。',
  },
]

const searchIndex: SearchItem[] = [
  { title: '选择项目', meta: '顶部栏 · 项目切换' },
  { title: '搜索', meta: '顶部栏 · 全局检索入口' },
  { title: '工具', meta: '左侧栏 · Creative Module Library' },
  { title: '添加工具', meta: '左侧栏 · 工具模块操作' },
  { title: 'Composer Agent', meta: '左侧栏 · 创作模块' },
  { title: 'Lyrics Agent', meta: '左侧栏 · 创作模块' },
  { title: 'Visual Agent', meta: '左侧栏 · 创作模块' },
  { title: '创作区', meta: '中间区域 · 工作区' },
  { title: 'Neyria', meta: '右侧栏 · AI 助手面板' },
  { title: '上传文件', meta: '右下输入区 · 功能按钮' },
  { title: '语音对话', meta: '右下输入区 · 功能按钮' },
  { title: '切换模型', meta: '右下输入区 · Auto 按钮' },
]

const filteredSearchResults = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return []

  return searchIndex
    .filter(item => `${item.title} ${item.meta}`.toLowerCase().includes(keyword))
    .slice(0, 5)
})

const searchPanelTitle = computed(() => {
  if (!searchQuery.value.trim()) return '未搜索到相关内容'
  return filteredSearchResults.value.length ? '搜索到以下相关内容' : '未搜索到相关内容'
})

const showSearchEllipsis = computed(() => !!searchQuery.value.trim() && filteredSearchResults.value.length > 0)
const displayedRecentProjects = computed(() => recentProjects.value.slice(0, 3))
const showRecentProjectsSection = computed(() => recentProjects.value.length > 0)
const showRecentProjectsEllipsis = computed(() => recentProjects.value.length > 3)
const currentSaveModeLabel = computed(() => {
  const labelMap: Record<AutoSaveMode, string> = {
    manual: '选择保存模式',
    'auto-1m': '每一分钟',
    'auto-3m': '每三分钟',
    'auto-5m': '每五分钟',
    'auto-10m': '每十分钟',
  }

  return labelMap[currentSaveMode.value]
})

const currentProjectTabLabel = computed(() => {
  return currentProjectName.value?.trim() || '选择项目'
})

function openToolModal() {
  isToolModalOpen.value = true
}

function closeToolModal() {
  isToolModalOpen.value = false
}

function resetWorkspaceTransientState() {
  isProjectOpen.value = false
  isSearchOpen.value = false
  isSaveModeOpen.value = false
  searchQuery.value = ''
  agentInput.value = ''
  activeToolName.value = ''
  chatAbortController?.abort('PROJECT_SWITCH')
  chatAbortController = null
  stopAgentThinking()
  isAgentSending.value = false
  agentMessages.value = []
}

function initializeEmptyAgentPanel() {
  agentPanelLoadToken += 1
  chatAbortController?.abort('PROJECT_SWITCH')
  chatAbortController = null
  stopAgentThinking()
  isAgentSending.value = false
  hasAgentStartedReplying.value = false
  activeToolName.value = ''
  agentInput.value = ''
  agentMessages.value = []
}

async function navigateToProject(projectId: number | null) {
  const currentProjectQuery = typeof route.query.project === 'string' ? route.query.project : null
  const nextProjectQuery = projectId != null ? String(projectId) : 'default'
  if (currentProjectQuery === nextProjectQuery) {
    initializeEmptyAgentPanel()
    resetWorkspaceTransientState()
    void loadAgentPanel()
    return
  }

  await router.replace({
    path: '/workstation',
    query: projectId != null ? { project: String(projectId) } : { project: 'default' },
  })
}

async function toggleProjectPanel() {
  const nextOpen = !isProjectOpen.value
  isProjectOpen.value = nextOpen
  isSearchOpen.value = false

  if (nextOpen) {
    await loadRecentProjects()
  }
}

async function handleCreateProject() {
  isProjectOpen.value = false
  isCreateProjectModalOpen.value = true
  isDiscardProjectConfirmOpen.value = false
  createProjectStep.value = 1
  newProjectName.value = ''
}

async function handleOpenProjectPicker() {
  isProjectOpen.value = false

  const directoryPicker = (window as Window & {
    showDirectoryPicker?: () => Promise<BrowserDirectoryHandle>
  }).showDirectoryPicker

  if (!directoryPicker) {
    openProjectWarning('当前浏览器不支持', '请选择 Chromium 内核浏览器后再打开本地项目文件夹。')
    return
  }

  try {
    const directoryHandle = await directoryPicker()
    const project = await readProjectDirectory(directoryHandle)
    applyOpenedProject(project, directoryHandle)
    ElMessage.success(`已打开项目：${project.name}`)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return

    if (error instanceof Error) {
      if (error.message === 'INVALID_PROJECT_DIRECTORY') {
        openProjectWarning('项目文件不合法', '所选文件夹中未找到可用的 `project.json` 项目文件。')
        return
      }
      if (error.message === 'INVALID_PROJECT_FILE') {
        openProjectWarning('项目文件不合法', '检测到 `project.json`，但内容格式不符合当前项目要求。')
        return
      }
    }

    openProjectWarning('打开项目失败', '本地项目读取失败，请重新选择一个有效的项目文件夹。')
  }
}

function handleOpenRecentProject(item: RecentProjectItem) {
  isProjectOpen.value = false
  currentProjectId.value = item.id > 0 ? item.id : null
  currentProjectName.value = item.title
  currentProjectPath.value = item.projectPath
  currentProjectDirectoryHandle.value = null
  currentSaveMode.value = item.saveMode
  syncAutoSaveTimer(item.saveMode)
  persistActiveProject()
  initializeEmptyAgentPanel()
  resetWorkspaceTransientState()
  void navigateToProject(currentProjectId.value)
  ElMessage.success(`已打开项目：${item.title}`)
}

function closeCreateProjectFlow() {
  if (isCreatingProject.value) return
  isCreateProjectModalOpen.value = false
  isDiscardProjectConfirmOpen.value = false
  createProjectStep.value = 1
  newProjectName.value = ''
}

function goToCreateProjectStepTwo() {
  if (!newProjectName.value.trim()) {
    ElMessage.warning('请先输入新项目名称')
    return
  }
  createProjectStep.value = 2
}

function backToCreateProjectStepOne() {
  createProjectStep.value = 1
}

function openDiscardProjectConfirm() {
  isDiscardProjectConfirmOpen.value = true
}

function closeDiscardProjectConfirm() {
  if (isCreatingProject.value) return
  isDiscardProjectConfirmOpen.value = false
}

function openProjectWarning(title: string, message: string) {
  projectWarningTitle.value = title
  projectWarningMessage.value = message
  isProjectWarningOpen.value = true
}

function closeProjectWarning() {
  isProjectWarningOpen.value = false
}

async function saveCurrentProjectAndCreate() {
  if (isCreatingProject.value) return
  isCreatingProject.value = true
  try {
    await ensureCurrentProjectSaved()
    await createNamedProject()
  } catch (error) {
    if (error instanceof Error && error.message !== 'USER_CANCELLED_DIRECTORY_PICKER') {
      ElMessage.error(error.message || '保存当前工程失败')
    }
  } finally {
    isCreatingProject.value = false
  }
}

async function discardCurrentProjectAndCreate() {
  if (isCreatingProject.value) return
  isCreatingProject.value = true
  try {
    await createNamedProject()
  } catch (error) {
    if (error instanceof Error) {
      ElMessage.error(error.message || '创建项目失败')
    }
  } finally {
    isCreatingProject.value = false
  }
}

async function createNamedProject() {
  const { project } = await createProject(newProjectName.value.trim())
  recentProjects.value = [
    formatRecentProject(project),
    ...recentProjects.value.filter(item => item.id !== project.id),
  ].slice(0, 8)
  currentProjectId.value = project.id ?? null
  currentProjectName.value = project.name
  currentProjectPath.value = project.project_path
  currentProjectDirectoryHandle.value = null
  currentSaveMode.value = normalizeSaveMode(project.save_mode)
  syncAutoSaveTimer(currentSaveMode.value)
  persistActiveProject()
  initializeEmptyAgentPanel()
  resetWorkspaceTransientState()
  closeCreateProjectFlow()
  ElMessage.success(`已创建项目：${project.name}`)
  await navigateToProject(currentProjectId.value)
}

async function ensureCurrentProjectSaved() {
  if (currentProjectPath.value) {
    return
  }

  const directoryPicker = (window as Window & {
    showDirectoryPicker?: () => Promise<{ name?: string }>
  }).showDirectoryPicker

  if (!directoryPicker) {
    throw new Error('当前浏览器不支持选择文件夹，请使用 Chromium 内核浏览器')
  }

  try {
    const handle = await directoryPicker()
    currentProjectDirectoryHandle.value = handle as BrowserDirectoryHandle
    currentProjectPath.value = handle?.name || '已选择文件夹'
    ElMessage.success('已选择当前工程保存位置')
  } catch {
    throw new Error('USER_CANCELLED_DIRECTORY_PICKER')
  }
}

async function readProjectDirectory(directoryHandle: BrowserDirectoryHandle) {
  let projectFileHandle: BrowserFileHandle

  try {
    projectFileHandle = await directoryHandle.getFileHandle('project.json')
  } catch {
    throw new Error('INVALID_PROJECT_DIRECTORY')
  }

  try {
    const file = await projectFileHandle.getFile()
    const rawText = await file.text()
    const parsed = JSON.parse(rawText) as Partial<ProjectFileContent>

    if (typeof parsed.name !== 'string' || !parsed.name.trim()) {
      throw new Error('INVALID_PROJECT_FILE')
    }

    return {
      id: typeof parsed.id === 'number' ? parsed.id : undefined,
      name: parsed.name.trim(),
      projectPath: directoryHandle.name || '已选择项目文件夹',
      saveMode: typeof parsed.save_mode === 'string' ? parsed.save_mode : 'manual',
    }
  } catch (error) {
    if (error instanceof Error && error.message === 'INVALID_PROJECT_FILE') {
      throw error
    }

    throw new Error('INVALID_PROJECT_FILE')
  }
}

function applyOpenedProject(
  project: { id?: number; name: string; projectPath: string; saveMode: string },
  directoryHandle: BrowserDirectoryHandle | null = null,
) {
  currentProjectId.value = project.id ?? null
  currentProjectName.value = project.name
  currentProjectPath.value = project.projectPath
  currentProjectDirectoryHandle.value = directoryHandle
  currentSaveMode.value = normalizeSaveMode(project.saveMode)
  syncAutoSaveTimer(currentSaveMode.value)
  initializeEmptyAgentPanel()

  const nextItem: RecentProjectItem = {
    id: project.id ?? localRecentProjectId--,
    title: project.name,
    meta: `最近打开 · 刚刚 · ${project.projectPath}`,
    projectPath: project.projectPath,
    saveMode: normalizeSaveMode(project.saveMode),
  }

  recentProjects.value = [
    nextItem,
    ...recentProjects.value.filter(item => item.title !== nextItem.title || item.projectPath !== nextItem.projectPath),
  ].slice(0, 8)
  persistActiveProject()
  resetWorkspaceTransientState()
  void navigateToProject(currentProjectId.value)
}

async function loadRecentProjects() {
  const { items } = await getRecentProjects(8)
  recentProjects.value = items.map(formatRecentProject)
}

function formatRecentProject(item: ProjectPayload): RecentProjectItem {
  return {
    id: item.id ?? localRecentProjectId--,
    title: item.name,
    meta: `最近打开 · ${formatProjectTime(item.last_opened_at || item.updated_at)} · ${item.project_path}`,
    projectPath: item.project_path,
    saveMode: normalizeSaveMode(item.save_mode),
  }
}

function formatProjectTime(value: string): string {
  const parsed = new Date(value.replace(' ', 'T'))
  if (Number.isNaN(parsed.getTime())) return value

  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const date = String(parsed.getDate()).padStart(2, '0')
  const hours = String(parsed.getHours()).padStart(2, '0')
  const minutes = String(parsed.getMinutes()).padStart(2, '0')
  return `${month}-${date} ${hours}:${minutes}`
}

function persistActiveProject() {
  if (!currentProjectName.value || !currentProjectPath.value) {
    localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY)
    return
  }

  localStorage.setItem(
    ACTIVE_PROJECT_STORAGE_KEY,
    JSON.stringify({
      id: currentProjectId.value,
      name: currentProjectName.value,
      projectPath: currentProjectPath.value,
      saveMode: currentSaveMode.value,
    }),
  )
}

function restoreActiveProjectFromStorage() {
  const raw = localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY)
  if (!raw) return false

  try {
    const parsed = JSON.parse(raw) as {
      id?: number | null
      name?: string
      projectPath?: string
      saveMode?: string
    }
    if (!parsed.name || !parsed.projectPath) return false

    currentProjectId.value = typeof parsed.id === 'number' ? parsed.id : null
    currentProjectName.value = parsed.name
    currentProjectPath.value = parsed.projectPath
    currentProjectDirectoryHandle.value = null
    currentSaveMode.value = normalizeSaveMode(parsed.saveMode)
    syncAutoSaveTimer(currentSaveMode.value)
    return true
  } catch {
    localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY)
    return false
  }
}

const currentProjectDisplayName = computed(() => {
  return currentProjectName.value || '当前未命名工程'
})

function normalizeSaveMode(value?: string): AutoSaveMode {
  if (value === 'auto-1m' || value === 'auto-3m' || value === 'auto-5m' || value === 'auto-10m') {
    return value
  }

  return 'manual'
}

function isAbsoluteProjectPath(path: string | null) {
  if (!path) return false
  return /^[A-Za-z]:[\\/]/.test(path) || /^\\\\/.test(path)
}

function getCurrentTimestampParts(date = new Date()) {
  const year = String(date.getFullYear())
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  return {
    display: `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`,
    file: `${year}${month}${day}_${hours}${minutes}${seconds}`,
  }
}

function buildAutoSaveProjectName() {
  const now = getCurrentTimestampParts()
  return `未命名项目 ${now.file.replace('_', '-')}`
}

function buildBackupFileName(projectName: string, timestamp: string) {
  const safeName = projectName.replace(/[<>:"/\\|?*\u0000-\u001f]+/g, '_').trim() || 'project'
  return `${safeName}_${timestamp}.json`
}

function getSaveModeOption(mode: AutoSaveMode) {
  return saveModeOptions.find(item => item.value === mode)
}

function clearAutoSaveTimer() {
  if (autoSaveTimer !== null) {
    window.clearInterval(autoSaveTimer)
    autoSaveTimer = null
  }
}

function syncAutoSaveTimer(mode: AutoSaveMode) {
  clearAutoSaveTimer()

  const activeOption = getSaveModeOption(mode)
  if (!activeOption) return

  autoSaveTimer = window.setInterval(() => {
    void runAutoBackup()
  }, activeOption.intervalMs)
}

async function readLocalProjectMeta(directoryHandle: BrowserDirectoryHandle) {
  try {
    const projectFileHandle = await directoryHandle.getFileHandle('project.json')
    const rawText = await (await projectFileHandle.getFile()).text()
    return JSON.parse(rawText) as Partial<ProjectFileContent>
  } catch {
    return null
  }
}

async function writeLocalJsonFile(directoryHandle: BrowserDirectoryHandle, fileName: string, payload: unknown) {
  const fileHandle = await directoryHandle.getFileHandle(fileName, { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(JSON.stringify(payload, null, 2))
  await writable.close()
}

async function ensureLocalProjectWorkspace(saveMode: Exclude<AutoSaveMode, 'manual'>) {
  const directoryHandle = currentProjectDirectoryHandle.value
  if (!directoryHandle) {
    throw new Error('当前项目没有可写入的本地目录')
  }

  for (const directoryName of ['assets', 'audio', 'image', 'video', 'exports']) {
    await directoryHandle.getDirectoryHandle(directoryName, { create: true })
  }

  const now = getCurrentTimestampParts()
  const currentMeta = (await readLocalProjectMeta(directoryHandle)) || {}
  const projectName =
    (typeof currentMeta.name === 'string' && currentMeta.name.trim()) ||
    currentProjectName.value ||
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
  currentProjectName.value = projectName
  currentProjectPath.value = currentProjectPath.value || directoryHandle.name || '已选择项目文件夹'

  return nextMeta
}

async function createLocalProjectBackup(saveMode: Exclude<AutoSaveMode, 'manual'>) {
  const directoryHandle = currentProjectDirectoryHandle.value
  if (!directoryHandle) {
    throw new Error('当前项目没有可写入的本地目录')
  }

  const now = getCurrentTimestampParts()
  const projectMeta = await ensureLocalProjectWorkspace(saveMode)
  const backupDirectoryHandle = await directoryHandle.getDirectoryHandle('backup', { create: true })
  const backupPayload = {
    ...projectMeta,
    updated_at: now.display,
    save_mode: saveMode,
    last_backup_at: now.display,
    backup_created_at: now.display,
    backup_source_path: currentProjectPath.value || directoryHandle.name || '已选择项目文件夹',
  }

  await writeLocalJsonFile(directoryHandle, 'project.json', backupPayload)
  await writeLocalJsonFile(backupDirectoryHandle, buildBackupFileName(projectMeta.name, now.file), backupPayload)
}

async function ensureAutoSaveWorkspace(saveMode: Exclude<AutoSaveMode, 'manual'>) {
  if (currentProjectDirectoryHandle.value) {
    await ensureLocalProjectWorkspace(saveMode)
    currentSaveMode.value = saveMode
    return
  }

  const { project } = await ensureAutoSaveProject({
    name: currentProjectName.value || buildAutoSaveProjectName(),
    project_path: isAbsoluteProjectPath(currentProjectPath.value) ? currentProjectPath.value : null,
    save_mode: saveMode,
  })

  currentProjectName.value = project.name
  currentProjectPath.value = project.project_path
  currentProjectDirectoryHandle.value = null
  currentSaveMode.value = normalizeSaveMode(project.save_mode)
  currentProjectId.value = project.id ?? currentProjectId.value
  persistActiveProject()
}

async function runAutoBackup() {
  const activeMode = currentSaveMode.value
  if (activeMode === 'manual') return

  try {
    if (currentProjectDirectoryHandle.value) {
      await createLocalProjectBackup(activeMode)
      return
    }

    const { project } = await createAutoBackup({
      name: currentProjectName.value || buildAutoSaveProjectName(),
      project_path: currentProjectPath.value,
      save_mode: activeMode,
    })

    currentProjectId.value = project.id ?? currentProjectId.value
    currentProjectName.value = project.name
    currentProjectPath.value = project.project_path
    persistActiveProject()
  } catch (error) {
    clearAutoSaveTimer()
    currentSaveMode.value = 'manual'

    if (error instanceof Error) {
      ElMessage.error(`自动备份失败：${error.message}`)
      return
    }

    ElMessage.error('自动备份失败，已停止当前保存模式')
  }
}

async function handleSelectSaveMode(option: SaveModeOption) {
  if (isSaveModeApplying.value) return

  isSaveModeApplying.value = true

  try {
    await ensureAutoSaveWorkspace(option.value)
    currentSaveMode.value = option.value
    syncAutoSaveTimer(option.value)
    isSaveModeOpen.value = false
    ElMessage.success(`已切换为：${option.label}`)
  } catch (error) {
    if (error instanceof Error) {
      ElMessage.error(error.message || '设置自动保存模式失败')
    }
  } finally {
    isSaveModeApplying.value = false
  }
}

function toggleSearchPanel() {
  isSearchOpen.value = !isSearchOpen.value
  isProjectOpen.value = false
}

function openSearchPanel() {
  isSearchOpen.value = true
  isProjectOpen.value = false
}

function toggleSaveMode() {
  isSaveModeOpen.value = !isSaveModeOpen.value
}

function buildAgentHistory(): AgentHistoryItem[] {
  return agentMessages.value
    .filter(item => !item.isError)
    .map(item => ({
      role: item.role,
      content: item.content,
    }))
}

function mapHistoryToAgentMessages(history: AgentHistoryItem[]) {
  return history.map(item => ({
    id: `agent-${localAgentMessageId++}`,
    role: item.role,
    content: item.content,
  }))
}

function formatToolName(toolName: string) {
  const toolMap: Record<string, string> = {
    calculate: '计算工具',
    get_current_time: '时间工具',
    search_web: '联网搜索',
  }

  return toolMap[toolName] || toolName
}

function startAgentThinking() {
  stopAgentThinking()
  isAgentThinking.value = true
  hasAgentStartedReplying.value = false
  agentThinkingSeconds.value = 0
  agentThinkingTimer = window.setInterval(() => {
    agentThinkingSeconds.value += 1
  }, 1000)
}

function markAgentReplyStarted() {
  hasAgentStartedReplying.value = true
}

function stopAgentThinking() {
  isAgentThinking.value = false
  hasAgentStartedReplying.value = false
  agentThinkingSeconds.value = 0
  if (agentThinkingTimer !== null) {
    window.clearInterval(agentThinkingTimer)
    agentThinkingTimer = null
  }
  if (agentFirstTokenTimeout !== null) {
    window.clearTimeout(agentFirstTokenTimeout)
    agentFirstTokenTimeout = null
  }
}

function isFirstTokenTimeoutError(error: unknown) {
  if (chatAbortController?.signal.aborted && chatAbortController.signal.reason === 'FIRST_TOKEN_TIMEOUT') {
    return true
  }

  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }

  if (error instanceof Error) {
    return error.name === 'AbortError' || error.message.includes('aborted')
  }

  return false
}

const agentThinkingStatusText = computed(() => {
  if (!isAgentSending.value) return ''
  if (activeToolName.value) return `正在调用 ${formatToolName(activeToolName.value)}`
  if (hasAgentStartedReplying.value) return `正在输出回复 · 已思考 ${agentThinkingSeconds.value}s`
  return `正在思考 · 已思考 ${agentThinkingSeconds.value}s`
})

async function scrollAssistantToBottom() {
  await nextTick()
  if (!assistantBodyRef.value) return
  assistantBodyRef.value.scrollTop = assistantBodyRef.value.scrollHeight
}

async function loadAgentPanel() {
  const currentLoadToken = ++agentPanelLoadToken
  const targetProjectId = currentProjectId.value
  try {
    // 真实进度接管：进入 API 调用阶段，>0 即从内置 rAF 切到真实进度
    loadingStore.setProgress(35)
    loadingStore.setLabel('Loading conversation history')
    const history = await getAgentHistory(targetProjectId)
    if (currentLoadToken !== agentPanelLoadToken || targetProjectId !== currentProjectId.value) {
      return
    }
    agentMessages.value = mapHistoryToAgentMessages(history)
    await scrollAssistantToBottom()
    loadingStore.setProgress(95)
    loadingStore.setLabel('Finalizing')
  } catch {
    if (currentLoadToken !== agentPanelLoadToken) {
      return
    }
    agentMessages.value = []
    loadingStore.setProgress(95)
    loadingStore.setLabel('Finalizing')
  } finally {
    loadingStore.setProgress(100)
    loadingStore.setLabel('Entering')
    // 关键：核心资源加载完成（成功或失败都算"完成"）后通知外层淡出覆盖层。
    emit('ready')
  }
}

function handleComposerKeydown(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  void sendAgentMessage()
}

async function sendAgentMessage() {
  const message = agentInput.value.trim()
  if (!message || isAgentSending.value) return

  const history = buildAgentHistory()
  const userMessage: AgentMessage = {
    id: `agent-${localAgentMessageId++}`,
    role: 'user',
    content: message,
  }
  const assistantMessage: AgentMessage = {
    id: `agent-${localAgentMessageId++}`,
    role: 'assistant',
    content: '',
    toolName: null,
    isPending: true,
  }

  agentMessages.value = [...agentMessages.value, userMessage, assistantMessage]
  agentInput.value = ''
  isAgentSending.value = true
  activeToolName.value = ''
  startAgentThinking()
  chatAbortController = new AbortController()
  agentFirstTokenTimeout = window.setTimeout(() => {
    if (!hasAgentStartedReplying.value && chatAbortController) {
      chatAbortController.abort('FIRST_TOKEN_TIMEOUT')
    }
  }, AGENT_FIRST_TOKEN_TIMEOUT_MS)
  await scrollAssistantToBottom()

  try {
    await streamAgentChat(
      {
        message,
        history,
        project_id: currentProjectId.value,
      },
      {
        onTool(event) {
          if (agentFirstTokenTimeout !== null) {
            window.clearTimeout(agentFirstTokenTimeout)
            agentFirstTokenTimeout = null
          }
          activeToolName.value = event.tool_name
          assistantMessage.toolName = event.tool_name
          void scrollAssistantToBottom()
        },
        onContent(event) {
          if (agentFirstTokenTimeout !== null) {
            window.clearTimeout(agentFirstTokenTimeout)
            agentFirstTokenTimeout = null
          }
          if (assistantMessage.isPending) {
            assistantMessage.isPending = false
          }
          if (!hasAgentStartedReplying.value) {
            markAgentReplyStarted()
          }
          assistantMessage.content += event.content
          void scrollAssistantToBottom()
        },
        onDone(event) {
          activeToolName.value = ''
          agentMessages.value = mapHistoryToAgentMessages(event.history)
          void scrollAssistantToBottom()
        },
      },
      chatAbortController.signal,
    )
  } catch (error) {
    if (isFirstTokenTimeoutError(error)) {
      assistantMessage.isPending = false
      assistantMessage.content = '10 秒内未收到模型返回，已自动暂停本次响应。请检查后端日志、接口耗时或重试。'
      assistantMessage.isError = true
      assistantMessage.toolName = null
      ElMessage.error('10 秒内未收到模型返回，已自动暂停')
      await scrollAssistantToBottom()
      return
    }

    const errorMessage = error instanceof Error ? error.message : 'N 响应失败'
    assistantMessage.isPending = false
    assistantMessage.content = errorMessage
    assistantMessage.isError = true
    assistantMessage.toolName = null
    ElMessage.error(errorMessage)
    await scrollAssistantToBottom()
  } finally {
    isAgentSending.value = false
    activeToolName.value = ''
    stopAgentThinking()
    chatAbortController = null
  }
}

function handleDocumentClick(event: MouseEvent) {
  const target = event.target as Node | null

  if (topbarCombinedRef.value && target && !topbarCombinedRef.value.contains(target)) {
    isProjectOpen.value = false
    isSearchOpen.value = false
  }

  if (saveModeWrapRef.value && target && !saveModeWrapRef.value.contains(target)) {
    isSaveModeOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  restoreActiveProjectFromStorage()
  if (typeof route.query.project === 'string' && route.query.project !== 'default') {
    const routeProjectId = Number(route.query.project)
    if (!Number.isNaN(routeProjectId)) {
      currentProjectId.value = routeProjectId
    }
  }
  void loadAgentPanel()
})

onBeforeUnmount(() => {
  chatAbortController?.abort()
  stopAgentThinking()
  clearAutoSaveTimer()
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.workstation-layout {
  --body-bg: #0b0b0b;
  --column-bg: #101010;
  --panel-bg: #101010;
  --hover-bg: #1a1a1a;
  --line: #262626;
  --text-primary: #e6e6e6;
  --text-secondary: #808080;
  --text-sidebar: #a0a0a0;
  --accent: #8a8a8a;
  --topbar-h: 56px;
  --app-min-width: 1420px;
  --app-min-height: 820px;
  --left-column-w: 312px;
  --right-column-w: 392px;
  width: 100vw;
  height: 100vh;
  overflow: auto;
  background: var(--body-bg);
  color: var(--text-primary);
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  font-weight: 400;
  line-height: 1.5;
}

.workstation-layout,
.workstation-layout *,
.workstation-layout *::before,
.workstation-layout *::after {
  box-sizing: border-box;
  box-shadow: none !important;
}

.workstation-layout button,
.workstation-layout input,
.workstation-layout textarea {
  font: inherit;
}

.workstation-layout button:not(.status-button):not(.add-tool-large) {
  border: 0 !important;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.workstation-layout button:not(.status-button):not(.add-tool-large):hover {
  background: var(--hover-bg);
  color: #ffffff;
  filter: brightness(1.1);
}

.combined-left,
.combined-right,
.status-button,
.project-switcher-option,
.search-result-item,
.status-panel-option,
.icon-button,
.add-tool-large,
.composer-tool,
.composer-model-button,
.composer-action,
.modal-option,
.modal-close {
  will-change: transform, background-color, opacity;
  transform-origin: center;
  transition:
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    background-color 180ms ease,
    color 180ms ease,
    filter 180ms ease,
    opacity 180ms ease;
}

.combined-right:hover,
.status-button:hover,
.project-switcher-option:hover,
.search-result-item:hover,
.status-panel-option:hover,
.icon-button:hover,
.add-tool-large:hover,
.composer-tool:hover,
.composer-model-button:hover,
.composer-action:hover,
.modal-option:hover,
.modal-close:hover {
  animation: ux-jelly 360ms cubic-bezier(0.22, 1, 0.36, 1) 1;
  transform: translateY(-1px) scale(1.018);
}

.combined-right:active,
.status-button:active,
.project-switcher-option:active,
.search-result-item:active,
.status-panel-option:active,
.icon-button:active,
.add-tool-large:active,
.composer-tool:active,
.composer-model-button:active,
.composer-action:active,
.modal-option:active,
.modal-close:active {
  transform: scale(0.985);
  transition-duration: 90ms;
}

.app-shell {
  width: max(100%, var(--app-min-width));
  min-width: var(--app-min-width);
  min-height: var(--app-min-height);
  height: max(100vh, var(--app-min-height));
  background: var(--body-bg);
}

.app-frame {
  width: 100%;
  min-width: var(--app-min-width);
  min-height: var(--app-min-height);
  height: 100%;
  background: var(--body-bg);
  overflow: hidden;
  display: grid;
  grid-template-rows: var(--topbar-h) 1fr;
}

.topbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
  position: relative;
  min-width: var(--app-min-width);
  padding: 0 18px;
  border-bottom: 1px solid var(--line) !important;
  background: var(--column-bg);
}

.topbar-left,
.topbar-center,
.topbar-right,
.menu-row,
.window-controls,
.status-row,
.title-row {
  display: flex;
  align-items: center;
  min-width: 0;
}

.topbar-left {
  gap: 0;
}

.title-row {
  gap: 10px;
  min-width: 0;
}

.app-title,
.section-title,
.assistant-title,
.modal-title,
.message-title {
  font-weight: 600;
}

.topbar-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  justify-content: center;
  gap: 12px;
  min-width: 0;
  padding-right: 0;
  z-index: 2;
}

.topbar-combined {
  height: 32px;
  position: relative;
  width: 463px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.015);
}

.combined-label {
  color: var(--text-secondary);
  white-space: nowrap;
  transition: color 180ms ease, opacity 180ms ease;
}

.combined-left,
.combined-right {
  height: 100%;
  display: inline-flex;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.combined-left {
  flex: 1;
  justify-content: flex-start;
  padding: 0 6px;
}

.combined-divider {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.14);
  margin: 0 10px 0 6px;
}

.combined-right {
  justify-content: flex-end;
  min-width: 72px;
  padding-right: 6px;
  gap: 6px;
}

.combined-right-text {
  color: var(--text-secondary);
  transition: color 180ms ease, opacity 180ms ease;
}

.combined-left:hover {
  transform: translateY(-1px);
  filter: none;
}

.combined-left:hover .combined-label,
.combined-right:hover .combined-right-text,
.status-button:hover span {
  color: var(--text-primary);
}

.combined-left:active {
  transform: scale(0.992);
  transition-duration: 90ms;
}

.search-signal {
  width: 1px;
  height: 12px;
  background: rgba(230, 230, 230, 0.12);
  opacity: 0;
  border-radius: 999px;
  transform: scaleY(0.7);
}

.search-signal.active {
  opacity: 1;
  animation: search-blink 1s steps(2, end) infinite;
}

.topbar-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  width: 100%;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  background: rgba(16, 16, 16, 0.94);
  backdrop-filter: blur(14px);
  z-index: 30;
  display: flex;
}

.project-switcher-group,
.project-history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.project-switcher-group-label {
  padding: 2px 10px 0;
  color: #6f6f6f;
  font-size: 12px;
  letter-spacing: 0.02em;
}

.project-switcher-option,
.search-result-item {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 16px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.project-option-title {
  color: inherit;
}

.project-option-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6f6f6f;
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.project-history-ellipsis {
  padding: 2px 0 0;
  color: #6f6f6f;
  text-align: center;
  letter-spacing: 2px;
}

.search-panel-title {
  color: var(--text-primary);
  font-size: 13px;
}

.search-panel input {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  padding: 8px 10px;
  outline: none;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.search-result-item:hover,
.project-switcher-option:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.search-result-meta {
  margin-top: 2px;
  font-size: 12px;
  color: #6f6f6f;
}

.search-result-ellipsis {
  color: var(--text-secondary);
  text-align: center;
  letter-spacing: 2px;
}

.topbar-right {
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
  padding-right: 0;
  margin-right: -6px;
}

.topbar-right .window-controls {
  display: none;
}

.status-row {
  gap: 8px;
  flex-wrap: wrap;
  position: relative;
}

.status-button-wrap {
  position: relative;
}

.status-button {
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 124px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.015);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.status-button-label {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.status-button:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.status-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 220px;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(20, 20, 20, 0.98);
  z-index: 30;
  display: flex;
}

.status-panel-option {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border-radius: 16px;
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.save-mode-label-enter-active,
.save-mode-label-leave-active {
  transition:
    opacity 180ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.save-mode-label-enter-from,
.save-mode-label-leave-to {
  opacity: 0;
  transform: translateY(3px);
}

.save-mode-label-enter-to,
.save-mode-label-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.window-controls {
  gap: 8px;
}

.window-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: transparent;
}

.main-grid {
  min-height: 0;
  display: grid;
  min-width: var(--app-min-width);
  grid-template-columns: var(--left-column-w) minmax(716px, 1fr) var(--right-column-w);
  grid-template-areas: 'left center right';
  background: var(--body-bg);
}

.left-column {
  grid-area: left;
  min-width: 0;
  display: grid;
  grid-template-columns: 42px 1fr;
  border-right: 1px solid var(--line) !important;
  background: var(--column-bg);
}

.icon-rail {
  padding: 8px 4px;
  border-right: 1px solid var(--line) !important;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--column-bg);
}

.rail-spacer {
  flex: 1;
}

.icon-button {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  color: var(--text-sidebar);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.icon-button:hover,
.icon-button.active {
  background: var(--hover-bg);
  color: #ffffff;
}

.sidebar-stack {
  min-width: 0;
  display: grid;
  grid-template-rows: 1fr;
  gap: 0;
  padding: 6px;
  background: var(--column-bg);
}

.sidebar-workspace {
  min-height: 100%;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.015);
  padding: 4px;
  display: flex;
  flex-direction: column;
}

.section-card {
  border-radius: 0;
  background: transparent;
  overflow: hidden;
}

.section-body {
  padding: 0;
}

.add-tool-large {
  width: 100%;
  min-height: 76px;
  border: 1px solid rgba(40, 40, 40, 0.6) !important;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
}

.add-tool-large:hover {
  background: rgba(255, 255, 255, 0.06) !important;
  color: var(--text-primary) !important;
  filter: none !important;
}

.center-column {
  grid-area: center;
  min-width: 0;
  position: relative;
  background: var(--body-bg);
}

.canvas-surface {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  padding: 6px;
  gap: 10px;
}

.canvas-area {
  flex: 1;
  display: flex;
}

.canvas-center {
  width: 100%;
  min-height: 100%;
  border: 1px solid rgba(40, 40, 40, 0.55);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.015);
  justify-content: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 18px;
  color: var(--text-secondary);
}

.canvas-callout {
  padding: 8px 12px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  font-weight: 400;
}

.right-column {
  grid-area: right;
  min-width: 0;
  padding: 0;
  border-left: 1px solid var(--line) !important;
  background:
    radial-gradient(circle at top, rgba(255, 255, 255, 0.04), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
    var(--column-bg);
}

.assistant-panel {
  height: 100%;
  display: grid;
  grid-template-rows: auto 1fr auto;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.014), rgba(255, 255, 255, 0)),
    var(--column-bg);
  overflow: hidden;
}

.assistant-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 0 10px;
  background: var(--column-bg);
}

.assistant-head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px 0 18px;
}

.assistant-head-copy {
  flex: 1;
  min-width: 0;
}

.assistant-title-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.assistant-title {
  font-size: 20px;
  letter-spacing: -0.02em;
}

.assistant-presence {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
  animation: assistant-presence-pulse 2.6s ease-in-out infinite;
}

.assistant-meta {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.assistant-head-divider {
  width: auto;
  margin: 0 6px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
}

.assistant-body {
  min-height: 0;
  overflow: auto;
  padding: 14px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--column-bg);
  scroll-behavior: smooth;
}

.agent-empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
  padding: 20px 14px;
  text-align: center;
}

.agent-empty-orbit {
  width: 60px;
  height: 60px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  position: relative;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.06), transparent 62%);
}

.agent-empty-orbit::before,
.agent-empty-orbit::after {
  content: '';
  position: absolute;
  inset: 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.agent-empty-orbit::after {
  inset: -1px;
  border-top-color: rgba(255, 255, 255, 0.36);
  border-right-color: transparent;
  border-bottom-color: transparent;
  border-left-color: transparent;
  animation: agent-empty-orbit-spin 5s linear infinite;
}

.agent-empty-title {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 400;
}

.agent-empty-meta {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  max-width: 268px;
}

.agent-message-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 4px;
}

.agent-message {
  display: flex;
  flex-direction: column;
  gap: 6px;
  will-change: transform, opacity, filter;
}

.agent-message.is-user {
  align-items: flex-end;
}

.agent-message.is-assistant,
.agent-message.is-error {
  align-items: flex-start;
}

.agent-message-meta {
  min-height: 16px;
  display: flex;
  align-items: center;
}

.agent-message-bubble {
  max-width: min(92%, 100%);
  padding: 11px 13px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.022)),
    rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transition:
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}

.agent-message-bubble:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.09);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 10px 24px rgba(0, 0, 0, 0.16);
}

.agent-message-bubble.is-pending {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 132px;
  min-height: 48px;
  padding-inline: 14px;
}

.agent-thinking-wave {
  display: inline-flex;
  align-items: center;
  gap: 1px;
}

.agent-thinking-letter {
  display: inline-block;
  color: rgba(255, 255, 255, 0.86);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  animation: thinking-letter-wave 1.28s ease-in-out infinite;
  will-change: transform, opacity;
}

.agent-message.is-user .agent-message-bubble {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.05)),
    rgba(255, 255, 255, 0.035);
  border-color: rgba(255, 255, 255, 0.09);
}

.agent-message.is-error .agent-message-bubble {
  border-color: rgba(173, 72, 72, 0.24);
  background: rgba(143, 45, 45, 0.1);
  color: #f0d8d8;
}

.agent-tool-chip,
.agent-status-line {
  color: var(--text-secondary);
  font-size: 12px;
}

.agent-tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 1px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.agent-tool-chip::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.42);
}

.agent-status-line {
  position: sticky;
  bottom: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  margin: 4px 0 0;
  padding: 8px 10px 2px 4px;
  color: rgba(255, 255, 255, 0.68);
  background: linear-gradient(180deg, transparent, rgba(11, 11, 11, 0.92) 32%, rgba(11, 11, 11, 0.98));
  pointer-events: none;
}

.agent-status-pulse {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  animation: agent-status-pulse 1.6s ease-in-out infinite;
}

.composer-wrap {
  padding: 8px 10px 10px;
  border-top: 1px solid var(--line) !important;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.012), transparent),
    var(--column-bg);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-composer {
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.028), rgba(255, 255, 255, 0.015)),
    rgba(255, 255, 255, 0.012);
  padding: 16px 12px 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: relative;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1);
}

.input-composer:hover,
.input-composer:focus-within {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.022)),
    rgba(255, 255, 255, 0.018);
  border-color: rgba(255, 255, 255, 0.1) !important;
  box-shadow:
    0 16px 40px rgba(0, 0, 0, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
  transform: translateY(-1px);
}

.input-composer textarea {
  min-height: 120px;
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 400;
  line-height: 1.7;
  padding: 0;
  width: 100%;
  display: block;
}

.input-composer textarea::placeholder {
  color: var(--text-secondary);
}

.input-composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.composer-toolbar-left,
.composer-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.composer-action {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 999px;
}

.composer-action-icon {
  display: inline-block;
  transition: transform 180ms ease, opacity 180ms ease;
}

.composer-action.primary {
  color: var(--text-secondary);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04)),
    rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
}

.composer-action.primary:hover {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.07)),
    rgba(255, 255, 255, 0.08);
}

.composer-action.primary:hover .composer-action-icon {
  transform: translateY(-1px) scale(1.04);
}

.composer-action:disabled {
  opacity: 0.56;
  cursor: default;
}

.composer-tool {
  min-width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  padding: 0 8px;
  border-radius: 999px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid transparent !important;
}

.composer-tool svg {
  width: 16px;
  height: 16px;
}

.composer-model-button {
  min-width: 72px;
  height: 40px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.028)),
    rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  color: var(--text-secondary);
  transition: background-color 150ms ease-out, color 180ms ease;
}

.composer-model-button:hover {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.11), rgba(255, 255, 255, 0.05)),
    rgba(255, 255, 255, 0.1) !important;
  color: var(--text-primary) !important;
  filter: none !important;
}

@media (max-width: 1480px) {
  .assistant-head-top {
    padding-inline: 12px;
  }

  .assistant-body {
    padding-inline: 12px;
  }

  .composer-wrap {
    padding-inline: 8px;
  }

  .agent-message-bubble {
    max-width: 100%;
  }
}

@media (max-width: 1320px) {
  .assistant-title {
    font-size: 18px;
  }

  .assistant-meta,
  .agent-empty-meta,
  .agent-message-bubble {
    font-size: 13px;
  }

  .input-composer {
    padding: 14px 10px 10px 14px;
  }

  .input-composer textarea {
    min-height: 104px;
    font-size: 15px;
  }

  .composer-model-button {
    min-width: 64px;
  }

  .agent-status-line {
    font-size: 11px;
  }
}

@keyframes assistant-presence-pulse {
  0%,
  100% {
    opacity: 0.55;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.08);
  }
}

@keyframes agent-empty-orbit-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@keyframes thinking-letter-wave {
  0%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }

  35% {
    opacity: 1;
    transform: translateY(-3px);
  }

  60% {
    opacity: 0.7;
    transform: translateY(1px);
  }
}

@keyframes agent-status-pulse {
  0%,
  100% {
    opacity: 0.25;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.agent-message-float-enter-active,
.agent-message-float-leave-active {
  transition:
    opacity 320ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 320ms cubic-bezier(0.16, 1, 0.3, 1),
    filter 320ms cubic-bezier(0.16, 1, 0.3, 1);
}

.agent-message-float-enter-from,
.agent-message-float-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.985);
  filter: blur(6px);
}

.agent-message-float-enter-to,
.agent-message-float-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
  filter: blur(0);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.58);
  backdrop-filter: blur(8px);
  z-index: 20;
}

.modal-card {
  width: min(540px, 100%);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(16, 16, 16, 0.96);
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  background: transparent;
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  cursor: pointer;
}

.modal-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: transparent;
}

.modal-option {
  width: 100%;
  text-align: left;
  color: var(--text-primary);
  cursor: pointer;
  border-radius: 16px;
  background: transparent;
  padding: 12px 14px;
}

.modal-option-sub {
  color: var(--text-secondary);
  line-height: 1.6;
}

.project-create-modal,
.project-confirm-modal,
.project-warning-modal {
  width: min(520px, 100%);
}

.project-confirm-modal {
  border-color: rgba(173, 72, 72, 0.26);
}

.project-create-body {
  gap: 16px;
}

.project-create-label {
  color: var(--text-primary);
  font-size: 13px;
}

.project-create-input {
  width: 100%;
  height: 42px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text-primary);
  padding: 0 12px;
  outline: none;
}

.project-create-input:focus {
  border-color: rgba(255, 255, 255, 0.14);
}

.project-create-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.project-summary-title {
  color: var(--text-primary);
}

.project-summary-meta {
  color: var(--text-secondary);
  font-size: 13px;
}

.project-create-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: center;
}

.project-create-actions--three {
  grid-template-columns: 1fr 1fr 1fr;
}

.project-warning-actions {
  display: flex;
  justify-content: flex-end;
}

.project-secondary-button,
.project-primary-button,
.project-danger-button {
  height: 38px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
    background-color 180ms ease,
    color 180ms ease,
    opacity 180ms ease;
}

.project-secondary-button {
  background: rgba(255, 255, 255, 0.04) !important;
  color: var(--text-secondary) !important;
}

.project-primary-button {
  background: #f2f2f2 !important;
  color: #0b0b0b !important;
}

.project-danger-button {
  background: #8f2d2d !important;
  color: #f3dede !important;
}

.warning-callout {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(173, 72, 72, 0.22);
  background: rgba(143, 45, 45, 0.08);
}

.warning-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(143, 45, 45, 0.18);
  color: #f3dede;
  font-size: 18px;
  line-height: 1;
}

.warning-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.warning-title {
  color: var(--text-primary);
  font-size: 14px;
}

.warning-message {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.project-secondary-button:hover,
.project-primary-button:hover,
.project-danger-button:hover {
  transform: translateY(-1px);
  filter: brightness(1.04);
}

.project-secondary-button:disabled,
.project-primary-button:disabled,
.project-danger-button:disabled {
  opacity: 0.6;
  cursor: default;
}

@media (max-width: 1180px) {
  .app-shell,
  .app-frame,
  .topbar,
  .main-grid {
    min-width: var(--app-min-width);
  }
}

@keyframes ux-jelly {
  0% {
    transform: translateY(0) scale(1);
  }
  40% {
    transform: translateY(-1px) scale(1.028, 0.984);
  }
  72% {
    transform: translateY(-1px) scale(0.996, 1.012);
  }
  100% {
    transform: translateY(-1px) scale(1.018);
  }
}

@keyframes search-blink {
  0%,
  45% {
    opacity: 0.12;
  }
  46%,
  100% {
    opacity: 0.92;
  }
}

.panel-float-enter-active,
.panel-float-leave-active {
  transition:
    opacity 320ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 320ms cubic-bezier(0.16, 1, 0.3, 1),
    filter 320ms cubic-bezier(0.16, 1, 0.3, 1);
}

.panel-float-enter-from,
.panel-float-leave-to {
  opacity: 0;
  transform: translateY(-12px) scale(0.985);
  filter: blur(6px);
}

.panel-float-enter-to,
.panel-float-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
  filter: blur(0);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 320ms cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-to,
.modal-fade-leave-from {
  opacity: 1;
}

.modal-fade-enter-active .modal-card,
.modal-fade-leave-active .modal-card {
  transition:
    opacity 320ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 320ms cubic-bezier(0.16, 1, 0.3, 1),
    filter 320ms cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-fade-enter-from .modal-card,
.modal-fade-leave-to .modal-card {
  opacity: 0;
  transform: translateY(-14px) scale(0.985);
  filter: blur(8px);
}

.modal-fade-enter-to .modal-card,
.modal-fade-leave-from .modal-card {
  opacity: 1;
  transform: translateY(0) scale(1);
  filter: blur(0);
}

.modal-swap-enter-active,
.modal-swap-leave-active {
  transition:
    opacity 240ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 240ms cubic-bezier(0.16, 1, 0.3, 1),
    filter 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-swap-enter-from,
.modal-swap-leave-to {
  opacity: 0;
  transform: translateY(8px);
  filter: blur(4px);
}

.modal-swap-enter-to,
.modal-swap-leave-from {
  opacity: 1;
  transform: translateY(0);
  filter: blur(0);
}
</style>
