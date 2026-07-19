<template>
  <div class="login-page">

    <!-- 全局 toast -->
    <transition name="toast">
      <div v-if="toast.show" class="toast">{{ toast.msg }}</div>
    </transition>

    <div class="login-card">
      <!-- Tab 切换 -->
      <div class="tabs">
        <button :class="['tab', mode === 'login' && 'active']" @click="mode = 'login'">Sign In</button>
        <button :class="['tab', mode === 'register' && 'active']" @click="mode = 'register'">Register</button>
      </div>

      <!-- 登录表单 -->
      <transition name="form" mode="out-in">
        <div v-if="mode === 'login'" key="login" class="form">
          <div class="logo-area">
            <span class="logo-text">MultiNeiroCreator<span class="dot">.</span></span>
            <p class="logo-sub">AI Creation Workstation</p>
          </div>

          <div class="field">
            <label>Email or Phone</label>
            <input v-model="loginForm.account" type="text" placeholder="Enter email or phone number" @keyup.enter="submitLogin" />
          </div>
          <div class="field">
            <label>Password</label>
            <div class="input-wrap">
              <input v-model="loginForm.password" :type="showPwd ? 'text' : 'password'" placeholder="Enter password" @keyup.enter="submitLogin" />
              <span class="eye" @click="showPwd = !showPwd">{{ showPwd ? '🙈' : '👁' }}</span>
            </div>
          </div>

          <div class="remember-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="loginForm.remember" />
              <span>Remember me for 30 days</span>
            </label>
            <a href="#" class="forgot">Forgot password?</a>
          </div>

          <p v-if="loginError" class="error-msg">{{ loginError }}</p>

          <button class="btn-primary" :class="{ loading: loginLoading }" @click="submitLogin" v-ripple>
            {{ loginLoading ? 'Signing in...' : 'Sign In' }}
          </button>

          <p class="switch-tip">Don't have an account? <span @click="mode='register'">Register now</span></p>
        </div>

        <!-- 注册表单 -->
        <div v-else key="register" class="form">
          <div class="logo-area">
            <span class="logo-text">MultiNeiroCreator<span class="dot">.</span></span>
            <p class="logo-sub">Create your account</p>
          </div>

          <div class="field">
            <label>Email or Phone</label>
            <div class="input-wrap">
              <input v-model="regForm.account" type="text" placeholder="Enter email or phone number" />
              <button class="send-code" :disabled="codeCooldown > 0" @click="sendCode">
                {{ codeCooldown > 0 ? `${codeCooldown}s` : 'Send Code' }}
              </button>
            </div>
          </div>

          <div class="field">
            <label>Verification Code</label>
            <input v-model="regForm.code" type="text" placeholder="Enter verification code" maxlength="6" />
          </div>

          <div class="field">
            <label>Password</label>
            <div class="input-wrap">
              <input v-model="regForm.password" :type="showRegPwd ? 'text' : 'password'" placeholder="Create a password" />
              <span class="eye" @click="showRegPwd = !showRegPwd">{{ showRegPwd ? '🙈' : '👁' }}</span>
            </div>
          </div>

          <div class="field">
            <label>Confirm Password</label>
            <div class="input-wrap">
              <input
                v-model="regForm.confirmPassword"
                :type="showRegPwd2 ? 'text' : 'password'"
                placeholder="Confirm your password"
                :class="{ 'input-error': pwdMismatch }"
              />
              <span class="eye" @click="showRegPwd2 = !showRegPwd2">{{ showRegPwd2 ? '🙈' : '👁' }}</span>
            </div>
            <p v-if="pwdMismatch" class="field-error">Passwords do not match</p>
          </div>

          <p v-if="regError" class="error-msg">{{ regError }}</p>

          <button class="btn-primary" :class="{ loading: regLoading }" @click="submitRegister" v-ripple>
            {{ regLoading ? 'Creating account...' : 'Create Account' }}
          </button>

          <p class="switch-tip">Already have an account? <span @click="mode='login'">Sign in</span></p>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { login, register, sendCode as sendCodeApi } from '@/serve/auth'

const router = useRouter()
const userStore = useUserStore()

const mode = ref<'login' | 'register'>('login')
const showPwd = ref(false)
const showRegPwd = ref(false)
const showRegPwd2 = ref(false)
const loginLoading = ref(false)
const regLoading = ref(false)
const loginError = ref('')
const regError = ref('')
const codeCooldown = ref(0)

const toast = reactive({ show: false, msg: '' })

const loginForm = reactive({ account: '', password: '', remember: false })
const regForm = reactive({ account: '', code: '', password: '', confirmPassword: '' })

const pwdMismatch = computed(() =>
  regForm.confirmPassword.length > 0 && regForm.password !== regForm.confirmPassword
)

function showToast(msg: string) {
  toast.msg = msg
  toast.show = true
  setTimeout(() => { toast.show = false }, 2500)
}

function startCooldown() {
  codeCooldown.value = 60
  const t = setInterval(() => {
    codeCooldown.value--
    if (codeCooldown.value <= 0) clearInterval(t)
  }, 1000)
}

async function sendCode() {
  if (!regForm.account) { regError.value = 'Please enter email or phone first'; return }
  if (!regForm.account.includes('@')) { regError.value = 'Please enter a valid email address'; return }
  try {
    await sendCodeApi(regForm.account)
    startCooldown()
    regError.value = ''
  } catch (e: any) {
    regError.value = e.response?.data?.detail || 'Failed to send code'
  }
}

