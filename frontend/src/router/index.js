import { createRouter, createWebHistory } from 'vue-router'
import { authApi } from '@/api'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘', icon: 'DataBoard' },
  },
  {
    path: '/task',
    name: 'TaskControl',
    component: () => import('@/views/TaskControl.vue'),
    meta: { title: '任务控制', icon: 'VideoPlay' },
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('@/views/Config.vue'),
    meta: { title: '配置管理', icon: 'Setting' },
  },
  {
    path: '/proxy',
    name: 'Proxy',
    component: () => import('@/views/Proxy.vue'),
    meta: { title: '代理管理', icon: 'Connection' },
  },
  {
    path: '/results',
    name: 'Results',
    component: () => import('@/views/Results.vue'),
    meta: { title: '结果查看', icon: 'List' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 公开页面直接放行
  if (to.meta.public) {
    next()
    return
  }

  // 检查认证状态
  try {
    const res = await authApi.check()
    if (res.authenticated) {
      next()
    } else {
      next('/login')
    }
  } catch (e) {
    // API 错误（可能是未启动后端）
    next('/login')
  }
})

export default router
