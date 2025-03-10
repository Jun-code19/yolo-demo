import { createRouter, createWebHistory } from 'vue-router'

const routes = [
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
    path: '/syslogs',
    name: 'SystemLogs',
    component: () => import('../views/SystemLogs.vue'),
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
    // 需要认证但未登录，直接在当前页显示登录界面
    console.log('需要认证但未登录，显示登录界面')
    next({ path: '/', replace: true })
  } else {
    // 正常导航
    next()
  }
})

export default router 