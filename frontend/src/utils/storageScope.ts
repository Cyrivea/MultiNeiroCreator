// B26：一切“业务级”缓存键按账号隔离。
// 事故现场：同一台浏览器换账号后，上个用户的“上次项目 / 画布草稿 / 创作工具”缓存
// 会在新账号的工作站上闪出来（实测证实）。账号是 USERNAME_KEY 里的值——
// 登录态变化时重新 loadForProject 就会拿到新键。
import { USERNAME_KEY } from '@/constants'

export function scopedKey(base: string): string {
  const username = localStorage.getItem(USERNAME_KEY)?.trim() || 'anonymous'
  return `${base}@u:${username}`
}

/** 读：优先隔离键；历史无隔离数据做一次性回退（读完下次写进隔离键，不再读老键） */
export function readScoped(base: string): string | null {
  const scoped = localStorage.getItem(scopedKey(base))
  if (scoped !== null) return scoped
  return localStorage.getItem(base)
}

export function writeScoped(base: string, value: string): void {
  localStorage.setItem(scopedKey(base), value)
}

export function removeScoped(base: string): void {
  localStorage.removeItem(scopedKey(base))
  localStorage.removeItem(base)
}
