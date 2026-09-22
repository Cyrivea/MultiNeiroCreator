/**
 * 任务完成提示音（B28）：WebAudio 即时合成短促 chime，不依赖任何音频资源文件。
 *
 * 浏览器自动播放策略：AudioContext 在页面获得用户手势前处于 suspended 状态，
 * 播不出来时静默吞掉（try/catch），不影响 ElNotification 通知本身。
 */

interface ChimeNote {
  /** 频率 Hz */
  freq: number
  /** 相对起点的偏移（秒） */
  start: number
  /** 持续（秒） */
  duration: number
}

const SUCCESS_CHIME: ChimeNote[] = [
  { freq: 659.25, start: 0, duration: 0.16 }, // E5
  { freq: 987.77, start: 0.13, duration: 0.32 }, // B5
]

const ERROR_CHIME: ChimeNote[] = [
  { freq: 392.0, start: 0, duration: 0.18 }, // G4
  { freq: 311.13, start: 0.15, duration: 0.36 }, // Eb4
]

let sharedContext: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (sharedContext) return sharedContext
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Ctor) return null
  try {
    sharedContext = new Ctor()
  } catch {
    return null
  }
  return sharedContext
}

/**
 * 播放完成提示音。kind='success' 上行双音，kind='error' 下行双音。
 * 环境不支持（SSR/无 AudioContext/自动播放被拒）时安静返回，绝不抛错。
 */
export function playTaskCompleteSound(kind: 'success' | 'error'): void {
  try {
    const ctx = getAudioContext()
    if (!ctx) return
    if (ctx.state === 'suspended') void ctx.resume()

    const notes = kind === 'success' ? SUCCESS_CHIME : ERROR_CHIME
    const base = ctx.currentTime + 0.02

    for (const note of notes) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = note.freq
      // 音量包络：快速淡入 + 指数淡出，避免爆音
      gain.gain.setValueAtTime(0, base + note.start)
      gain.gain.linearRampToValueAtTime(0.18, base + note.start + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, base + note.start + note.duration)
      osc.connect(gain).connect(ctx.destination)
      osc.start(base + note.start)
      osc.stop(base + note.start + note.duration + 0.02)
    }
  } catch {
    /* 提示音是锦上添花，任何失败都静默 */
  }
}
