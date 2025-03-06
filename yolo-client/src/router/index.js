import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      requiresAuth: false
    }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/system',
    name: 'System',
    component: () => import('../views/System.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('../views/Devices.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/realtime',
    name: 'RealtimeDetection',
    component: () => import('../views/detection/RealtimeDetection.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/video',
    name: 'VideoDetection',
    component: () => import('../views/detection/VideoDetection.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/image',
    name: 'ImageDetection',
    component: () => import('../views/detection/ImageDetection.vue'),
    meta: {
      requiresAuth: true
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const isAuthenticated = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，重定向到登录页
    next({ path: '/login' })
  } else if (to.path === '/login' && isAuthenticated) {
    // 已登录但访问登录页，重定向到首页
    next({ path: '/' })
  } else {
    next()
  }
})

export default router 