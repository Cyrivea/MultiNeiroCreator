export const TOKEN_KEY = 'neyria_token'
export const USERNAME_KEY = 'neyria_username'
export const LEGACY_TOKEN_KEY = 'multineirocreator_token'
export const LEGACY_USERNAME_KEY = 'multineirocreator_username'
// API 前缀由环境变量提供（.env.development / .env.production），全库唯一出口（F6）
export const API_BASE = import.meta.env.VITE_API_BASE || '/api'
