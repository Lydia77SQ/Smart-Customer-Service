<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'
import { resetWorkspaceStores } from '@/stores/resetWorkspace'
import { getApiErrorCode, getApiErrorMessage } from '@/utils/error'

type TabId = 'login' | 'register'
type AlertKind = 'error' | 'need-login' | 'conflict' | 'ok' | 'validation' | null

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const tab = ref<TabId>('login')
const alertKind = ref<AlertKind>(null)
const envelopeMessage = ref('')
const loginAccount = ref('wang.li')
const loginPassword = ref('pass-word-6')
const registerAccount = ref('')
const registerPassword = ref('')
const loginLoading = ref(false)
const registerLoading = ref(false)

function applyQueryState(state: unknown) {
  const value = typeof state === 'string' ? state : ''
  if (value === 'register' || value === 'conflict' || value === 'ok') {
    tab.value = 'register'
  } else {
    tab.value = 'login'
  }
  if (value === 'error') alertKind.value = 'error'
  else if (value === 'need-login') alertKind.value = 'need-login'
  else if (value === 'conflict') alertKind.value = 'conflict'
  else if (value === 'ok') alertKind.value = 'ok'
  else alertKind.value = null
  loginLoading.value = value === 'loading'
}

watch(
  () => route.query.state,
  (state) => applyQueryState(state),
  { immediate: true },
)

function showLogin() {
  tab.value = 'login'
  alertKind.value = null
  envelopeMessage.value = ''
}

function showRegister() {
  tab.value = 'register'
  alertKind.value = null
  envelopeMessage.value = ''
}

const loginDisabled = computed(
  () => loginLoading.value || !loginAccount.value.trim() || !loginPassword.value,
)

const registerDisabled = computed(
  () => registerLoading.value || !registerAccount.value.trim() || !registerPassword.value,
)

const errorText = computed(() => {
  if (alertKind.value === 'error') return '账号或密码不正确'
  if (alertKind.value === 'need-login') return '请先登录后再进入工作台'
  if (alertKind.value === 'conflict') {
    return envelopeMessage.value || '该账号名已被占用'
  }
  if (alertKind.value === 'validation') {
    return envelopeMessage.value || '参数验证失败'
  }
  return ''
})

const okText = computed(() =>
  alertKind.value === 'ok' ? '账号已创建，请使用该凭证登录' : '',
)

async function onLoginSubmit() {
  if (loginDisabled.value) return
  alertKind.value = null
  envelopeMessage.value = ''
  loginLoading.value = true
  try {
    const session = await login({
      account: loginAccount.value.trim(),
      password: loginPassword.value,
    })
    authStore.setSession(session.token, session.user)
    resetWorkspaceStores()
    await router.push('/employee')
  } catch (error) {
    const code = getApiErrorCode(error)
    if (code === 'UNAUTHORIZED') {
      alertKind.value = 'error'
    } else {
      alertKind.value = 'validation'
      envelopeMessage.value = getApiErrorMessage(error) || '无法连接服务'
    }
  } finally {
    loginLoading.value = false
  }
}

async function onRegisterSubmit() {
  if (registerDisabled.value) return
  alertKind.value = null
  envelopeMessage.value = ''
  registerLoading.value = true
  try {
    await register({
      account: registerAccount.value.trim(),
      password: registerPassword.value,
    })
    alertKind.value = 'ok'
  } catch (error) {
    const code = getApiErrorCode(error)
    envelopeMessage.value = getApiErrorMessage(error)
    if (code === 'CONFLICT') {
      alertKind.value = 'conflict'
    } else if (code === 'VALIDATION_ERROR') {
      alertKind.value = 'validation'
    } else {
      alertKind.value = 'conflict'
    }
  } finally {
    registerLoading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <section class="card">
      <h1>智能客服系统</h1>
      <p class="hint">内部 IT / 行政支持</p>
      <div class="tabs" role="tablist">
        <button
          id="tab-login"
          type="button"
          role="tab"
          :class="{ 'is-active': tab === 'login' }"
          :aria-selected="tab === 'login'"
          @click="showLogin"
        >
          登录
        </button>
        <button
          id="tab-register"
          type="button"
          role="tab"
          :class="{ 'is-active': tab === 'register' }"
          :aria-selected="tab === 'register'"
          @click="showRegister"
        >
          注册
        </button>
      </div>
      <div v-if="errorText" class="alert alert-error" role="alert">{{ errorText }}</div>
      <div v-if="okText" class="alert alert-ok" role="alert">{{ okText }}</div>
      <form id="form-login" :hidden="tab !== 'login'" @submit.prevent="onLoginSubmit">
        <label class="field">
          <span>账号</span>
          <input
            v-model="loginAccount"
            class="input"
            name="account"
            autocomplete="username"
          />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="loginPassword"
            class="input"
            name="password"
            type="password"
            autocomplete="current-password"
          />
        </label>
        <button
          id="btn-login"
          class="btn"
          type="submit"
          style="width: 100%"
          :disabled="loginDisabled"
        >
          {{ loginLoading ? '登录中' : '登录' }}
        </button>
      </form>
      <form id="form-register" :hidden="tab !== 'register'" @submit.prevent="onRegisterSubmit">
        <label class="field">
          <span>账号</span>
          <input
            v-model="registerAccount"
            class="input"
            name="new-account"
            placeholder="请输入账号"
          />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="registerPassword"
            class="input"
            name="new-password"
            type="password"
            placeholder="请输入密码"
          />
        </label>
        <button class="btn" type="submit" style="width: 100%" :disabled="registerDisabled">
          创建账号
        </button>
      </form>
    </section>
  </main>
</template>
