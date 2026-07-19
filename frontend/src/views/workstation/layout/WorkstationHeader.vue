<template>
  <div class="workstation-header y2k-border">
    <div class="header-left">
      <div class="logo">
        <span class="logo-text">MultiNeiroCreator</span>
        <span class="logo-dot">.</span>
      </div>
      <div class="project-name">Untitled_Project</div>
      <div class="save-status">
        <span class="status-dot"></span>
        <span>Auto-saved</span>
      </div>
    </div>
    <div class="header-right">
      <div class="api-monitor">
        <div class="stat">
          <span class="stat-label">Tokens</span>
          <span class="stat-value">0</span>
        </div>
        <div class="stat">
          <span class="stat-label">GPU</span>
          <span class="stat-value">0%</span>
        </div>
      </div>
      <button class="header-btn">⚙️</button>
      <div class="user-avatar">👤</div>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
@import '../styles/y2k-theme.css';

.workstation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--bg-secondary);
  border-left: none;
  border-right: none;
  border-top: none;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo {
  font-weight: 700;
  letter-spacing: -0.02em;
}
.logo-dot { color: var(--accent-purple); }

.project-name {
  font-size: 13px;
  color: var(--text-secondary);
  padding-left: 16px;
  border-left: 1px solid var(--border-subtle);
}

.save-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-neon-green);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.api-monitor {
  display: flex;
  gap: 16px;
  font-size: 11px;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.stat-label { color: var(--text-muted); }
.stat-value { color: var(--text-primary); font-weight: 600; }

.header-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.2s;
}
.header-btn:hover { opacity: 1; }

.user-avatar {
  font-size: 20px;
}
</style>