<template>
  <div class="workstation-sidebar y2k-border">
    <!-- Tab 导航 -->
    <div class="sidebar-tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        :class="['sidebar-tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        {{ tab.icon }} {{ tab.label }}
      </button>
    </div>
    
    <!-- Tab 内容区域 -->
    <div class="sidebar-content">
      <p style="color: var(--text-secondary); font-size: 13px;">
        {{ getActiveTabLabel() }} 内容区域
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Tab {
  id: string
  label: string
  icon: string
}

const tabs: Tab[] = [
  { id: 'midi', label: 'MIDI', icon: '🎹' },
  { id: 'audio', label: 'Audio', icon: '🎵' },
  { id: 'assets', label: 'Assets', icon: '🖼️' },
  { id: 'project', label: 'Project', icon: '📁' }
]

const activeTab = ref<string>('midi')

function getActiveTabLabel() {
  return tabs.find(t => t.id === activeTab.value)?.label || ''
}
</script>

<style scoped>
@import '../styles/y2k-theme.css';

.workstation-sidebar {
  background: var(--bg-secondary);
  border-top: none;
  border-bottom: none;
  border-left: none;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

/* Tab 导航 */
.sidebar-tabs {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  border-bottom: 1px solid var(--border-subtle);
}

.sidebar-tab {
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.sidebar-tab:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.sidebar-tab.active {
  background: rgba(139, 92, 246, 0.15);
  border-color: rgba(139, 92, 246, 0.3);
  color: var(--accent-purple);
}

/* Tab 内容 */
.sidebar-content {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}
</style>