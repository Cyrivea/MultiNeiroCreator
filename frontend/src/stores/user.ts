import { defineStore } from 'pinia'
import { LEGACY_TOKEN_KEY, LEGACY_USERNAME_KEY, TOKEN_KEY, USERNAME_KEY } from '@/constants'

function readStorageValue(key: string, legacyKey: string) {
  const current = localStorage.getItem(key)
  if (current) return current
  const legacy = localStorage.getItem(legacyKey)
  if (legacy) localStorage.setItem(key, legacy)
  return legacy || ''
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: readStorageValue(TOKEN_KEY, LEGACY_TOKEN_KEY),
    username: readStorageValue(USERNAME_KEY, LEGACY_USERNAME_KEY),
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    setUser(token: string, username: string) {
      this.token = token
      this.username = username
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USERNAME_KEY, username)
      localStorage.removeItem(LEGACY_TOKEN_KEY)
      localStorage.removeItem(LEGACY_USERNAME_KEY)
    },
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USERNAME_KEY)
      localStorage.removeItem(LEGACY_TOKEN_KEY)
      localStorage.removeItem(LEGACY_USERNAME_KEY)
    },
  },
})
