<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import deviceApi from '@/api/device'
import { useRouter } from 'vue-router'

// 引入路由
const router = useRouter()

// 加载状态
const loading = ref(false)
const passwordLoading = ref(false)

// 用户信息表单
const userForm = reactive({
  user_id: '',
  username: '',
  role: '',
  allowed_devices: []
})

// 修改密码表单
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

// 表单规则
const userRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应在3到20个字符之间', trigger: 'blur' }
  ]
}

const passwordRules = {
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应在6到20个字符之间', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { 
      validator: (rule, value, callback) => {
        if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      }, 
      trigger: 'blur' 
    }
  ]
}

// 表单引用
const userFormRef = ref(null)
const passwordFormRef = ref(null)

// 加载用户信息
onMounted(async () => {
  try {
    loading.value = true
    
    // 从localStorage获取基本信息
    const userInfo = localStorage.getItem('userInfo')
    if (userInfo) {
      const user = JSON.parse(userInfo)
      userForm.user_id = user.user_id
      userForm.username = user.username
      userForm.role = user.role
      userForm.allowed_devices = user.allowed_devices || []
    }
    
    // 如果需要，也可以从API获取最新信息
    const { data } = await deviceApi.getCurrentUser()
    userForm.user_id = data.user_id
    userForm.username = data.username
    userForm.role = data.role
    userForm.allowed_devices = data.allowed_devices || []
    
    // 更新localStorage中的用户信息
    localStorage.setItem('userInfo', JSON.stringify(data))
    
  } catch (error) {
    console.error('加载用户信息失败:', error)
    ElMessage.error('加载用户信息失败')
  } finally {
    loading.value = false
  }
})

// 更新用户信息
const updateUserInfo = async () => {
  if (!userFormRef.value) return
  
  await userFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    loading.value = true
    try {
      // 更新用户信息
      await deviceApi.updateUserProfile(userForm)
      
      // 更新localStorage中的用户信息
      localStorage.setItem('userInfo', JSON.stringify(userForm))
      
      // 触发页面刷新以更新顶部导航栏的用户名
      setTimeout(() => {
        window.location.reload()
      }, 1000)
      
      ElMessage.success('用户信息更新成功，页面将自动刷新')
    } catch (error) {
      console.error('更新用户信息失败:', error)
      ElMessage.error(`更新用户信息失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      loading.value = false
    }
  })
}

// 更新密码
const updatePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    passwordLoading.value = true
    try {
      // 更新密码
      await deviceApi.updatePassword({
        user_id: userForm.user_id,
        old_password: passwordForm.oldPassword,
        new_password: passwordForm.newPassword
      })
      
      // 清空密码表单
      passwordForm.oldPassword = ''
      passwordForm.newPassword = ''
      passwordForm.confirmPassword = ''
      
      // 显示成功消息并询问是否立即退出登录
      ElMessageBox.confirm(
        '密码更新成功！为了安全起见，您需要使用新密码重新登录。',
        '密码已更改',
        {
          confirmButtonText: '立即退出并重新登录',
          type: 'success',
          showCancelButton: false,
          center: true
        }
      ).then(() => {
        // 清除认证信息并跳转到登录页
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
        window.location.href = '/'
      })
    } catch (error) {
      console.error('更新密码失败:', error)
      ElMessage.error(`更新密码失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      passwordLoading.value = false
    }
  })
}
</script>

<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <h2>个人中心</h2>
        </div>
      </template>
      
      <el-tabs>
        <!-- 基本信息修改 -->
        <el-tab-pane label="个人信息">
          <el-form 
            ref="userFormRef"
            :model="userForm"
            :rules="userRules"
            label-width="100px"
            v-loading="loading"
          >
            <el-form-item label="用户ID">
              <el-input v-model="userForm.user_id" disabled />
            </el-form-item>
            
            <el-form-item label="用户名" prop="username">
              <el-input v-model="userForm.username" />
            </el-form-item>
            
            <el-form-item label="角色">
              <el-input v-model="userForm.role" disabled />
            </el-form-item>
            
            <el-form-item>
              <el-button 
                type="primary" 
                @click="updateUserInfo"
                :loading="loading"
              >
                保存修改
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <!-- 密码修改 -->
        <el-tab-pane label="修改密码">
          <el-form 
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="100px"
            v-loading="passwordLoading"
          >
            <el-form-item label="当前密码" prop="oldPassword">
              <el-input 
                v-model="passwordForm.oldPassword" 
                type="password"
                show-password
              />
            </el-form-item>
            
            <el-form-item label="新密码" prop="newPassword">
              <el-input 
                v-model="passwordForm.newPassword" 
                type="password"
                show-password
              />
            </el-form-item>
            
            <el-form-item label="确认新密码" prop="confirmPassword">
              <el-input 
                v-model="passwordForm.confirmPassword" 
                type="password"
                show-password
              />
            </el-form-item>
            
            <el-form-item>
              <el-button 
                type="primary" 
                @click="updatePassword"
                :loading="passwordLoading"
              >
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.profile-container {
  padding: 20px;
}

.profile-card {
  max-width: 800px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}
</style> 