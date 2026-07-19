import { createRouter, createWebHistory } from 'vue-router'
import { TOKEN_KEY } from '@/constants'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
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
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/workstation')
  } else {
    next()
  }
})

export default router
