import axios from 'axios'
import { TOKEN_KEY } from '@/constants'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

request.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || '请求失败'
    if (err.response?.status === 401) {
      localStorage.clear()
      window.location.href = '/login'
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export default request
