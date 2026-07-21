<template>
  <div class="intro-page" @click="handleStart">
    <canvas ref="canvas" class="intro-canvas" aria-hidden="true" />
    <div class="intro-vignette"></div>

    <Transition name="intro-copy">
      <div v-if="introState === 'intro'" class="intro-copy">
        <div class="intro-kicker">AI Native Creative Workstation</div>
        <h1 class="intro-title">Enter MultiNeiroCreator</h1>
        <p class="intro-description">
          Composition, lyrics, visuals, PV workflow, and Neyria live inside one creative surface.
        </p>
        <button class="intro-button" type="button">开始进入</button>
        <div class="intro-tip">Click anywhere to begin</div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

interface IntroParticleNode {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  alpha: number
  sphereX: number
  sphereY: number
  sphereZ: number
}

const router = useRouter()
const canvas = ref<HTMLCanvasElement | null>(null)
const introState = ref<'intro' | 'exploding'>('intro')

let animationFrameId = 0
let introEntered = false

function initIntroBackground() {
  const element = canvas.value
  if (!element) return

  const context = element.getContext('2d')
  if (!context) return

  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const nodes: IntroParticleNode[] = []
  const totalParticles = 720

  let width = 0
  let height = 0
  let sphereRotationAngle = 0

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
    const radiusSphere = Math.min(width, height) * 0.23

    for (let index = 0; index < totalParticles; index += 1) {
      const phi = Math.acos(1 - (2 * (index + 0.5)) / totalParticles)
      const theta = Math.PI * (1 + Math.sqrt(5)) * (index + 0.5)

      const sphereX = width / 2 + radiusSphere * Math.sin(phi) * Math.cos(theta)
      const sphereY = height / 2 + radiusSphere * Math.sin(phi) * Math.sin(theta)
      const sphereZ = radiusSphere * Math.cos(phi)

      nodes.push({
        x: sphereX,
        y: sphereY,
        vx: 0,
        vy: 0,
        radius: 0.8 + Math.random() * 1.4,
        alpha: 0.28 + Math.random() * 0.56,
        sphereX,
        sphereY,
        sphereZ,
      })
    }
  }

  const onResize = () => {
    resize()
    buildNodes()
  }

  const draw = () => {
    context.clearRect(0, 0, width, height)

    if (introState.value === 'intro') {
      sphereRotationAngle += 0.008
      const centerX = width / 2
      const centerY = height / 2
      const radiusSphere = Math.min(width, height) * 0.23

      for (const node of nodes) {
        const cos = Math.cos(sphereRotationAngle)
        const sin = Math.sin(sphereRotationAngle)
        const ox = node.sphereX - centerX
        const oz = node.sphereZ

        const rx = ox * cos - oz * sin
        const rz = ox * sin + oz * cos
        const perspective = 560 / (560 + rz)

        node.x = centerX + rx * perspective
        node.y = centerY + (node.sphereY - centerY) * perspective

        const depthAlpha = node.alpha * (0.4 + 0.6 * ((rz + radiusSphere) / (2 * radiusSphere)))

        context.beginPath()
        context.arc(node.x, node.y, node.radius * perspective, 0, Math.PI * 2)
        context.fillStyle = `rgba(255, 255, 255, ${Math.max(0.1, depthAlpha)})`
        context.fill()
      }
    } else {
      let allSettled = true
      const centerX = width / 2
      const centerY = height / 2

      for (const node of nodes) {
        if (node.vx === 0 && node.vy === 0) {
          const angle = Math.atan2(node.y - centerY, node.x - centerX)
          const speed = 18 + Math.random() * 26
          node.vx = Math.cos(angle) * speed
          node.vy = Math.sin(angle) * speed
        }

        node.x += node.vx
        node.y += node.vy
        node.vx *= 0.9
        node.vy *= 0.9

        if (Math.abs(node.vx) > 0.8 || Math.abs(node.vy) > 0.8) {
          allSettled = false
        }

        context.beginPath()
        context.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
        context.fillStyle = `rgba(255, 255, 255, ${node.alpha})`
        context.fill()
      }

      if (allSettled && !introEntered) {
        introEntered = true
        router.push('/home')
      }
    }

    animationFrameId = window.requestAnimationFrame(draw)
  }

  resize()
  buildNodes()
  draw()

  window.addEventListener('resize', onResize)

  return () => {
    window.removeEventListener('resize', onResize)
  }
}

function handleStart() {
  if (introState.value !== 'intro' || introEntered) return
  introState.value = 'exploding'
}

let cleanup: (() => void) | undefined

onMounted(() => {
  cleanup = initIntroBackground()
})

onUnmounted(() => {
  window.cancelAnimationFrame(animationFrameId)
  cleanup?.()
})
</script>

<style scoped>
.intro-page {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #0b0b0b;
  color: #ffffff;
  cursor: pointer;
}

.intro-canvas,
.intro-vignette {
  position: absolute;
  inset: 0;
}

.intro-canvas {
  width: 100%;
  height: 100%;
}

.intro-vignette {
  pointer-events: none;
  background:
    radial-gradient(circle at center, transparent 40%, rgba(0, 0, 0, 0.58) 100%),
    linear-gradient(180deg, rgba(0, 0, 0, 0.08), rgba(0, 0, 0, 0.32));
}

.intro-copy {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px;
}

.intro-kicker {
  color: rgba(255, 255, 255, 0.48);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.intro-title {
  margin-top: 18px;
  font-size: clamp(34px, 5vw, 62px);
  line-height: 0.96;
  letter-spacing: -0.06em;
  font-weight: 700;
}

.intro-description {
  margin-top: 16px;
  max-width: 560px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 16px;
  line-height: 1.75;
}

.intro-button {
  margin-top: 24px;
  min-height: 44px;
  padding: 0 20px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  cursor: pointer;
}

.intro-tip {
  margin-top: 16px;
  color: rgba(255, 255, 255, 0.38);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.intro-copy-enter-active,
.intro-copy-leave-active {
  transition: opacity 260ms ease;
}

.intro-copy-enter-from,
.intro-copy-leave-to {
  opacity: 0;
}
</style>
