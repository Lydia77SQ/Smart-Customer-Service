import type { ApiErrorBody } from '@/types/api'

interface EnvelopeLike {
  response?: {
    data?: Partial<ApiErrorBody>
  }
}

export function getApiErrorCode(error: unknown): string | number | undefined {
  if (typeof error === 'object' && error !== null) {
    return (error as EnvelopeLike).response?.data?.code
  }
  return undefined
}

function isNetworkFailure(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false
  const item = error as { code?: string; message?: string; response?: unknown }
  if (item.response !== undefined) return false
  return item.code === 'ERR_NETWORK' || item.message === 'Network Error'
}

export function getApiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const message = (error as EnvelopeLike).response?.data?.message
    if (typeof message === 'string' && message.length > 0) return message
  }
  if (isNetworkFailure(error)) return '无法连接服务，请确认后端已启动'
  if (error instanceof Error && error.message) return error.message
  return '请求失败'
}
