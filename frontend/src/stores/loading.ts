// 全局过渡覆盖层状态。
//
// 设计要点：
// - 单实例 store 持有 overlay 的"显示 / 隐藏"和"动效进度"。
// - 组件 LoadingOverlay 通过订阅此 store 渲染；调用方只调 show/hide/setProgress。
// - 不与路由耦合，路由跳转由调用方决定，overlay 仅负责"看到什么、何时退场"。
// - 任意时刻只允许一个显式流程，重复 show 会被新的 mode 覆盖并保留可见态。
//
// 智能 hide：
// - 调用方在资源加载完成后调 hide()。
// - 若 show() 距今 < minDuration（默认 1s）：延后到 minDuration 满足后再 visible=false。
//   保证"快速加载也至少展示 1s"的硬性要求。
// - 若 show() 距今 >= minDuration：立即 visible=false。
//   跟随实际资源加载耗时，不设上限，不会"为了凑 1s 而空转"。
//
// 真实进度接管：
// - 调用方可在加载过程中调 setProgress(0..100)。
// - 一旦 realProgress > 0，覆盖层以真实进度为准；
//   调用方从未推过任何进度时，覆盖层回退到内置 rAF 动画保证视觉流畅。
import { defineStore } from 'pinia'

export type LoadingMode = 'login' | 'register' | 'auto' | 'workstation'

const DEFAULTS: Record<LoadingMode, string> = {
  login: 'Preparing your workspace',
  register: 'Provisioning your studio',
  auto: 'Resuming your session',
  workstation: 'Resuming your session',
}

const DEFAULT_MIN_DURATION = 1000 // 1s 最低展示时长

// 模块级延时句柄（不放入 state，避免序列化与跨实例共享问题）
let pendingHideTimer: ReturnType<typeof setTimeout> | null = null

export const useLoadingStore = defineStore('loading', {
  state: () => ({
    visible: false,
    /** 外部推动的真实进度；0 表示"无真实进度" */
    realProgress: 0,
    /** show() 的时间戳，用于计算最低展示时长 */
    shownAt: null as number | null,
    /** 最低展示时长（ms），默认 1000 */
    minDuration: DEFAULT_MIN_DURATION,
    mode: 'auto' as LoadingMode,
    label: 'Preparing your workspace',
  }),
  actions: {
    /**
     * 显示覆盖层。
     * - 取消任何挂起的 hide 延时（避免上次未完成的延时干扰）。
     * - 重置 shownAt / realProgress。
     * - 可选配置：minDuration 覆盖默认 1s；label 覆盖默认提示语。
     */
    show(
      mode: LoadingMode = 'auto',
      options?: { minDuration?: number; label?: string },
    ) {
      if (pendingHideTimer) {
        clearTimeout(pendingHideTimer)
        pendingHideTimer = null
      }
      this.visible = true
      this.shownAt = Date.now()
      this.realProgress = 0
      this.mode = mode
      this.label = options?.label || DEFAULTS[mode]
      this.minDuration =
        options?.minDuration != null
          ? Math.max(0, options.minDuration)
          : DEFAULT_MIN_DURATION
    },

    /**
     * 推动真实加载进度。
     * - 0 表示"无真实进度"（overlay 会回退到内置 rAF 动画）。
     * - 任意 > 0 的值会接管显示，进度条与百分比同步。
     */
    setProgress(p: number) {
      const v = Math.max(0, Math.min(100, Number(p) || 0))
      this.realProgress = v
    },

    setLabel(label: string) {
      if (label) this.label = label
    },

    setMinDuration(ms: number) {
      this.minDuration = Math.max(0, Number(ms) || 0)
    },

    /**
     * 隐藏覆盖层。智能行为：
     * - 若 show() 距今 >= minDuration：立即 visible=false（跟随实际耗时，无 1s 上限）。
     * - 若 show() 距今 <  minDuration：延后到 minDuration 满足后再 visible=false（保底 1s）。
     * - 重复调用、show 期间调用等异常路径均有兜底，不会卡住。
     */
    hide() {
      if (!this.visible) {
        // 即使已经隐藏，也清掉挂起的延时，避免下次 show 被旧延时影响
        if (pendingHideTimer) {
          clearTimeout(pendingHideTimer)
          pendingHideTimer = null
        }
        return
      }
      if (this.shownAt == null) {
        this.visible = false
        this.realProgress = 0
        return
      }
      const elapsed = Date.now() - this.shownAt
      const remaining = Math.max(0, this.minDuration - elapsed)
      if (remaining === 0) {
        this.visible = false
        this.shownAt = null
        this.realProgress = 0
      } else {
        if (pendingHideTimer) {
          clearTimeout(pendingHideTimer)
        }
        pendingHideTimer = setTimeout(() => {
          pendingHideTimer = null
          this.visible = false
          this.shownAt = null
          this.realProgress = 0
        }, remaining)
      }
    },
  },
})
