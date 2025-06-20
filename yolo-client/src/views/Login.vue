<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Monitor, VideoCamera, Picture, DataLine, UserFilled, Lock } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import deviceApi from '@/api/device'

const router = useRouter()
const loading = ref(false)

// 系统初始化状态
const isInitializing = ref(false)
const isSystemInitialized = ref(true)

// 登录表单
const loginForm = reactive({
  username: '',
  password: ''
})

// 管理员注册表单
const adminForm = reactive({
  user_id: '',
  username: '',
  password: '',
  password_confirm: '',
  role: 'admin',
  allowed_devices: []
})

// 表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3到20个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应在6到20个字符之间', trigger: 'blur' }
  ]
}

// 管理员注册表单规则
const adminRules = {
  user_id: [
    { required: true, message: '请输入用户ID', trigger: 'blur' },
    { min: 3, max: 20, message: '用户ID长度应在3到20个字符之间', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3到20个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应在6到20个字符之间', trigger: 'blur' }
  ],
  password_confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== adminForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const loginFormRef = ref(null)
const adminFormRef = ref(null)

onMounted(async () => {
  // 检查系统是否初始化
  try {
    const { data } = await deviceApi.checkSystemInitialized()
    isSystemInitialized.value = data.initialized
  } catch (error) {
    // console.error('检查系统初始化状态失败:', error)
  }
})

// 登录处理
const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const response = await deviceApi.login(loginForm.username, loginForm.password)
      const { access_token } = response.data

      // 保存token
      localStorage.setItem('token', access_token)

      // 获取用户信息
      const userInfo = await deviceApi.getCurrentUser()
      localStorage.setItem('userInfo', JSON.stringify(userInfo.data))

      ElMessage.success('登录成功')

      // 重置表单
      loginForm.username = ''
      loginForm.password = ''

      // 强制刷新页面，确保登录状态更新并跳转
      window.location.href = '/'
    } catch (error) {
      // console.error('登录失败:', error)
      let errorMsg = '登录失败: 用户名或密码错误'

      // 显示详细错误信息以便调试
      if (error.response) {
        errorMsg += `\n状态码: ${error.response.status}`
        // console.error("错误详情:", error.response.data);
        if (error.response.data && error.response.data.detail) {
          errorMsg += `\n详情: ${error.response.data.detail}`
        }
      }

      ElMessage.error(errorMsg)
    } finally {
      loading.value = false
    }
  })
}

