import axios from 'axios'
import router from '@/router'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 401 未授权，跳转到登录页
    if (error.response?.status === 401) {
      router.push('/login')
    }
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// 认证 API
export const authApi = {
  login: (password) => api.post('/auth/login', { password }),
  logout: () => api.post('/auth/logout'),
  check: () => api.get('/auth/check'),
}

// 配置 API
export const configApi = {
  get: () => api.get('/config'),
  update: (data) => api.put('/config', data),
  reset: () => api.post('/config/reset'),
}

// 任务 API
export const taskApi = {
  start: (config) => api.post('/task/start', config),
  stop: () => api.post('/task/stop'),
  getStatus: () => api.get('/task/status'),
  getLogs: (limit = 100) => api.get('/task/logs', { params: { limit } }),
  getSuccess: (limit = 100) => api.get('/task/success', { params: { limit } }),
}

// 代理 API
export const proxyApi = {
  get: () => api.get('/proxies'),
  save: (proxies) => api.post('/proxies', { proxies }),
  add: (proxy) => api.post('/proxies/add', proxy),
  delete: (host, port) => api.delete(`/proxies/${host}/${port}`),
  clear: () => api.delete('/proxies'),
}

// 结果 API
export const resultApi = {
  get: (params) => api.get('/results', { params }),
  export: (params) => api.get('/results/export', { params, responseType: 'blob' }),
  getStats: () => api.get('/results/stats'),
  clear: (type) => api.delete('/results', { params: { type } }),
}

// WebSocket 连接
export class WebSocketClient {
  constructor() {
    this.ws = null
    this.callbacks = {
      status: [],
      log: [],
      success: [],
    }
    this.reconnectTimer = null
    this.heartbeatTimer = null
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/status`

    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.startHeartbeat()
    }

    this.ws.onmessage = (event) => {
      try {
        if (event.data === 'heartbeat' || event.data === 'pong') return
        const data = JSON.parse(event.data)
        const { type, data: payload } = data
        if (this.callbacks[type]) {
          this.callbacks[type].forEach((cb) => cb(payload))
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.stopHeartbeat()
      this.reconnect()
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  reconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, 3000)
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 25000)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  on(type, callback) {
    if (this.callbacks[type]) {
      this.callbacks[type].push(callback)
    }
  }

  off(type, callback) {
    if (this.callbacks[type]) {
      this.callbacks[type] = this.callbacks[type].filter((cb) => cb !== callback)
    }
  }

  disconnect() {
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

export const wsClient = new WebSocketClient()
