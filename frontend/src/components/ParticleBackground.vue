<template>
  <canvas ref="canvas" class="particle-canvas" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement | null>(null)
let animId = 0
const mouse = { x: -9999, y: -9999 }

function initParticles() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')!
  let W = c.width = window.innerWidth
  let H = c.height = window.innerHeight

  type P = { x: number; y: number; vx: number; vy: number; ox: number; oy: number; r: number; a: number }
  const particles: P[] = []
  const COUNT = 400

  for (let i = 0; i < COUNT; i++) {
    const x = Math.random() * W
    const y = Math.random() * H
    particles.push({
      x, y, ox: x, oy: y,
      vx: (Math.random() - 0.5) * 1.0,
      vy: (Math.random() - 0.5) * 1.0,
      r: Math.random() * 1.8 + 0.4,
      a: Math.random() * 0.4 + 0.15,
    })
  }

  const REPEL_RADIUS = 120
  const REPEL_STRENGTH = 6

  const onResize = () => { W = c.width = window.innerWidth; H = c.height = window.innerHeight }
  const onMouse = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY }
  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onMouse)

  function draw() {
    ctx.clearRect(0, 0, W, H)
    for (const p of particles) {
      p.ox += p.vx; p.oy += p.vy
      if (p.ox < 0 || p.ox > W) p.vx *= -1
      if (p.oy < 0 || p.oy > H) p.vy *= -1
      const dx = p.ox - mouse.x
      const dy = p.oy - mouse.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < REPEL_RADIUS && dist > 0) {
        const force = (1 - dist / REPEL_RADIUS) * REPEL_STRENGTH
        p.x += (dx / dist) * force
        p.y += (dy / dist) * force
      }
      p.x += (p.ox - p.x) * 0.08
      p.y += (p.oy - p.y) * 0.08
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(139,92,246,${p.a})`
      ctx.fill()
    }
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < 90) {
          ctx.beginPath()
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(139,92,246,${0.12 * (1 - d / 90)})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }
    animId = requestAnimationFrame(draw)
  }
  draw()
  return () => { window.removeEventListener('resize', onResize); window.removeEventListener('mousemove', onMouse) }
}

let cleanup: (() => void) | undefined
onMounted(() => { cleanup = initParticles() })
onUnmounted(() => { cancelAnimationFrame(animId); cleanup?.() })
</script>

<style scoped>
.particle-canvas {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
</style>
