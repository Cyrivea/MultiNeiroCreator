import { createRouter, createWebHistory } from 'vue-router'
import { TOKEN_KEY } from '@/constants'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Intro',
      component: () => import('@/views/intro/Intro.vue'),
    },
    {
      path: '/home',
      name: 'Home',
      component: () => import('@/views/home/Home.vue'),
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/Login.vue'),
    },
    {
      path: '/workstation',
      name: 'Workstation',
      component: () => import('@/views/workstation/Workstation.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to, _, next) => {
  const token = localStorage.getItem(TOKEN_KEY)

  // 受保护页面：未登录 -> 去 /login
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }

  // 已登录访问 /login：直接放行到登录页，由登录页/调用方决定是否触发覆盖层
  next()
})

export default router
