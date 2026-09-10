// 滚动显现指令（v-reveal）：元素进入视口时执行一次上浮显现动效。
// 纯视觉增强——不改动任何布局参数与交互逻辑；
// 尊重 prefers-reduced-motion 与不支持 IntersectionObserver 的环境（直接正常显示）。
import type { Directive } from 'vue'

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const observer =
  typeof IntersectionObserver !== 'undefined' && !reducedMotion
    ? new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue
            entry.target.classList.add('is-revealed')
            observer?.unobserve(entry.target)
          }
        },
        { threshold: 0.12, rootMargin: '0px 0px -8% 0px' },
      )
    : null

export const vReveal: Directive<HTMLElement> = {
  mounted(el) {
    // 无观察能力时不加 reveal-item 基类，元素保持默认可见
    if (!observer) return
    el.classList.add('reveal-item')
    observer.observe(el)
  },
  unmounted(el) {
    observer?.unobserve(el)
  },
}
