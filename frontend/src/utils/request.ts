import axios from 'axios'
import { TOKEN_KEY } from '@/constants'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 这些接口的 401/4xx 是"本次操作失败"（如密码输错），不是登录态失效，
// 由调用方页面内联展示错误，不触发全局登出跳转
const AUTH_URLS = ['/auth/login', '/auth/register', '/auth/send-code']

request.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

request.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || '请求失败'
    const isAuthUrl = AUTH_URLS.some(u => err.config?.url?.startsWith(u))
    if (err.response?.status === 401 && !isAuthUrl) {
      // 真正的 token 失效：只清用户态，不用 localStorage.clear() 连坐其他数据
      useUserStore().logout()
      ElMessage.error('登录已过期，请重新登录')
      window.location.href = '/login'
    } else if (!isAuthUrl) {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export default request
