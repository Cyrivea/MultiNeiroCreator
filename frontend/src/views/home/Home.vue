<template>
  <div class="home">
    <canvas ref="canvas" class="particle-canvas" />

    <header class="navbar">
      <div class="inner">
        <div class="nav-logo">MultiNeiroCreator<span class="dot">.</span></div>
        <nav class="nav-links">
          <a href="#features">Features</a>
          <a href="#demo">Demo</a>
          <a href="#about">About</a>
        </nav>
        <div class="nav-actions">
          <router-link to="/login" class="btn-login">Sign in</router-link>
          <router-link to="/login" class="btn-register" v-ripple>Get Started</router-link>
        </div>
        <button class="menu-btn" @click="menuOpen = !menuOpen">☰</button>
      </div>
      <div v-if="menuOpen" class="mobile-menu">
        <a href="#features" @click="menuOpen=false">Features</a>
        <a href="#demo" @click="menuOpen=false">Demo</a>
        <router-link to="/login" @click="menuOpen=false">Sign in / Register</router-link>
      </div>
    </header>

    <section class="hero-section">
      <div class="inner hero">
        <div class="hero-left">
          <div class="hero-tag">AI Multi-modal Creation Platform</div>
          <h1 class="hero-title">
            Create anything,<br />
            starting from a <span class="gradient-text">single idea.</span>
          </h1>
          <p class="hero-desc">
            Audio generation, lyric alignment, PV production, image creation.<br />
            Multiple AI Agents collaborate in parallel to bring your ideas to life.
          </p>
          <div class="hero-btns">
            <router-link to="/login" class="btn-primary" v-ripple>Start Creating →</router-link>
            <a href="#demo" class="btn-ghost" v-ripple>Watch Demo</a>
          </div>
        </div>
        <div class="hero-right">
          <div class="demo-placeholder">
            <div class="demo-inner">
              <div class="demo-icon">▶</div>
              <p>Product Demo</p>
              <span>Video / GIF coming soon</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="features-section" id="features">
      <div class="inner">
        <div class="section-header">
          <h2>Four Creative Modules</h2>
          <p>Each module is powered by a dedicated Agent, working together to complete complex creative tasks.</p>
        </div>
        <div class="features-grid">
          <div v-for="f in features" :key="f.title" class="feature-card">
            <div class="feature-icon">{{ f.icon }}</div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
            <div class="feature-tags">
              <span v-for="tag in f.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="demo-section" id="demo">
      <div class="inner">
        <div class="section-header">
          <div class="demo-label">DEMO</div>
          <h2>See Agents in Action</h2>
          <p>From a single creative prompt, multiple Agents decompose the task and deliver results in parallel.</p>
        </div>
        <div class="demo-video-placeholder">
          <span>Demo Video / GIF Placeholder</span>
        </div>
      </div>
    </section>

    <footer class="footer-section">
      <div class="inner footer">
        <span class="footer-logo">MultiNeiroCreator<span class="dot">.</span></span>
        <span class="footer-copy">© 2025 MultiNeiroCreator · AI Creation Workstation</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref<HTMLCanvasElement | null>(null)
const menuOpen = ref(false)
let animId = 0
const mouse = { x: -9999, y: -9999 }

