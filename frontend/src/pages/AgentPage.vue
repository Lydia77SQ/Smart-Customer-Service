<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import { useAgentStore } from '@/stores/useAgentStore'
import type { AgentQueueStatus, MessageSenderType, TicketCategory, TicketStatus } from '@/types/ticket'

const CATEGORIES: TicketCategory[] = ['IT-网络', 'IT-账号', '行政-工牌', '行政-场地']
const SUGGEST_FAIL_TEXT = '暂时无法生成建议。请手写回复，不要向员工发送自动消息。'

const agentStore = useAgentStore()
const draft = ref('')
const threadEl = ref<HTMLElement | null>(null)

const selected = computed(() => agentStore.detail)
const isPending = computed(() => selected.value?.status === 'pending')
const isInProgress = computed(() => selected.value?.status === 'in_progress')
const isClosed = computed(() => selected.value?.status === 'closed')
const listEmpty = computed(() => !agentStore.queueLoading && agentStore.queueItems.length === 0)
const emptyListText = computed(() =>
  agentStore.queueStatus === 'pending' ? '当前没有待处理工单。' : '当前没有处理中工单。',
)

const statusBarText: Record<TicketStatus, string> = {
  ai_assisting: '待处理 · 员工已转人工，上下文已保留',
  pending: '待处理 · 员工已转人工，上下文已保留',
  in_progress: '处理中 · 系统不再自动对外发言',
  closed: '已完结 · 不能再发送',
}

const composerPlaceholder = computed(() => {
  if (isClosed.value) return '已完结，不能再发送'
  if (isPending.value || !selected.value) return '请先接入后再回复'
  return '回复员工'
})

const canSend = computed(() => {
  if (!isInProgress.value) return false
  if (agentStore.sending) return false
  return Boolean(draft.value.trim())
})

const acceptLabel = computed(() => (isInProgress.value ? '已接入' : '接入处理'))
const canAccept = computed(() => isPending.value && !agentStore.accepting)
const canClose = computed(() => isInProgress.value && !agentStore.closing)
const canSuggest = computed(() => isInProgress.value && !agentStore.suggesting)
const canFill = computed(
  () => isInProgress.value && Boolean(agentStore.suggestion) && !agentStore.suggestionFailed,
)
const canClassify = computed(() => Boolean(selected.value) && !isClosed.value && !agentStore.classifying)

function queueDotClass(status: TicketStatus): string {
  if (status === 'in_progress') return 'dot dot-doing'
  return 'dot dot-wait'
}

function bubbleClass(sender: MessageSenderType): string {
  if (sender === 'agent') return 'bubble bubble-agent'
  if (sender === 'system') return 'bubble bubble-sys'
  return 'bubble bubble-employee'
}

function whoLabel(sender: MessageSenderType): string {
  if (sender === 'system') return '系统'
  if (sender === 'agent') return '坐席'
  return selected.value?.requester.display_name ?? '员工'
}

