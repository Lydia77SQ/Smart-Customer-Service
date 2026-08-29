<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppHeader from '@/components/AppHeader.vue'
import { useKnowledgeStore } from '@/stores/useKnowledgeStore'
import type { KnowledgeDocumentListItem, KnowledgeDocumentStatus } from '@/types/knowledge'
import { formatKnowledgeUpdatedAt } from '@/utils/datetime'

const NON_MARKDOWN_HINT = '仅支持 Markdown，该文件未入库。'

const knowledgeStore = useKnowledgeStore()
const fileInput = ref<HTMLInputElement | null>(null)

const listEmpty = computed(
  () => !knowledgeStore.listLoading && knowledgeStore.items.length === 0,
)

function isMarkdownFile(file: File): boolean {
  return file.name.toLowerCase().endsWith('.md')
}

function statusLabel(status: KnowledgeDocumentStatus): string {
  if (status === 'enabled') return '启用'
  if (status === 'disabled') return '已停用'
  return '未生效'
}

function statusTagClass(status: KnowledgeDocumentStatus): string {
  if (status === 'enabled') return 'tag tag-on'
  if (status === 'disabled') return 'tag tag-off'
  return 'tag tag-fail'
}

function canToggle(item: KnowledgeDocumentListItem): boolean {
  return item.status === 'enabled' || item.status === 'disabled'
}

function openFilePicker() {
  fileInput.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!isMarkdownFile(file)) {
    knowledgeStore.setClientError(NON_MARKDOWN_HINT)
    return
  }
  try {
    await knowledgeStore.upload(file)
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
}

async function onToggle(item: KnowledgeDocumentListItem, event: Event) {
  const input = event.target as HTMLInputElement
  if (!canToggle(item) || knowledgeStore.togglingId === item.id) {
    input.checked = item.status === 'enabled'
    return
  }
  try {
    await knowledgeStore.toggle(item.id, input.checked)
  } catch {
    input.checked = item.status === 'enabled'
  }
}

onMounted(async () => {
  try {
    await knowledgeStore.loadList()
  } catch {
    /* 错误文案由 store.errorMessage 展示 */
  }
})
</script>

<template>
  <div class="app">
    <AppHeader />
    <div class="main" style="flex: 1">
      <div class="toolbar">
        <button
          class="btn"
          type="button"
          :disabled="knowledgeStore.uploading"
          @click="openFilePicker"
        >
          上传 Markdown
        </button>
        <input
          ref="fileInput"
          type="file"
          accept=".md"
          hidden
          @change="onFileChange"
        />
        <span class="hint" style="margin: 0">仅支持 .md</span>
      </div>
      <div v-if="knowledgeStore.errorMessage" class="alert alert-error" style="margin: 16px" role="alert">
        {{ knowledgeStore.errorMessage }}
      </div>
      <div v-if="knowledgeStore.listLoading">
        <div class="skeleton"></div>
        <div class="skeleton"></div>
      </div>
      <div v-else-if="listEmpty" class="empty">还没有知识文档。请上传 Markdown。</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>文档名称</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>启用</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in knowledgeStore.items" :key="item.id">
              <td>{{ item.filename }}</td>
              <td>
                <span :class="statusTagClass(item.status)">{{ statusLabel(item.status) }}</span>
              </td>
              <td>{{ formatKnowledgeUpdatedAt(item.updated_at) }}</td>
              <td>
                <label class="switch">
                  <input
                    type="checkbox"
                    :checked="item.status === 'enabled'"
                    :disabled="!canToggle(item) || knowledgeStore.togglingId === item.id"
                    @change="onToggle(item, $event)"
                  />
                  <span class="slider"></span>
                </label>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
