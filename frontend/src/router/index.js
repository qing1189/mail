import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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

export default router