async function onSwitchQueue(status: AgentQueueStatus) {
  if (agentStore.queueStatus === status) return
  draft.value = ''
  try {
    await agentStore.switchQueue(status)
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

async function openTicket(ticketId: number) {
  draft.value = ''
  try {
    await agentStore.openTicket(ticketId)
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

async function onAccept() {
  if (!canAccept.value) return
  try {
    await agentStore.accept()
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

async function onSend() {
  if (!canSend.value) return
  const content = draft.value
  draft.value = ''
  try {
    await agentStore.send(content)
  } catch {
    draft.value = content
  }
}

async function onSuggest() {
  if (!canSuggest.value) return
  try {
    await agentStore.fetchSuggestion()
  } catch {
    /* 右栏失败说明由 suggestionFailed / errorMessage 展示 */
  }
}

function onFill() {
  if (!canFill.value || !agentStore.suggestion) return
  draft.value = agentStore.suggestion.content
}

async function onClassify(event: Event) {
  const target = event.target as HTMLSelectElement
  const value = target.value as TicketCategory
  if (!CATEGORIES.includes(value)) return
  try {
    await agentStore.classify(value)
  } catch {
    target.value = selected.value?.category ?? ''
  }
}

async function onClose() {
  if (!canClose.value) return
  draft.value = ''
  try {
    await agentStore.close()
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

watch(
  () => selected.value?.messages.length,
  async () => {
    await nextTick()
    if (threadEl.value) {
      threadEl.value.scrollTop = threadEl.value.scrollHeight
    }
  },
)

onMounted(async () => {
  try {
    await agentStore.loadQueue()
    const first = agentStore.queueItems[0]
    if (first) {
      await openTicket(first.id)
    }
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
})
</script>

<template>
  <div class="app">
    <AppHeader />
    <div class="shell">
      <aside class="sidebar">
        <h2>工单</h2>
        <div class="seg">
          <button
            type="button"
            :class="{ 'is-active': agentStore.queueStatus === 'pending' }"
            @click="onSwitchQueue('pending')"
          >
            待处理
          </button>
          <button
            type="button"
            :class="{ 'is-active': agentStore.queueStatus === 'in_progress' }"
            @click="onSwitchQueue('in_progress')"
          >
            处理中
          </button>
        </div>
        <div v-if="agentStore.queueLoading" class="show-loading">
          <div class="skeleton"></div>
          <div class="skeleton"></div>
        </div>
        <div v-else-if="listEmpty" class="empty">{{ emptyListText }}</div>
        <div v-else class="list">
          <button
            v-for="item in agentStore.queueItems"
            :key="item.id"
            class="item"
            type="button"
            :class="{ 'is-active': selected?.id === item.id }"
            @click="openTicket(item.id)"
          >
            <span class="title">
              <span :class="queueDotClass(item.status)"></span>
              {{ item.requester.display_name }} · {{ item.title }}
            </span>
            <span class="meta">等待 {{ item.waiting_minutes }} 分钟</span>
            <span
              v-if="selected?.id === item.id && selected.category"
              class="tag tag-cat"
            >{{ selected.category }}</span>
          </button>
        </div>
      </aside>
      <template v-if="selected">
        <section class="main">
          <div class="status-bar" :class="{ 'is-closed': isClosed }">
            {{ statusBarText[selected.status] }}
          </div>
          <div v-if="agentStore.errorMessage" class="alert alert-error" role="alert">
            {{ agentStore.errorMessage }}
          </div>
          <div ref="threadEl" class="thread">
            <div
              v-for="message in selected.messages"
              :key="message.id"
              :class="bubbleClass(message.sender_type)"
            >
              <div class="who">{{ whoLabel(message.sender_type) }}</div>
              {{ message.content }}
            </div>
          </div>
          <div class="composer">
            <textarea
              v-model="draft"
              class="input"
              :placeholder="composerPlaceholder"
              :disabled="!isInProgress"
            ></textarea>
            <button class="btn" type="button" :disabled="!canSend" @click="onSend">发送</button>
          </div>
        </section>
        <aside class="panel">
          <h2>当前工单</h2>
          <div class="block">
            <button
              class="btn"
              type="button"
              style="width: 100%"
              :disabled="!canAccept"
              @click="onAccept"
            >
              {{ acceptLabel }}
            </button>
            <label>
              分类
              <select
                class="select"
                :value="selected.category ?? ''"
                :disabled="!canClassify"
                @change="onClassify"
              >
                <option value="" disabled hidden></option>
                <option v-for="category in CATEGORIES" :key="category" :value="category">
                  {{ category }}
                </option>
              </select>
            </label>
            <span v-if="selected.category" class="tag tag-cat">{{ selected.category }}</span>
            <label>智能回答</label>
            <button
              class="btn btn-secondary"
              type="button"
              style="width: 100%; margin-bottom: 8px"
              :disabled="!canSuggest"
              @click="onSuggest"
            >
              获取建议
            </button>
            <div
              v-if="agentStore.suggestion && !agentStore.suggestionFailed"
              class="suggest"
            >
              {{ agentStore.suggestion.content }}
            </div>
            <p v-if="agentStore.suggestionFailed" class="hint">
              {{ agentStore.suggestion?.content ?? SUGGEST_FAIL_TEXT }}
            </p>
            <button
              class="btn btn-secondary"
              type="button"
              style="width: 100%; margin-top: 8px"
              :disabled="!canFill"
              @click="onFill"
            >
              填入输入框
            </button>
            <button
              class="btn btn-danger"
              type="button"
              style="width: 100%; margin-top: 12px"
              :disabled="!canClose"
              @click="onClose"
            >
              结束工单
            </button>
          </div>
        </aside>
      </template>
      <section v-else class="main">
        <div v-if="agentStore.errorMessage" class="alert alert-error" role="alert">
          {{ agentStore.errorMessage }}
        </div>
        <div class="empty">{{ emptyListText }}</div>
      </section>
    </div>
  </div>
</template>
