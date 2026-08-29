export interface ApiEnvelope<T> {
  code: number | string
  message: string
  data: T | null
}

export interface ApiErrorBody {
  code: string | number
  message: string
  data: null
}
