import { useAgentStore } from '@/stores/useAgentStore'
import { useKnowledgeStore } from '@/stores/useKnowledgeStore'
import { useTicketStore } from '@/stores/useTicketStore'

export function resetWorkspaceStores() {
  useTicketStore().$reset()
  useAgentStore().$reset()
  useKnowledgeStore().$reset()
}
