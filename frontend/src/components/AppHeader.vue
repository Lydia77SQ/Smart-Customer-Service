<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { logout } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

const router = useRouter()
const authStore = useAuthStore()
const displayName = computed(() => authStore.user?.display_name ?? '')

async function onLogout() {
  try {
    await logout()
  } catch {
    /* 仍退出本地会话 */
  }
  authStore.clearSession()
  await router.push('/login')
}
</script>

<template>
  <header class="topbar">
    <div class="brand">智能客服系统</div>
    <nav class="nav">
      <RouterLink to="/employee" active-class="is-active" exact-active-class="is-active">
        员工咨询
      </RouterLink>
      <RouterLink to="/agent" active-class="is-active" exact-active-class="is-active">
        坐席接待
      </RouterLink>
      <RouterLink to="/knowledge" active-class="is-active" exact-active-class="is-active">
        知识维护
      </RouterLink>
    </nav>
    <div class="topbar-right">
      {{ displayName }}
      <button class="btn btn-secondary" type="button" style="height: 32px" @click="onLogout">
        退出
      </button>
    </div>
  </header>
</template>
