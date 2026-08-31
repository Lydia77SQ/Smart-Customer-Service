<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import { useTicketStore } from '@/stores/useTicketStore'
import type { MessageSenderType, TicketStatus } from '@/types/ticket'
import { formatTicketListTime } from '@/utils/datetime'

const ticketStore = useTicketStore()
const draft = ref('')
const threadEl = ref<HTMLElement | null>(null)

const statusLabel: Record<TicketStatus, string> = {
  ai_assisting: 'AI 接待中',
  pending: '待处理',
  in_progress: '处理中',
  closed: '已完结',
}

const statusBarText: Record<TicketStatus, string> = {
  ai_assisting: 'AI 接待中 · 可继续提问或转人工',
  pending: '待处理 · 已提交，等待对接人',
  in_progress: '处理中 · 已转人工，等待对接人回复',
  closed: '已完结 · 不能再发送消息',
}

const whoLabel: Record<MessageSenderType, string> = {
  employee: '我',
  system: '系统',
  agent: '坐席',
}

const selected = computed(() => ticketStore.detail)
const isClosed = computed(() => selected.value?.status === 'closed')
const canTransfer = computed(() => selected.value?.status === 'ai_assisting')
const canSend = computed(() => {
  if (ticketStore.sending) return false
  if (!draft.value.trim()) return false
  if (ticketStore.composingNew) return true
  if (!selected.value) return false
  return selected.value.status !== 'closed'
})
const composerPlaceholder = computed(() =>
  isClosed.value ? '已完结，不能再发送' : '描述你的 IT 或行政问题',
)
const showMain = computed(() => ticketStore.composingNew || selected.value !== null)
const listEmpty = computed(() => !ticketStore.listLoading && ticketStore.items.length === 0)

function dotClass(status: TicketStatus): string {
  if (status === 'ai_assisting') return 'dot dot-ai'
  if (status === 'pending') return 'dot dot-wait'
  if (status === 'in_progress') return 'dot dot-doing'
  return 'dot dot-done'
}

function bubbleClass(sender: MessageSenderType): string {
  if (sender === 'employee') return 'bubble bubble-me'
  if (sender === 'agent') return 'bubble bubble-agent'
  return 'bubble bubble-sys'
}

async function openTicket(ticketId: number) {
  draft.value = ''
  try {
    await ticketStore.openTicket(ticketId)
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

function onNewConsult() {
  draft.value = ''
  ticketStore.startNewConsult()
}

async function onSend() {
  if (!canSend.value) return
  const content = draft.value
  draft.value = ''
  try {
    await ticketStore.send(content)
  } catch {
    draft.value = content
  }
}

async function onTransfer() {
  if (!canTransfer.value) return
  try {
    await ticketStore.transfer()
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
  ticketStore.$reset()
  try {
    await ticketStore.loadMine()
    const first = ticketStore.items[0]
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
        <h2>我的咨询</h2>
        <div v-if="ticketStore.listLoading" class="show-loading">
          <div class="skeleton"></div>
          <div class="skeleton"></div>
        </div>
        <div v-else-if="listEmpty" class="empty">还没有咨询。点下方新咨询开始提问。</div>
        <div v-else class="list">
          <button
            v-for="item in ticketStore.items"
            :key="item.id"
            class="item"
            type="button"
            :class="{ 'is-active': selected?.id === item.id && !ticketStore.composingNew }"
            @click="openTicket(item.id)"
          >
            <span class="title">
              <span :class="dotClass(item.status)"></span>{{ item.title }}
            </span>
            <span class="meta">{{ statusLabel[item.status] }} · {{ formatTicketListTime(item.updated_at) }}</span>
          </button>
        </div>
        <div style="padding: 12px 16px">
          <button class="btn" type="button" style="width: 100%" @click="onNewConsult">新咨询</button>
        </div>
      </aside>
      <section v-if="showMain" class="main">
        <div
          v-if="selected && !ticketStore.composingNew"
          class="status-bar"
          :class="{ 'is-closed': isClosed }"
        >
          {{ statusBarText[selected.status] }}
        </div>
        <div v-if="ticketStore.errorMessage" class="alert alert-error" role="alert">
          {{ ticketStore.errorMessage }}
        </div>
        <div ref="threadEl" class="thread">
          <div
            v-for="message in selected?.messages ?? []"
            :key="message.id"
            :class="bubbleClass(message.sender_type)"
          >
            <div class="who">{{ whoLabel[message.sender_type] }}</div>
            {{ message.content }}
          </div>
        </div>
        <div class="composer">
          <textarea
            v-model="draft"
            class="input"
            :placeholder="composerPlaceholder"
            :disabled="isClosed"
          ></textarea>
          <button
            class="btn btn-secondary"
            type="button"
            :class="{ 'is-disabled': isClosed || !canTransfer }"
            :disabled="isClosed || !canTransfer || ticketStore.transferring"
            @click="onTransfer"
          >
            转人工
          </button>
          <button
            class="btn"
            type="button"
            :class="{ 'is-disabled': isClosed }"
            :disabled="isClosed || !canSend"
            @click="onSend"
          >
            发送
          </button>
        </div>
      </section>
      <section v-else class="main">
        <div class="empty">选择一条咨询，或点「新咨询」开始提问。</div>
      </section>
    </div>
  </div>
</template>
