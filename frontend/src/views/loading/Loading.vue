<template>
  <!--
    过渡加载页：登录 / 注册成功后驻留展示，加载动画完整播放后渐隐切入工作站。
    动效全部基于 transform / opacity（GPU 合成层），无 canvas 循环、无第三方库 —— 保证 60fps 且体积极小。
    视觉概念「Ignition」：从近乎单色的登录态，绽放为工作站的霓虹 Y2K 品牌色，隐喻「进入创作界面」。
  -->
  <div
    class="loading-page"
    :class="{ 'is-leaving': leaving }"
    :style="{ '--exit': EXIT + 'ms' }"
    role="status"
    aria-live="polite"
  >
    <!-- 背景光晕 -->
    <div class="aura" aria-hidden="true"></div>
    <div class="grid-veil" aria-hidden="true"></div>

    <!-- 主体：同心环 + 品牌核 -->
    <div class="stage">
      <div class="rings" aria-hidden="true">
        <span class="ring ring--outer"></span>
        <span class="ring ring--mid"></span>
        <span class="ring ring--inner"></span>
        <span class="core"></span>
        <span class="spark spark--a"></span>
        <span class="spark spark--b"></span>
        <span class="spark spark--c"></span>
      </div>

      <div class="brand">
        <div class="brand-mark">MNC</div>
        <div class="brand-name">MultiNeiroCreator</div>
      </div>

      <div class="status-line">
        <span class="status-text">{{ label }}</span>
        <span class="status-pct">{{ Math.round(progress) }}%</span>
      </div>

      <!-- 确定性进度条：与驻留时长绑定 -->
      <div class="track" aria-hidden="true">
        <span class="track-fill" :style="{ transform: `scaleX(${progress / 100})` }"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 目标页与驻留时长可通过路由 query 覆盖：/loading?next=/workstation&dwell=2200&mode=register
const next = (route.query.next as string) || '/workstation'
const mode = (route.query.mode as string) === 'register' ? 'register' : 'login'
const prefersReduced =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// 驻留时长：确保入场 + 循环动画完整展示；reduced-motion 下大幅缩短
const DWELL = prefersReduced ? 600 : Math.max(1200, Number(route.query.dwell) || 2400)
const EXIT = prefersReduced ? 200 : 620 // 渐隐退场时长，与 CSS 一致

const label = ref(mode === 'register' ? 'Provisioning your studio' : 'Preparing your workspace')
const progress = ref(0)
const leaving = ref(false)

let rafId = 0
let startTs = 0
let exitTimer: ReturnType<typeof setTimeout> | undefined
let navTimer: ReturnType<typeof setTimeout> | undefined

// easeOutCubic —— 进度前段快、末段稳，观感更「加载」而非线性
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3)

function tick(now: number) {
  if (!startTs) startTs = now
  const elapsed = now - startTs
  const t = Math.min(1, elapsed / DWELL)
  progress.value = easeOut(t) * 100

  if (t < 1) {
    rafId = requestAnimationFrame(tick)
  } else {
    progress.value = 100
    label.value = 'Entering'
    // 触发渐隐退场，动画结束后平滑切换路由
    leaving.value = true
    navTimer = setTimeout(() => router.replace(next), EXIT)
  }
}

onMounted(() => {
  rafId = requestAnimationFrame(tick)
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  if (exitTimer) clearTimeout(exitTimer)
  if (navTimer) clearTimeout(navTimer)
})
</script>

<style scoped>
/* 品牌令牌（对齐工作站 y2k-theme.css，不新增游离色相） */
.loading-page {
  --bg-a: #040405;
  --bg-b: #060610;
  --text: #f4f4f4;
  --neon-green: #39ff14;
  --cyan: #06b6d4;
  --pink: #ff00ff;
  --purple: #8b5cf6;

  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  overflow: hidden;
  background:
    radial-gradient(120% 120% at 50% 40%, var(--bg-b) 0%, var(--bg-a) 70%);
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  /* 入场：整页淡入上浮 */
  animation: page-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  transition: opacity var(--exit, 620ms) ease, filter var(--exit, 620ms) ease;
}

/* 渐隐退场：整页 blur + 上浮 + 淡出，霓虹绽放后平滑切走 */
.loading-page.is-leaving {
  opacity: 0;
  filter: blur(14px);
  transform: scale(1.04);
}

@keyframes page-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 背景霓虹光晕：缓慢呼吸，退场时增强绽放 */
.aura {
  position: absolute;
  width: min(78vw, 620px);
  aspect-ratio: 1;
  border-radius: 50%;
  background:
    radial-gradient(circle at 42% 40%, rgba(57, 255, 20, 0.16), transparent 60%),
    radial-gradient(circle at 62% 60%, rgba(6, 182, 212, 0.18), transparent 62%),
    radial-gradient(circle at 55% 48%, rgba(139, 92, 246, 0.12), transparent 66%);
  filter: blur(18px);
  animation: aura-breathe 4.2s ease-in-out infinite;
  will-change: transform, opacity;
}
.is-leaving .aura { animation: none; opacity: 1; transform: scale(1.5); filter: blur(26px); }

@keyframes aura-breathe {
  0%, 100% { transform: scale(0.92); opacity: 0.75; }
  50%      { transform: scale(1.06); opacity: 1; }
}

