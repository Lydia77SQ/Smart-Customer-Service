const SHANGHAI = 'Asia/Shanghai'

function shanghaiYmd(date: Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: SHANGHAI,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function shanghaiHm(date: Date): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: SHANGHAI,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function isoAtShanghai(daysAgo: number, hour: number, minute: number, second = 0): string {
  const now = new Date()
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: SHANGHAI,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)
  const year = Number(parts.find((part) => part.type === 'year')?.value)
  const month = Number(parts.find((part) => part.type === 'month')?.value)
  const day = Number(parts.find((part) => part.type === 'day')?.value)
  const utcMs =
    Date.UTC(year, month - 1, day, hour - 8, minute, second) - daysAgo * 24 * 60 * 60 * 1000
  return new Date(utcMs).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

export function formatTicketListTime(iso: string): string {
  const date = new Date(iso)
  const today = shanghaiYmd(new Date())
  const target = shanghaiYmd(date)
  const yesterday = shanghaiYmd(new Date(Date.now() - 24 * 60 * 60 * 1000))
  const hm = shanghaiHm(date)
  if (target === today) return `今天 ${hm}`
  if (target === yesterday) return `昨天 ${hm}`
  return `${target} ${hm}`
}

export function formatKnowledgeUpdatedAt(iso: string): string {
  const date = new Date(iso)
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: SHANGHAI,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const hour = (parts.find((part) => part.type === 'hour')?.value ?? '00').padStart(2, '0')
  const minute = (parts.find((part) => part.type === 'minute')?.value ?? '00').padStart(2, '0')
  return `${shanghaiYmd(date)} ${hour}:${minute}`
}
