export interface UserPublic {
  id: number
  account: string
  display_name: string
}

export interface AuthLoginRequest {
  account: string
  password: string
}

export interface AuthRegisterRequest {
  account: string
  password: string
}

export interface AuthSessionResponse {
  token: string
  user: UserPublic
}

export interface AuthRegisterResponse {
  id: number
  account: string
  display_name: string
}
