import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElIcons from '@element-plus/icons-vue'
import router from '@/router'
import App from './App.vue'
import './style.css'
import { vRipple } from '@/directives/ripple'

const app = createApp(App)

Object.entries(ElIcons).forEach(([name, component]) => {
  app.component(name, component)
})

app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.directive('ripple', vRipple)
app.mount('#app')
