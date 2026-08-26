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
    component: () => import('../views/device/Devices.vue'),
    meta: {
      requiresAuth: true
    }
  },
  {
    path: '/devices/area-config/:deviceId',
    name: 'AreaConfigSetting',
    component: () => import('../views/device/AreaConfigSetting.vue'),
    meta: {
      requiresAuth: true,
      title: '区域设置'
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
    redirect: '/models/list?tab=video'
  },
  {
    path: '/image',
    redirect: '/models/list?tab=image'
  },
  {
    path: '/models',
    component: () => import('../views/models/Layout.vue'),
    meta: {
      requiresAuth: true
    },
    children: [
      {
        path: '',
        redirect: '/models/list'
      },
      {
        path: 'list',
        name: 'ModelList',
        component: () => import('../views/models/ModelList.vue'),
        meta: {
          requiresAuth: true,
          title: '本地模型'
        }
      },
      {
        path: 'vlm',
        name: 'VlmManagement',
        component: () => import('../views/models/VlmManagement.vue'),
        meta: {
          requiresAuth: true,
          title: 'VLM 大模型'
        }
      },
      {
        path: 'image',
        redirect: { path: '/models/list', query: { tab: 'image' } }
      },
      {
        path: 'video',
        redirect: { path: '/models/list', query: { tab: 'video' } }
      }
    ]
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
    name: 'DataListenerHub',
    component: () => import('../views/dataPush/DataListenerHub.vue'),
    meta: {
      requiresAuth: true,
      title: '事件监听'
    }
  },
  {
    path: '/data-events',
    redirect: (to) => ({
      path: '/data-listeners',
      query: { ...to.query, tab: 'events' }
    })
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
        redirect: { name: 'CrowdAnalysis' }
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
    path: '/vlm-inspection',
    component: () => import('@/views/vlm-inspection/Layout.vue'),
    children: [
      {
        path: '',
        name: 'VlmInspection',
        component: () => import('@/views/vlm-inspection/List.vue'),
        meta: { title: 'VLM 巡检', requiresAuth: true }
      },
      {
        path: 'detail/:id',
        name: 'VlmInspectionDetail',
        component: () => import('@/views/vlm-inspection/Detail.vue'),
        meta: { title: '巡检详情', requiresAuth: true }
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
    name: 'SmartSchemeHub',
    component: () => import('../views/smartScheme/SmartSchemeHub.vue'),
    meta: {
      requiresAuth: true,
      title: '事件订阅'
    }
  },
  {
    path: '/smart-events',
    redirect: (to) => ({
      path: '/smart-schemes',
      query: { ...to.query, tab: 'events' }
    })
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