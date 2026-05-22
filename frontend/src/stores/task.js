import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskApi, wsClient } from '@/api'

export const useTaskStore = defineStore('task', () => {
  // 状态
  const status = ref({
    total_tasks: 0,
    submitted: 0,
    succeeded: 0,
    failed: 0,
    remaining: 0,
    active_threads: 0,
    success_rate: 0,
    oauth_succeeded: 0,
    oauth_failed: 0,
    is_running: false,
    is_stopping: false,
  })

  const logs = ref([])
  const successEmails = ref([])
  const connected = ref(false)

  // 计算属性
  const isRunning = computed(() => status.value.is_running)
  const isStopping = computed(() => status.value.is_stopping)
  const progress = computed(() => {
    if (status.value.total_tasks === 0) return 0
    return Math.round((status.value.submitted / status.value.total_tasks) * 100)
  })

  // 初始化 WebSocket
  function initWebSocket() {
    wsClient.on('status', (data) => {
      status.value = { ...status.value, ...data }
    })

    wsClient.on('log', (data) => {
      logs.value.push(data.message)
      if (logs.value.length > 500) {
        logs.value = logs.value.slice(-500)
      }
    })

    wsClient.on('success', (data) => {
      successEmails.value.unshift(data.email)
      if (successEmails.value.length > 200) {
        successEmails.value = successEmails.value.slice(0, 200)
      }
    })

    wsClient.connect()
    connected.value = true
  }

  // 断开 WebSocket
  function disconnectWebSocket() {
    wsClient.disconnect()
    connected.value = false
  }

  // 获取状态
  async function fetchStatus() {
    try {
      const res = await taskApi.getStatus()
      if (res.code === 0) {
        status.value = res.data
      }
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }

  // 获取日志
  async function fetchLogs() {
    try {
      const res = await taskApi.getLogs(200)
      if (res.code === 0) {
        logs.value = res.data
      }
    } catch (e) {
      console.error('Failed to fetch logs:', e)
    }
  }

  // 获取成功邮箱
  async function fetchSuccessEmails() {
    try {
      const res = await taskApi.getSuccess(200)
      if (res.code === 0) {
        successEmails.value = res.data
      }
    } catch (e) {
      console.error('Failed to fetch success emails:', e)
    }
  }

  // 启动任务
  async function startTask(config) {
    try {
      const res = await taskApi.start(config)
      return res
    } catch (e) {
      console.error('Failed to start task:', e)
      throw e
    }
  }

  // 停止任务
  async function stopTask() {
    try {
      const res = await taskApi.stop()
      return res
    } catch (e) {
      console.error('Failed to stop task:', e)
      throw e
    }
  }

  // 清空日志
  function clearLogs() {
    logs.value = []
  }

  return {
    status,
    logs,
    successEmails,
    connected,
    isRunning,
    isStopping,
    progress,
    initWebSocket,
    disconnectWebSocket,
    fetchStatus,
    fetchLogs,
    fetchSuccessEmails,
    startTask,
    stopTask,
    clearLogs,
  }
})
