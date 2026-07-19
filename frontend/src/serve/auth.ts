import request from '@/utils/request'

export interface AuthPayload {
  username: string
  password: string
}

export const login = (data: AuthPayload) =>
  request.post<any, { token: string; username: string }>('/auth/login', data)

export const sendCode = (username: string) =>
  request.post<any, { status: string; message: string }>('/auth/send-code', { username, password: '' })

export const register = (data: AuthPayload & { code: string }) =>
  request.post<any, { token: string; username: string }>(`/auth/register?code=${data.code}`, { username: data.username, password: data.password })