const features = [
  { icon: '🎵', title: 'Audio Creation', desc: 'Upload a reference audio and let AI generate acoustically similar samples. Search targeted audio libraries across the web to find exactly what you need.', tags: ['Audio Generation', 'Sample Search', 'AudioCraft'] },
  { icon: '✍️', title: 'Lyric Generation', desc: 'Parse MIDI note duration and melody, auto-generate syllable-aligned lyrics for virtual vocalist workflows. Designed for Vocaloid producers.', tags: ['MIDI Parsing', 'Syllable Align', 'Lyric Craft'] },
  { icon: '🎬', title: 'PV Production', desc: 'Generate character-driven music videos with lyric subtitles that sync to MIDI beats automatically. Supports Vocaloid-style animated text effects.', tags: ['Video Gen', 'Subtitle Sync', 'Kling API'] },
  { icon: '🖼️', title: 'Image Creation', desc: 'Generate high-quality images from creative prompts. Auto background removal outputs transparent PNG files ready for PV compositing.', tags: ['Image Gen', 'Smart Cutout', 'FLUX'] },
]

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

  const onResize = () => {
    W = c.width = window.innerWidth
    H = c.height = window.innerHeight
  }
  const onMouse = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY }
  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onMouse)

  function draw() {
    ctx.clearRect(0, 0, W, H)

    for (const p of particles) {
      // drift
      p.ox += p.vx
      p.oy += p.vy
      if (p.ox < 0 || p.ox > W) p.vx *= -1
      if (p.oy < 0 || p.oy > H) p.vy *= -1

      // mouse repel
      const dx = p.ox - mouse.x
      const dy = p.oy - mouse.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < REPEL_RADIUS && dist > 0) {
        const force = (1 - dist / REPEL_RADIUS) * REPEL_STRENGTH
        p.x += (dx / dist) * force
        p.y += (dy / dist) * force
      }
      // lerp back to orbit
      p.x += (p.ox - p.x) * 0.08
      p.y += (p.oy - p.y) * 0.08

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(139,92,246,${p.a})`
      ctx.fill()
    }

    // connections
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

  return () => {
    window.removeEventListener('resize', onResize)
    window.removeEventListener('mousemove', onMouse)
  }
}

let cleanup: (() => void) | undefined
onMounted(() => { cleanup = initParticles() })
onUnmounted(() => { cancelAnimationFrame(animId); cleanup?.() })
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

.home {
  width: 100%;
  background: #060610;
  color: #fff;
  overflow-x: hidden;
  font-family: 'Outfit', system-ui, sans-serif;
}

.particle-canvas {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.inner {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 40px;
  box-sizing: border-box;
}

/* Navbar */
.navbar {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  width: 100%;
  backdrop-filter: blur(16px);
  background: rgba(6,6,16,0.75);
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.navbar .inner {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 40px;
}
.nav-logo {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  flex-shrink: 0;
}
.dot { color: #8b5cf6; }
.nav-links { display: flex; gap: 32px; flex: 1; }
.nav-links a {
  color: #666;
  text-decoration: none;
  font-size: 14px;
  font-weight: 400;
  letter-spacing: 0.01em;
  transition: color 0.2s;
}
.nav-links a:hover { color: #fff; }
.nav-actions { display: flex; gap: 12px; align-items: center; flex-shrink: 0; }
.btn-login {
  color: #777;
  text-decoration: none;
  font-size: 14px;
  padding: 8px 16px;
  transition: color 0.2s;
}
.btn-login:hover { color: #fff; }
.btn-register {
  background: #8b5cf6;
  color: #fff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  padding: 8px 20px;
  border-radius: 8px;
  white-space: nowrap;
  transition: background 0.2s;
}
.btn-register:hover { background: #7c3aed; }
.menu-btn { display: none; background: none; border: none; color: #fff; font-size: 20px; cursor: pointer; margin-left: auto; }
.mobile-menu { display: flex; flex-direction: column; padding: 12px 40px 16px; gap: 12px; border-top: 1px solid rgba(255,255,255,0.05); }
.mobile-menu a { color: #aaa; text-decoration: none; font-size: 15px; padding: 8px 0; }

/* Hero */
.hero-section {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: 100vh;
  display: flex;
  align-items: center;
}
.hero {
  display: flex;
  align-items: center;
  gap: 80px;
  padding-top: 64px;
  min-height: 100vh;
}
.hero-left { flex: 1; min-width: 0; }
.hero-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8b5cf6;
  border: 1px solid rgba(139,92,246,0.35);
  border-radius: 20px;
  padding: 5px 14px;
  margin-bottom: 28px;
}
.hero-title {
  font-size: clamp(36px, 4.5vw, 68px);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-bottom: 24px;
  color: #f0f0f0;
}
.gradient-text {
  background: linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-desc {
  font-size: clamp(14px, 1.3vw, 16px);
  font-weight: 300;
  color: #666;
  line-height: 1.9;
  margin-bottom: 40px;
  letter-spacing: 0.01em;
}
.hero-btns { display: flex; gap: 14px; flex-wrap: wrap; }
.btn-primary {
  background: #8b5cf6;
  color: #fff;
  text-decoration: none;
  padding: 13px 26px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.2s, transform 0.15s;
}
.btn-primary:hover { background: #7c3aed; transform: translateY(-1px); }
.btn-ghost {
  color: #777;
  text-decoration: none;
  padding: 13px 26px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 400;
  border: 1px solid rgba(255,255,255,0.1);
  white-space: nowrap;
  transition: border-color 0.2s, color 0.2s;
}
.btn-ghost:hover { border-color: rgba(255,255,255,0.25); color: #ccc; }
.hero-right { flex: 1; min-width: 0; }
.demo-placeholder {
  width: 100%;
  aspect-ratio: 16/9;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.demo-inner { text-align: center; }
.demo-icon { font-size: 32px; margin-bottom: 12px; opacity: 0.25; }
.demo-inner p { font-size: 13px; color: #444; margin-bottom: 4px; font-weight: 400; }
.demo-inner span { font-size: 11px; color: #333; }

/* Section shared */
.section-header { text-align: center; margin-bottom: 56px; }
.section-header h2 {
  font-size: clamp(24px, 3vw, 40px);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-bottom: 14px;
  color: #e8e8e8;
}
.section-header p { font-size: 15px; color: #555; font-weight: 300; line-height: 1.7; }

/* Features */
.features-section {
  position: relative;
  z-index: 1;
  width: 100%;
  padding: 120px 0;
  border-top: 1px solid rgba(255,255,255,0.04);
}
.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}
.feature-card {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px;
  padding: 32px 26px;
  transition: border-color 0.25s, transform 0.25s;
}
.feature-card:hover {
  border-color: rgba(139,92,246,0.25);
  transform: translateY(-3px);
}
.feature-icon { font-size: 28px; margin-bottom: 18px; }
.feature-card h3 {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-bottom: 10px;
  color: #e0e0e0;
}
.feature-card p {
  font-size: 13px;
  color: #666;
  line-height: 1.75;
  margin-bottom: 20px;
  font-weight: 300;
}
.feature-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: #8b5cf6;
  border: 1px solid rgba(139,92,246,0.25);
  border-radius: 20px;
  padding: 3px 10px;
}

/* Demo */
.demo-section {
  position: relative;
  z-index: 1;
  width: 100%;
  padding: 120px 0;
  border-top: 1px solid rgba(255,255,255,0.04);
}
.demo-section .inner { text-align: center; }
.demo-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2em;
  color: #8b5cf6;
  margin-bottom: 20px;
}
.demo-video-placeholder {
  width: 100%;
  max-width: 860px;
  margin: 48px auto 0;
  aspect-ratio: 16/9;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
  font-size: 13px;
  font-weight: 300;
}

/* Footer */
.footer-section {
  position: relative;
  z-index: 1;
  width: 100%;
  border-top: 1px solid rgba(255,255,255,0.05);
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 28px;
  padding-bottom: 28px;
  flex-wrap: wrap;
  gap: 12px;
}
.footer-logo { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
.footer-copy { font-size: 12px; color: #444; font-weight: 300; }

/* Responsive */
@media (max-width: 768px) {
  .inner { padding: 0 20px; }
  .hero { flex-direction: column; padding-top: 80px; min-height: auto; padding-bottom: 60px; gap: 40px; }
  .hero-right { width: 100%; }
  .nav-links, .nav-actions { display: none; }
  .menu-btn { display: block; }
  .features-grid { grid-template-columns: 1fr; }
}
</style>
