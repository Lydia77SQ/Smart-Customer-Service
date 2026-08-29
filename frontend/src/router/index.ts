import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '@/pages/LoginPage.vue'
import EmployeePage from '@/pages/EmployeePage.vue'
import AgentPage from '@/pages/AgentPage.vue'
import KnowledgePage from '@/pages/KnowledgePage.vue'
import { useAuthStore } from '@/stores/useAuthStore'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
    },
    {
      path: '/employee',
      name: 'employee',
      component: EmployeePage,
      meta: { requiresAuth: true },
    },
    {
      path: '/agent',
      name: 'agent',
      component: AgentPage,
      meta: { requiresAuth: true },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: KnowledgePage,
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  if (!requiresAuth && to.path !== '/login') {
    return true
  }

  const authStore = useAuthStore()
  const token = localStorage.getItem('token')
  if (!token) {
    authStore.clearSession()
    if (requiresAuth) {
      return { path: '/login', query: { state: 'need-login' }, replace: true }
    }
    return true
  }

  const ok = await authStore.restoreSession()
  if (requiresAuth && !ok) {
    return { path: '/login', query: { state: 'need-login' }, replace: true }
  }
  if (to.path === '/login' && ok) {
    return { path: '/employee', replace: true }
  }
  return true
})

export default router
