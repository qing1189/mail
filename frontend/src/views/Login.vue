<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <el-icon :size="48" color="#1890ff"><Lock /></el-icon>
        <h2>Outlook Register</h2>
        <p>Web 控制面板</p>
      </div>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  password: '',
})

const rules = {
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
}

async function handleLogin() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  
  loading.value = true
  
  try {
    const res = await authApi.login(form.password)
    if (res.success) {
      ElMessage.success('登录成功')
      router.push('/dashboard')
    } else {
      ElMessage.error(res.message || '登录失败')
    }
  } catch (e) {
    if (e.response?.status === 401) {
      ElMessage.error('密码错误')
    } else {
      ElMessage.error('登录失败，请重试')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h2 {
  margin: 16px 0 8px;
  color: #333;
  font-size: 24px;
}

.login-header p {
  color: #999;
  font-size: 14px;
}
</style>
