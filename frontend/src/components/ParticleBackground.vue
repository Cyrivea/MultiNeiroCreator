<template>
  <div class="particle-background" aria-hidden="true">
    <canvas ref="canvas" class="particle-canvas" />
    <div class="particle-vignette"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

interface ParticleNode {
  homeX: number
  homeY: number
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  alpha: number
  phase: number
  drift: number
}

const canvas = ref<HTMLCanvasElement | null>(null)
let animationFrameId = 0
const pointer = { x: -9999, y: -9999, targetX: -9999, targetY: -9999, active: false }

function initParticles() {
  const element = canvas.value
  if (!element) return

  const context = element.getContext('2d')
  if (!context) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const nodes: ParticleNode[] = []

  let width = 0
  let height = 0
  let time = 0

  const resize = () => {
    width = window.innerWidth
    height = window.innerHeight
    element.width = Math.round(width * dpr)
    element.height = Math.round(height * dpr)
    element.style.width = `${width}px`
    element.style.height = `${height}px`
    context.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  const buildNodes = () => {
    nodes.length = 0
    const spacing = prefersReducedMotion ? 35 : Math.max(22, Math.min(30, width / 55))

    for (let y = spacing * 0.5; y < height + spacing; y += spacing) {
      for (let x = spacing * 0.5; x < width + spacing; x += spacing) {
        const homeX = x + (Math.random() - 0.5) * spacing * 0.45
        const homeY = y + (Math.random() - 0.5) * spacing * 0.45

        nodes.push({
          homeX,
          homeY,
          x: homeX,
          y: homeY,
          vx: 0,
          vy: 0,
          radius: 0.8 + Math.random() * 1.5,
          alpha: 0.2 + Math.random() * 0.6,
          phase: Math.random() * Math.PI * 2,
          drift: 1.2 + Math.random() * 3.0,
        })
      }
    }
  }

  const onResize = () => {
    resize()
    buildNodes()
  }

  const onPointerMove = (event: MouseEvent) => {
    pointer.targetX = event.clientX
    pointer.targetY = event.clientY
    if (!pointer.active) {
      pointer.x = event.clientX
      pointer.y = event.clientY
    }
    pointer.active = true
  }

  const onPointerLeave = () => {
    pointer.active = false
    pointer.targetX = -9999
    pointer.targetY = -9999
  }

  const draw = () => {
    context.clearRect(0, 0, width, height)
    time += prefersReducedMotion ? 0.004 : 0.008

    if (pointer.active) {
      pointer.x += (pointer.targetX - pointer.x) * 0.12
      pointer.y += (pointer.targetY - pointer.y) * 0.12
    } else {
      pointer.x += (-9999 - pointer.x) * 0.05
      pointer.y += (-9999 - pointer.y) * 0.05
    }

    const repelRadius = 280
    const repelStrength = 4.5
    const springStrength = 0.028
    const damping = 0.84

    for (const node of nodes) {
      const driftX = Math.sin(time + node.phase) * node.drift
      const driftY = Math.cos(time * 0.75 + node.phase * 1.2) * node.drift * 0.8
      const targetX = node.homeX + driftX
      const targetY = node.homeY + driftY

      const dx = node.x - pointer.x
      const dy = node.y - pointer.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      if (distance < repelRadius && distance > 0) {
        const force = (1 - distance / repelRadius) ** 1.8 * repelStrength
        node.vx += (dx / distance) * force
        node.vy += (dy / distance) * force
      }

      node.vx += (targetX - node.x) * springStrength
      node.vy += (targetY - node.y) * springStrength
      node.vx *= damping
      node.vy *= damping
      node.x += node.vx
      node.y += node.vy

      context.beginPath()
      context.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
      context.fillStyle = `rgba(255, 255, 255, ${node.alpha})`
      context.fill()
    }

    animationFrameId = window.requestAnimationFrame(draw)
  }

  resize()
  buildNodes()
  draw()

  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onPointerMove)
  window.addEventListener('mouseleave', onPointerLeave)

  return () => {
    window.removeEventListener('resize', onResize)
    window.removeEventListener('mousemove', onPointerMove)
    window.removeEventListener('mouseleave', onPointerLeave)
  }
}

let cleanup: (() => void) | undefined

onMounted(() => {
  cleanup = initParticles()
})

onUnmounted(() => {
  window.cancelAnimationFrame(animationFrameId)
  cleanup?.()
})
</script>

<style scoped>
.particle-background {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.particle-canvas,
.particle-vignette {
  position: absolute;
  inset: 0;
}

.particle-canvas {
  width: 100%;
  height: 100%;
}

.particle-vignette {
  pointer-events: none;
  background:
    radial-gradient(circle at center, transparent 40%, rgba(0, 0, 0, 0.6) 100%),
    linear-gradient(180deg, rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.4));
}
</style>
