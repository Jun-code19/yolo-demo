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
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: {
      requiresAuth: false,
      title: 'AI行为监测数据大屏',
      layout: 'fullscreen'
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
  },
  {
    path: '/profile',
    name: 'UserProfile',
    component: () => import('../views/UserProfile.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/models',
    name: 'Models',
    component: () => import('../views/Models.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/detection/config',
    name: 'DetectionConfig',
    component: () => import('../views/detection/DetectionConfig.vue'),
    meta: {
      requiresAuth: true,
      title: '检测配置'
    }
  },
  {
    path: '/detection/events',
    name: 'DetectionEvents',
    component: () => import('../views/detection/DetectionEvents.vue'),
    meta: {
      requiresAuth: true,
      title: '检测事件'
    }
  },
  {
    path: '/detection/smart-config/:configId',
    name: 'SmartConfigSetting',
    component: () => import('../views/detection/SmartConfigSetting.vue'),
    meta: {
      requiresAuth: true,
      title: '智能方案设置'
    }
  },
  {
    path: '/push/config',
    name: 'PushConfig',
    component: () => import('../views/dataPush/PushConfig.vue'),
    meta: {
      requiresAuth: true,
      title: '数据推送配置'
    }
  },
  {
    path: '/data-listeners',
    name: 'DataListeners',
    component: () => import('../views/dataPush/DataListeners.vue'),
    meta: {
      requiresAuth: true,
      title: '数据监听器配置'
    }
  },
  {
    path:'/data-events',
    name:'DataEvents',
    component:()=>import('../views/dataPush/DataEvents.vue'),
    meta:{
      requiresAuth:true,
      title:'数据事件'
    }
  },
  {
    path: '/crowd-analysis',
    component: () => import('@/views/crowd-analysis/Layout.vue'),
    children: [
      {
        path: '',
        name: 'CrowdAnalysis',
        component: () => import('@/views/crowd-analysis/List.vue'),
        meta: { title: '人群分析', requiresAuth: true }
      },
      {
        path: 'create',
        name: 'CreateCrowdAnalysis',
        component: () => import('@/views/crowd-analysis/Create.vue'),
        meta: { title: '创建人群分析任务', requiresAuth: true }
      },
      {
        path: 'detail/:id',
        name: 'CrowdAnalysisDetail',
        component: () => import('@/views/crowd-analysis/Detail.vue'),
        meta: { title: '任务详情', requiresAuth: true }
      }
    ]
  },
  {
    path: '/edge-servers',
    name: 'EdgeServers',
    component: () => import('@/views/edgeServer/EdgeServers.vue'),
    meta: {
      requiresAuth: true,
      title: '边缘服务器管理'
    }
  },
  {
    path: '/edge-servers/:serverId',
    name: 'EdgeServerDetail',
    component: () => import('@/views/edgeServer/EdgeServerDetail.vue'),
    meta: {
      requiresAuth: true,
      title: '边缘服务器详情'
    }
  },
  {
    path: '/heatmap-management',
    name: 'HeatMapManagement',
    component: () => import('../views/HeatMapManagement.vue'),
    meta: {
      requiresAuth: false,
      title: '人数热力图管理',
      layout: 'fullscreen'
    }
  },
  {
    path: '/smart-schemes',
    name: 'SmartSchemeManagement',
    component: () => import('../views/smartScheme/SmartSchemeManagement.vue'),
    meta: {
      requiresAuth: true,
      title: '事件订阅管理'
    }
  },
  {
    path: '/smart-events',
    name: 'SmartEvents',
    component: () => import('../views/smartScheme/SmartEvents.vue'),
    meta: {
      requiresAuth: true,
      title: '订阅事件管理'
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
  
  // 为了调试，打印路由信息
  // console.log(`路由导航: 从 ${from.path} 到 ${to.path}, 认证状态: ${isAuthenticated ? '已登录' : '未登录'}`)
  
  if (to.meta.requiresAuth && !isAuthenticated) {
    // 需要认证但未登录，重定向到登录页
    // console.log('需要认证但未登录，重定向到登录页')
    next({ path: '/login', replace: true })
  } else if (to.path === '/login' && isAuthenticated) {
    // 已登录但访问登录页，重定向到首页
    // console.log('已登录但访问登录页，重定向到首页')
    next({ path: '/', replace: true })
  } else {
    // 正常导航
    next()
  }
})

export default router 