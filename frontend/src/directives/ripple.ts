import type { Directive } from 'vue'

export const vRipple: Directive = {
  mounted(el: HTMLElement) {
    el.style.position = 'relative'
    el.style.overflow = 'hidden'
    el.style.transform = 'translateZ(0)'

    const onEnter = (e: MouseEvent) => {
      // 果冻放大
      el.style.transition = 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease'
      el.style.transform = 'scale(1.06) translateZ(0)'
      el.style.boxShadow = '0 0 24px rgba(139,92,246,0.35), inset 0 1px 0 rgba(255,255,255,0.15)'

      // 波纹
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const maxR = Math.max(
        Math.hypot(x, y),
        Math.hypot(x - rect.width, y),
        Math.hypot(x, y - rect.height),
        Math.hypot(x - rect.width, y - rect.height)
      )

      const ripple = document.createElement('span')
      ripple.style.cssText = `
        position: absolute;
        left: ${x}px;
        top: ${y}px;
        width: 0;
        height: 0;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        background: radial-gradient(circle, rgba(255,255,255,0.35) 0%, rgba(139,92,246,0.2) 40%, transparent 70%);
        pointer-events: none;
        animation: ripple-wave 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        --r: ${maxR * 2}px;
      `
      el.appendChild(ripple)
      setTimeout(() => ripple.remove(), 600)
    }

    const onLeave = () => {
      el.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease'
      el.style.transform = 'scale(1) translateZ(0)'
      el.style.boxShadow = ''
    }

    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)
    ;(el as any)._rippleCleanup = () => {
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
    }
  },
  unmounted(el: HTMLElement) {
    ;(el as any)._rippleCleanup?.()
  },
}
