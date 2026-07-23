<template>
  <WorkstationLayout :key="workstationKey" @ready="onLayoutReady" />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import WorkstationLayout from './layout/WorkstationLayout.vue'
import { useLoadingStore } from '@/stores/loading'

const route = useRoute()
const loadingStore = useLoadingStore()
const workstationKey = computed(() => String(route.query.project ?? 'default'))

// 工作站所有核心资源加载、初始化流程全部完成后，触发覆盖层优雅淡出。
// 时机由 WorkstationLayout 在 loadAgentPanel 等关键流程完成后通过 emit('ready') 给出。
function onLayoutReady() {
  loadingStore.hide()
}

onMounted(() => {
  // 兜底：若 layout 因异常未发出 ready，组件挂载 6s 后强制收尾，
  // 避免覆盖层在异常路径下永远挂着。
  setTimeout(() => {
    if (loadingStore.visible) {
      loadingStore.hide()
    }
  }, 6000)
})
</script>

<style scoped>
</style>
