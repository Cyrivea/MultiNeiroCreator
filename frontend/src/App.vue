<template>
  <div class="app">
    <ParticleBackground v-if="showParticleBackground" />
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" :key="route.fullPath" />
      </transition>
    </router-view>
    <!-- 全局过渡覆盖层：受 loading store 控制，与路由完全解耦 -->
    <LoadingOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ParticleBackground from '@/components/ParticleBackground.vue'
import LoadingOverlay from '@/components/LoadingOverlay.vue'

const route = useRoute()

const showParticleBackground = computed(() => route.path === '/home' || route.path === '/login')
</script>

<style>
.app { width: 100%; min-height: 100vh; position: relative; }

.page-enter-active { animation: fadeIn 0.5s ease; }
.page-leave-active { animation: fadeOut 0.4s ease; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeOut {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-8px); }
}
</style>
