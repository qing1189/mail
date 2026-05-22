<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '200px'" class="app-aside">
      <div class="logo" @click="isCollapse = !isCollapse">
        <el-icon :size="24"><DataBoard /></el-icon>
        <span v-show="!isCollapse" class="logo-text">Outlook Register</span>
      </div>
      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        router
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#1890ff"
      >
        <el-menu-item
          v-for="route in menuRoutes"
          :key="route.path"
          :index="route.path"
        >
          <el-icon><component :is="route.meta.icon" /></el-icon>
          <template #title>{{ route.meta.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部状态栏 -->
      <el-header class="app-header">
        <div class="status-bar">
          <el-tag :type="taskStore.isRunning ? 'success' : 'info'" effect="dark">
            {{ taskStore.isRunning ? '运行中' : '已停止' }}
          </el-tag>
          <span class="status-item">
            成功: <strong>{{ taskStore.status.succeeded }}</strong>
          </span>
          <span class="status-item">
            失败: <strong>{{ taskStore.status.failed }}</strong>
          </span>
          <span class="status-item">
            成功率: <strong>{{ taskStore.status.success_rate }}%</strong>
          </span>
          <span class="status-item">
            线程: <strong>{{ taskStore.status.active_threads }}</strong>
          </span>
        </div>
      </el-header>

      <!-- 页面内容 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()

const isCollapse = ref(false)

const currentRoute = computed(() => route.path)

const menuRoutes = computed(() => {
  return router.getRoutes().filter((r) => r.meta && r.meta.title)
})

onMounted(() => {
  taskStore.initWebSocket()
  taskStore.fetchStatus()
})

onUnmounted(() => {
  taskStore.disconnectWebSocket()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.app-container {
  height: 100%;
}

.app-aside {
  background-color: #001529;
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #fff;
  gap: 8px;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.el-menu {
  border-right: none !important;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 24px;
}

.status-item {
  color: #666;
  font-size: 14px;
}

.status-item strong {
  color: #333;
  margin-left: 4px;
}

.app-main {
  background: #f5f5f5;
  padding: 24px;
  overflow-y: auto;
}
</style>
