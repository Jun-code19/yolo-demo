<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { HomeFilled, DataLine, VideoCamera, Fold, Expand, Picture, VideoPlay, Monitor, Setting, UserFilled } from '@element-plus/icons-vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import deviceApi from '@/api/device'

const router = useRouter()
const route = useRoute()
const username = ref('')
const isCollapse = ref(false)

// 是否显示登录页
const showLogin = computed(() => {
  return !localStorage.getItem('token')
})

onMounted(async () => {
  // 从本地存储中获取用户信息
  const userInfo = localStorage.getItem('userInfo')
  if (userInfo) {
    const user = JSON.parse(userInfo)
    username.value = user.username
  }
})

const handleLogout = () => {
  // 清除所有认证相关的存储
  localStorage.removeItem('token')
  localStorage.removeItem('userInfo')
  username.value = ''
  
  // 强制刷新页面，确保登录状态更新
  console.log("正在退出登录...");
  window.location.href = '/'
}

// 处理下拉菜单命令
const handleDropdownCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'profile') {
    router.push('/profile')
  }
}
</script>

<template>
  <!-- 使用路由系统显示登录页或主应用界面 -->
  <router-view v-if="showLogin"></router-view>
  
  <!-- 主应用界面 -->
  <el-container v-else class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '240px'" class="transition-width">
      <div class="logo-container">
        <img src="./assets/fangte_dark.ico" alt="Logo" class="logo-img" />
        <span class="logo-text" v-show="!isCollapse">智能视频分析系统</span>
      </div>
      <el-menu
        :default-active="route.path"
        class="el-menu-vertical"
        :router="true"
        background-color="#1e293b"
        text-color="#94a3b8"
        active-text-color="#ffffff"
        :collapse="isCollapse"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        
        <el-sub-menu index="detection">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>目标检测</span>
          </template>
          
          <el-menu-item index="/realtime">
            <el-icon><VideoCamera /></el-icon>
            <template #title>实时检测</template>
          </el-menu-item>
          
          <el-menu-item index="/video">
            <el-icon><VideoPlay /></el-icon>
            <template #title>视频检测</template>
          </el-menu-item>
          
          <el-menu-item index="/image">
            <el-icon><Picture /></el-icon>
            <template #title>图片检测</template>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/devices">
          <el-icon><VideoCamera /></el-icon>
          <template #title>设备管理</template>
        </el-menu-item>
        
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon>
          <template #title>数据统计</template>
        </el-menu-item>

        <el-menu-item index="/system">
          <el-icon><Setting /></el-icon>
          <template #title>系统状态</template>
        </el-menu-item>
        
        <el-menu-item index="/syslogs">
          <el-icon><DataLine /></el-icon>
          <template #title>系统日志</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container class="right-container">
      <el-header height="64px">
        <div class="header-content">
          <div class="header-left">
            <el-button
              class="collapse-btn"
              @click="isCollapse = !isCollapse"
            >
              <el-icon :size="14">
                <Fold v-if="!isCollapse" />
                <Expand v-else />
              </el-icon>
            </el-button>
          </div>
          <el-dropdown @command="handleDropdownCommand">
            <div class="user-info">
              <span class="username">{{ username }}</span>
              <el-avatar :size="32" :icon="UserFilled" />
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main>
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
/* 应用布局样式 */
.layout-container {
  width: 100%;
  height: 100%;
}

.right-container {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background-color: #f8fafc;
}

.el-aside {
  background-color: #1e293b;
  color: #fff;
  height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
  box-shadow: 4px 0 6px rgba(0, 0, 0, 0.05);
}

.transition-width {
  transition: width 0.3s ease-in-out;
}

.logo-container {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  background-color: #0f172a;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.logo-img {
  width: 32px;
  height: 32px;
  margin-right: 16px;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.logo-text {
  color: #ffffff;
  font-size: 16px;
  font-weight: 500;
  white-space: nowrap;
  letter-spacing: 0.5px;
  opacity: 0.95;
}

.el-menu {
  border-right: none;
  width: 100%;
}

:deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
  margin: 4px 0;
}

:deep(.el-menu-item.is-active) {
  background-color: #2d3a4f !important;
  border-right: 3px solid #409EFF;
}

:deep(.el-menu-item:hover) {
  background-color: #2d3a4f !important;
}

:deep(.el-menu-item .el-icon) {
  font-size: 18px;
}

.el-header {
  background-color: #ffffff;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 24px;
  position: relative;
  z-index: 999;
  height: 64px !important;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);
}

.header-content {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
}

.collapse-btn {
  height: 32px;
  width: 32px;
  padding: 0;
  font-size: 15px;
  border: 1px solid #e2e8f0;
  background-color: #f8fafc;
  color: #1e293b;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.collapse-btn:hover {
  background-color: #1e293b;
  color: #ffffff;
  border-color: #1e293b;
  transform: scale(1.05);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background-color 0.3s ease;
}

.user-info:hover {
  background-color: #f1f5f9;
}

.username {
  margin-right: 8px;
  font-weight: 500;
  color: #334155;
}
</style>