// 创建管理员账户
const handleInitSystem = async () => {
  if (!adminFormRef.value) return

  await adminFormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      // 创建管理员数据对象（删除确认密码字段）
      const adminData = { ...adminForm }
      delete adminData.password_confirm

      await deviceApi.initializeSystem(adminData)
      ElMessage.success('系统初始化成功，管理员账户已创建')
      isInitializing.value = false
      isSystemInitialized.value = true

      // 使用刚创建的管理员账户登录
      loginForm.username = adminForm.username
      loginForm.password = adminForm.password

      // 清空管理员表单
      adminForm.user_id = ''
      adminForm.username = ''
      adminForm.password = ''
      adminForm.password_confirm = ''
    } catch (error) {
      // console.error('初始化系统失败:', error)
      ElMessage.error(`初始化失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      loading.value = false
    }
  })
}

// 切换到初始化系统界面
const showInitForm = () => {
  isInitializing.value = true
}

// 返回登录页
const backToLogin = () => {
  isInitializing.value = false
}
</script>

<template>
  <div class="login-container">
    <div class="login-panel">
      <div class="login-left">
        <div class="left-content">
          <div class="logo-box">
            <el-icon :size="64">
              <Monitor />
            </el-icon>
          </div>
          <h1>智能视频分析系统</h1>
          <p>YOLO Client</p>
          <div class="feature-list">
            <div class="feature-item">
              <el-icon>
                <VideoCamera />
              </el-icon>
              <span>实时视频分析</span>
            </div>
            <div class="feature-item">
              <el-icon>
                <Picture />
              </el-icon>
              <span>异常行为检测</span>
            </div>
            <div class="feature-item">
              <el-icon>
                <DataLine />
              </el-icon>
              <span>数据可视分析</span>
            </div>
          </div>
        </div>
      </div>

      <div class="login-right">
        <div class="login-form">
          <!-- 系统未初始化时显示初始化设置 -->
          <template v-if="!isSystemInitialized">
            <div class="login-header" v-if="!isInitializing">
              <h2>系统初始化</h2>
              <p>系统首次使用，需要创建管理员账户</p>
            </div>

            <div v-if="!isInitializing" class="init-notice">
              <el-alert title="系统尚未初始化" type="info" description="检测到系统是首次使用，请先创建一个管理员账户。" show-icon :closable="false" />
              <el-button type="primary" @click="showInitForm" style="width: 100%; margin-top: 16px;">
                创建管理员账户
              </el-button>
            </div>

            <!-- 管理员注册表单 -->
            <template v-if="isInitializing">
              <div class="login-header">
                <h2>创建管理员</h2>
                <p>请设置系统管理员账户信息</p>
              </div>

              <el-form ref="adminFormRef" :model="adminForm" :rules="adminRules" label-width="0"
                @keyup.enter="handleInitSystem">
                <el-form-item prop="user_id">
                  <el-input v-model="adminForm.user_id" placeholder="请输入用户ID" :prefix-icon="UserFilled" size="large" />
                </el-form-item>

                <el-form-item prop="username">
                  <el-input v-model="adminForm.username" placeholder="请输入用户名" :prefix-icon="UserFilled" size="large" />
                </el-form-item>

                <el-form-item prop="password">
                  <el-input v-model="adminForm.password" type="password" placeholder="请输入密码" :prefix-icon="Lock"
                    show-password size="large" />
                </el-form-item>

                <el-form-item prop="password_confirm">
                  <el-input v-model="adminForm.password_confirm" type="password" placeholder="请再次输入密码"
                    :prefix-icon="Lock" show-password size="large" />
                </el-form-item>

                <el-form-item>
                  <div class="form-actions">
                    <el-button @click="backToLogin">返回</el-button>
                    <el-button type="primary" @click="handleInitSystem" :loading="loading" class="init-button">
                      创建管理员
                    </el-button>
                  </div>
                </el-form-item>
              </el-form>
            </template>
          </template>

          <!-- 登录表单 -->
          <template v-else>
            <div class="login-header">
              <h2>账号登录</h2>
              <p>欢迎回来，请输入您的账号信息</p>
            </div>

            <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-width="0"
              @keyup.enter="handleLogin">
              <el-form-item prop="username">
                <el-input v-model="loginForm.username" placeholder="请输入用户名" :prefix-icon="UserFilled" size="large" />
              </el-form-item>

              <el-form-item prop="password">
                <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" :prefix-icon="Lock"
                  show-password size="large" />
              </el-form-item>

              <el-form-item>
                <el-button type="primary" class="login-button" :loading="loading" @click="handleLogin" size="large"
                  :disabled="loading">
                  {{ loading ? '登录中...' : '登录系统' }}
                </el-button>
              </el-form-item>
            </el-form>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 登录页样式 - 方特主题公园风格 */
.login-container {
  height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #ff6b6b 100%);
  overflow: hidden;
  position: relative;
}

.login-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 107, 107, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(74, 144, 226, 0.3) 0%, transparent 50%);
  z-index: 1;
}

.login-panel {
  width: 1000px;
  height: 600px;
  background-color: #fff;
  border-radius: 20px;
  box-shadow:
    0 20px 60px rgba(0, 0, 0, 0.2),
    0 8px 30px rgba(255, 107, 107, 0.1);
  display: flex;
  overflow: hidden;
  position: relative;
  z-index: 2;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.login-left {
  flex: 1;
  background: linear-gradient(135deg, #4a90e2 0%, #1e3c72 50%, #ff8a65 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  padding: 60px 40px;
  position: relative;
  overflow: hidden;
}

.login-left::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(circle at 30% 40%, rgba(255, 255, 255, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(255, 138, 101, 0.2) 0%, transparent 50%);
  z-index: 1;
}

.login-left::after {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle fill="rgba(255,255,255,0.05)" cx="50" cy="50" r="2"/></svg>') repeat;
  background-size: 40px 40px;
  animation: float 20s infinite linear;
  z-index: 1;
}

@keyframes float {
  0% {
    transform: translateX(-50px) translateY(-50px);
  }

  100% {
    transform: translateX(50px) translateY(50px);
  }
}

.left-content {
  text-align: center;
  position: relative;
  z-index: 2;
}

.logo-box {
  width: 100px;
  height: 100px;
  margin: 0 auto 30px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.25), rgba(255, 138, 101, 0.3));
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
  border: 2px solid rgba(255, 255, 255, 0.2);
  position: relative;
}

.logo-box::before {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ff8a65, #4a90e2);
  z-index: -1;
  animation: rotate 3s linear infinite;
}

@keyframes rotate {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.left-content h1 {
  font-size: 42px;
  margin-bottom: 16px;
  font-weight: 700;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #ffffff, #ffe0b5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.left-content p {
  font-size: 20px;
  opacity: 0.95;
  margin-bottom: 40px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.feature-list {
  text-align: left;
  max-width: 280px;
  margin: 0 auto;
}

.feature-item {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 138, 101, 0.1));
  padding: 14px 20px;
  border-radius: 12px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.feature-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.feature-item:hover {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.25), rgba(255, 138, 101, 0.2));
  transform: translateX(8px) translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.feature-item:hover::before {
  left: 100%;
}

.feature-item .el-icon {
  margin-right: 12px;
  font-size: 22px;
  color: #ffe0b5;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

.feature-item span {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.95);
  font-weight: 500;
}

.login-right {
  width: 400px;
  padding: 60px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
  position: relative;
}

.login-right::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(74, 144, 226, 0.1) 0%, transparent 70%);
  border-radius: 50%;
  transform: translate(50%, -50%);
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
  position: relative;
  z-index: 2;
}

.login-header h2 {
  font-size: 28px;
  color: #1e3c72;
  margin-bottom: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #1e3c72, #4a90e2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.login-header p {
  font-size: 16px;
  color: #6b7c93;
  font-weight: 500;
}

.login-form {
  width: 100%;
  position: relative;
  z-index: 2;
}

:deep(.el-input__wrapper) {
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
  box-shadow: 0 2px 12px rgba(74, 144, 226, 0.1) !important;
  border: 2px solid rgba(74, 144, 226, 0.2);
  border-radius: 12px;
  transition: all 0.3s ease;
  height: 50px;
}

:deep(.el-input__wrapper:hover) {
  border-color: #4a90e2;
  background: #ffffff;
  box-shadow: 0 4px 20px rgba(74, 144, 226, 0.15) !important;
  transform: translateY(-1px);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #4a90e2;
  background: #ffffff;
  box-shadow:
    /* 0 4px 20px rgba(74, 144, 226, 0.2) !important, */
    0 0 0 3px rgba(74, 144, 226, 0.1) !important;
  transform: translateY(-1px);
}

:deep(.el-input__inner) {
  height: 46px;
  color: #1e3c72;
  font-weight: 500;
  font-size: 15px;
}

:deep(.el-input__inner::placeholder) {
  color: #a0aec0;
}

:deep(.el-input__prefix-inner) {
  color: #4a90e2;
  font-size: 18px;
}

:deep(.el-form-item) {
  margin-bottom: 24px;
}

.login-button,
.init-button {
  width: 100%;
  height: 50px;
  border-radius: 12px;
  /* font-size: 16px; */
  font-weight: 600;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #4a90e2 0%, #1e3c72 50%, #ff8a65 100%);
  border: none;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
}

.login-button::before,
.init-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transition: left 0.5s ease;
}

.login-button:hover,
.init-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(74, 144, 226, 0.4);
  background: linear-gradient(135deg, #5ba0f2 0%, #2e4c82 50%, #ff9a75 100%);
}

.login-button:hover::before,
.init-button:hover::before {
  left: 100%;
}

.login-button:active,
.init-button:active {
  transform: translateY(0);
  box-shadow: 0 4px 15px rgba(74, 144, 226, 0.3);
}

.init-notice {
  margin-top: 20px;
  position: relative;
  z-index: 2;
}

:deep(.el-alert) {
  border-radius: 12px;
  border: 2px solid rgba(74, 144, 226, 0.2);
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
}

.form-actions {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}

.form-actions .el-button {
  flex: 1;
  height: 45px;
  border-radius: 10px;
  font-weight: 600;
}

.form-actions .el-button:first-child {
  background: linear-gradient(135deg, #e2e8f0, #cbd5e0);
  color: #4a5568;
  border: none;
}

.form-actions .el-button:first-child:hover {
  background: linear-gradient(135deg, #cbd5e0, #a0aec0);
  transform: translateY(-1px);
}

/* 响应式设计 */
@media screen and (max-width: 1200px) {
  .login-panel {
    width: 90%;
    max-width: 1000px;
  }
}

@media screen and (max-width: 768px) {
  .login-panel {
    width: 95%;
    height: auto;
    flex-direction: column;
    max-height: 90vh;
    overflow-y: auto;
  }

  .login-left {
    padding: 40px 20px;
  }

  .logo-box {
    width: 80px;
    height: 80px;
    margin-bottom: 20px;
  }

  .left-content h1 {
    font-size: 32px;
    margin-bottom: 12px;
  }

  .left-content p {
    font-size: 18px;
    margin-bottom: 30px;
  }

  .feature-list {
    max-width: 240px;
  }

  .feature-item {
    padding: 12px 16px;
    margin-bottom: 16px;
  }

  .feature-item:hover {
    transform: none;
  }

  .login-right {
    width: 100%;
    padding: 40px 20px;
  }

  .login-header {
    margin-bottom: 30px;
  }

  :deep(.el-input__wrapper) {
    height: 45px;
  }  :deep(.el-input__inner) {
    height: 41px;
  }
}
</style> 