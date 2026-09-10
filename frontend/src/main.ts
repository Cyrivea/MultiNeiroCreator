import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import App from './App.vue'
import './style.css'
import { vRipple } from '@/directives/ripple'
import { vReveal } from '@/directives/reveal'

// Element Plus 不再全量引入（D4）：全库唯一用途是 ElMessage，
// 由 @/utils/toast 按需引入组件与样式；图标库无任何使用，注册已删除。
const app = createApp(App)

app.use(createPinia())
app.use(router)
app.directive('ripple', vRipple)
app.directive('reveal', vReveal)
app.mount('#app')
