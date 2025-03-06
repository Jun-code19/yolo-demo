<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-left">
        <div class="left-content">
          <div class="logo-box">
            <el-icon :size="64"><Monitor /></el-icon>
          </div>
          <h1>YOLO Client</h1>
          <p>智能视频分析系统</p>
          <div class="feature-list">
            <div class="feature-item">
              <el-icon><VideoCamera /></el-icon>
              <span>实时视频分析</span>
            </div>
            <div class="feature-item">
              <el-icon><Warning /></el-icon>
              <span>异常行为检测</span>
            </div>
            <div class="feature-item">
              <el-icon><DataAnalysis /></el-icon>
              <span>数据可视分析</span>
            </div>
          </div>
        </div>
      </div>
      <div class="login-right">
        <div class="login-form">
          <div class="login-header">
            <h2>账号登录</h2>
            <p>欢迎回来，请输入您的账号信息</p>
          </div>
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                :prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                :prefix-icon="Lock"
                show-password
                size="large"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                class="login-button"
                :loading="loading"
                @click="handleLogin"
                size="large"
              >
                登录系统
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { 
  User, 
  Lock, 
  Monitor,
  VideoCamera,
  Warning,
  DataAnalysis
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: 'admin123'
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能小于6位', trigger: 'blur' }
  ]
}

const handleLogin = () => {
  if (!loginFormRef.value) return

  loginFormRef.value.validate((valid) => {
    if (valid) {
      loading.value = true
      // 模拟登录请求
      setTimeout(() => {
        if (
          loginForm.username === 'admin' &&
          loginForm.password === 'admin123'
        ) {
          localStorage.setItem('token', 'demo-token')
          localStorage.setItem('user', JSON.stringify({
            username: loginForm.username
          }))
          router.push('/')
          ElMessage.success('登录成功')
        } else {
          ElMessage.error('用户名或密码错误')
        }
        loading.value = false
      }, 1000)
    }
  })
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #2b3a4d 0%, #1e2a3b 100%);
  overflow: hidden;
}

.login-box {
  width: 1000px;
  height: 600px;
  background-color: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  display: flex;
  overflow: hidden;
}

.login-left {
  flex: 1;
  background: linear-gradient(135deg, #36599f 0%, #192f5d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  padding: 60px 40px;
  position: relative;
}

.login-left::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="white" fill-opacity="0.05" x="0" y="0" width="100" height="100"/></svg>') repeat;
  opacity: 0.1;
}

.left-content {
  text-align: center;
  position: relative;
  z-index: 1;
}

.logo-box {
  width: 100px;
  height: 100px;
  margin: 0 auto 30px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.left-content h1 {
  font-size: 42px;
  margin-bottom: 16px;
  font-weight: 600;
  letter-spacing: 1px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.left-content p {
  font-size: 20px;
  opacity: 0.95;
  margin-bottom: 40px;
  color: rgba(255, 255, 255, 0.9);
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
  background: rgba(255, 255, 255, 0.08);
  padding: 12px 20px;
  border-radius: 8px;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.feature-item:hover {
  background: rgba(255, 255, 255, 0.12);
  transform: translateX(5px);
}

.feature-item .el-icon {
  margin-right: 12px;
  font-size: 20px;
  color: rgba(255, 255, 255, 0.9);
}

.feature-item span {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
}

.login-right {
  width: 400px;
  padding: 60px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #ffffff;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.login-header h2 {
  font-size: 28px;
  color: #2c3e50;
  margin-bottom: 12px;
  font-weight: 600;
}

.login-header p {
  font-size: 16px;
  color: #7f8c8d;
}

.login-form {
  width: 100%;
}

:deep(.el-input__wrapper) {
  background-color: #f8fafc;
  box-shadow: none !important;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  transition: all 0.3s ease;
}

:deep(.el-input__wrapper:hover) {
  border-color: #36599f;
  background-color: #fff;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #36599f;
  background-color: #fff;
  box-shadow: 0 0 0 2px rgba(54, 89, 159, 0.1) !important;
}

:deep(.el-input__inner) {
  height: 45px;
  color: #2c3e50;
}

:deep(.el-input__prefix-inner) {
  color: #7f8c8d;
}

:deep(.el-form-item) {
  margin-bottom: 24px;
}

.login-button {
  width: 100%;
  height: 45px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
  background: linear-gradient(135deg, #36599f 0%, #192f5d 100%);
  border: none;
  transition: all 0.3s ease;
}

.login-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(54, 89, 159, 0.3);
  opacity: 0.95;
}

.login-button:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(54, 89, 159, 0.3);
}

@media screen and (max-width: 1200px) {
  .login-box {
    width: 90%;
    max-width: 1000px;
  }
}

@media screen and (max-width: 768px) {
  .login-box {
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
    padding: 10px 16px;
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
}
</style> 