/* 细网格纱幕：微弱科技质感 */
.grid-veil {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.028) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.028) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: radial-gradient(circle at center, #000 0%, transparent 72%);
  -webkit-mask-image: radial-gradient(circle at center, #000 0%, transparent 72%);
  opacity: 0.6;
}

.stage {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(20px, 4vh, 34px);
  padding: 24px;
  width: min(90vw, 460px);
}

/* 同心环容器 */
.rings {
  position: relative;
  width: clamp(140px, 34vw, 200px);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  /* 入场：从 0 放大回弹 */
  animation: rings-in 0.72s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
@keyframes rings-in {
  from { opacity: 0; transform: scale(0.5) rotate(-25deg); }
  to   { opacity: 1; transform: scale(1) rotate(0); }
}

.ring {
  position: absolute;
  border-radius: 50%;
  border: 2px solid transparent;
  will-change: transform;
}
/* 三层环：不同尺寸 / 转速 / 方向，形成流畅层次 */
.ring--outer {
  inset: 0;
  border-top-color: var(--neon-green);
  border-right-color: rgba(57, 255, 20, 0.25);
  box-shadow: 0 0 16px rgba(57, 255, 20, 0.28), inset 0 0 12px rgba(57, 255, 20, 0.12);
  animation: spin 2.4s linear infinite;
}
.ring--mid {
  inset: 15%;
  border-bottom-color: var(--cyan);
  border-left-color: rgba(6, 182, 212, 0.25);
  box-shadow: 0 0 14px rgba(6, 182, 212, 0.3), inset 0 0 10px rgba(6, 182, 212, 0.12);
  animation: spin-rev 1.8s linear infinite;
}
.ring--inner {
  inset: 31%;
  border-top-color: var(--purple);
  border-right-color: var(--pink);
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.3);
  animation: spin 1.3s linear infinite;
}

/* 中心核：呼吸脉冲 */
.core {
  position: absolute;
  width: 22%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle, #fff 0%, var(--neon-green) 55%, rgba(57, 255, 20, 0) 100%);
  box-shadow: 0 0 22px rgba(57, 255, 20, 0.7);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(0.82); opacity: 0.9; }
  50%      { transform: scale(1.1); opacity: 1; }
}

/* 环绕轨道上的高光点，增强旋转感 */
.spark {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  top: 50%;
  left: 50%;
  margin: -3px;
  will-change: transform;
}
.spark--a {
  background: var(--neon-green);
  box-shadow: 0 0 10px var(--neon-green);
  animation: orbit 2.4s linear infinite;
  --orbit: clamp(70px, 17vw, 100px);
}
.spark--b {
  background: var(--cyan);
  box-shadow: 0 0 10px var(--cyan);
  animation: orbit 1.8s linear infinite reverse;
  --orbit: clamp(54px, 13vw, 76px);
}
.spark--c {
  background: var(--pink);
  box-shadow: 0 0 8px var(--pink);
  animation: orbit 1.3s linear infinite;
  --orbit: clamp(38px, 9vw, 54px);
}
@keyframes orbit {
  from { transform: rotate(0) translateX(var(--orbit)) rotate(0); }
  to   { transform: rotate(360deg) translateX(var(--orbit)) rotate(-360deg); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes spin-rev {
  to { transform: rotate(-360deg); }
}

/* 品牌字标 */
.brand {
  text-align: center;
  animation: fade-up 0.6s ease 0.15s both;
}
.brand-mark {
  font-size: clamp(26px, 6vw, 34px);
  font-weight: 800;
  letter-spacing: 0.18em;
  color: var(--text);
  text-shadow: 0 0 18px rgba(57, 255, 20, 0.35);
}
.brand-name {
  margin-top: 6px;
  font-size: clamp(11px, 2.6vw, 13px);
  font-weight: 600;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: rgba(244, 244, 244, 0.5);
}

.status-line {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  animation: fade-up 0.6s ease 0.28s both;
}
.status-text {
  font-size: clamp(11px, 2.4vw, 12px);
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(244, 244, 244, 0.62);
}
.status-pct {
  font-size: clamp(11px, 2.4vw, 12px);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--neon-green);
  font-variant-numeric: tabular-nums;
}

/* 确定性进度条 */
.track {
  position: relative;
  width: 100%;
  height: 3px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
  animation: fade-up 0.6s ease 0.36s both;
}
.track-fill {
  position: absolute;
  inset: 0;
  transform-origin: left center;
  transform: scaleX(0);
  border-radius: 999px;
  background: linear-gradient(90deg, var(--cyan), var(--neon-green));
  box-shadow: 0 0 12px rgba(57, 255, 20, 0.5);
  /* 进度由 JS 平滑推进，此处过渡兜平帧间跳变 */
  transition: transform 0.12s linear;
}

@keyframes fade-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 无障碍：尊重减少动态偏好 —— 停掉旋转/呼吸，仅保留进度与淡入淡出 */
@media (prefers-reduced-motion: reduce) {
  .loading-page,
  .rings,
  .brand,
  .status-line,
  .track { animation: none; }
  .ring,
  .core,
  .spark,
  .aura { animation: none !important; }
  .ring--outer { border-color: var(--neon-green) transparent transparent transparent; }
}
</style>