async function submitLogin() {
  if (!loginForm.account || !loginForm.password) {
    loginError.value = 'Please fill in all fields'
    return
  }
  loginLoading.value = true
  loginError.value = ''
  try {
    const res = await login({ username: loginForm.account, password: loginForm.password })
    userStore.setUser(res.token, res.username)
    if (loginForm.remember) {
      localStorage.setItem('remember', '1')
    }
    router.push('/workstation')
  } catch (e: any) {
    loginError.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loginLoading.value = false
  }
}

async function submitRegister() {
  if (!regForm.account || !regForm.code || !regForm.password || !regForm.confirmPassword) {
    regError.value = 'Please fill in all fields'
    return
  }
  if (pwdMismatch.value) return
  regLoading.value = true
  regError.value = ''
  try {
    const res = await register({ username: regForm.account, password: regForm.password, code: regForm.code })
    userStore.setUser(res.token, res.username)
    showToast('🎉 Registration successful!')
    setTimeout(() => router.push('/workstation'), 2000)
  } catch (e: any) {
    regError.value = e.response?.data?.detail || 'Registration failed'
  } finally {
    regLoading.value = false
  }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

.login-page {
  position: relative;
  z-index: 1;
  width: 100%;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Outfit', system-ui, sans-serif;
}

/* Toast */
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(139,92,246,0.15);
  border: 1px solid rgba(139,92,246,0.4);
  backdrop-filter: blur(12px);
  color: #c4b5fd;
  padding: 12px 28px;
  border-radius: 40px;
  font-size: 14px;
  font-weight: 500;
  z-index: 999;
  white-space: nowrap;
}
.toast-enter-active { animation: toastIn 0.4s cubic-bezier(0.34,1.56,0.64,1); }
.toast-leave-active { animation: toastOut 0.35s ease forwards; }
@keyframes toastIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
@keyframes toastOut {
  from { opacity: 1; transform: translateX(-50%) translateY(0); }
  to { opacity: 0; transform: translateX(-50%) translateY(-20px); }
}

/* Card */
.login-card {
  width: 100%;
  max-width: 440px;
  margin: 0 20px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  padding: 36px 36px 32px;
  backdrop-filter: blur(20px);
}

/* Tabs */
.tabs {
  display: flex;
  background: rgba(255,255,255,0.04);
  border-radius: 10px;
  padding: 4px;
  margin-bottom: 28px;
}
.tab {
  flex: 1;
  padding: 9px;
  border: none;
  background: transparent;
  color: #555;
  font-size: 14px;
  font-family: 'Outfit', system-ui, sans-serif;
  font-weight: 500;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}
.tab.active { background: rgba(139,92,246,0.2); color: #c4b5fd; }

/* Logo */
.logo-area { text-align: center; margin-bottom: 28px; }
.logo-text { font-size: 22px; font-weight: 700; color: #f0f0f0; letter-spacing: -0.02em; }
.dot { color: #8b5cf6; }
.logo-sub { font-size: 13px; color: #555; margin-top: 4px; font-weight: 300; }

/* Form */
.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; font-weight: 500; color: #666; letter-spacing: 0.04em; text-transform: uppercase; }
.field input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px;
  color: #f0f0f0;
  font-size: 14px;
  font-family: 'Outfit', system-ui, sans-serif;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.field input:focus { border-color: rgba(139,92,246,0.5); }
.field input.input-error { border-color: rgba(239,68,68,0.6) !important; }
.field input::placeholder { color: #333; }

.input-wrap { position: relative; display: flex; align-items: center; }
.input-wrap input { flex: 1; padding-right: 44px; }
.eye {
  position: absolute;
  right: 12px;
  cursor: pointer;
  font-size: 14px;
  opacity: 0.5;
  transition: opacity 0.2s;
  user-select: none;
}
.eye:hover { opacity: 1; }

.send-code {
  position: absolute;
  right: 8px;
  background: rgba(139,92,246,0.15);
  border: 1px solid rgba(139,92,246,0.3);
  color: #a78bfa;
  font-size: 12px;
  font-family: 'Outfit', system-ui, sans-serif;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.send-code:hover:not(:disabled) { background: rgba(139,92,246,0.25); }
.send-code:disabled { opacity: 0.4; cursor: not-allowed; }

.remember-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: -4px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #666;
}
.checkbox-label input[type=checkbox] { accent-color: #8b5cf6; width: 14px; height: 14px; }
.forgot { font-size: 13px; color: #555; text-decoration: none; transition: color 0.2s; }
.forgot:hover { color: #a78bfa; }

.field-error { font-size: 12px; color: #ef4444; margin-top: 2px; }
.error-msg { font-size: 13px; color: #ef4444; text-align: center; margin: -4px 0; }

.btn-primary {
  width: 100%;
  padding: 13px;
  background: #8b5cf6;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-family: 'Outfit', system-ui, sans-serif;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
  margin-top: 4px;
  position: relative;
  overflow: hidden;
}
.btn-primary:hover { background: #7c3aed; }
.btn-primary.loading { opacity: 0.7; cursor: not-allowed; }

.switch-tip {
  text-align: center;
  font-size: 13px;
  color: #555;
  margin-top: -4px;
}
.switch-tip span { color: #a78bfa; cursor: pointer; transition: color 0.2s; }
.switch-tip span:hover { color: #8b5cf6; }

/* Form transition */
.form-enter-active { animation: formIn 0.35s ease; }
.form-leave-active { animation: formOut 0.25s ease forwards; }
@keyframes formIn {
  from { opacity: 0; transform: translateX(16px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes formOut {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(-16px); }
}
</style>
