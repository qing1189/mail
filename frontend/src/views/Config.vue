<template>
  <div class="config-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>配置管理</span>
          <div>
            <el-button type="primary" @click="handleSave">保存配置</el-button>
            <el-button type="warning" @click="handleReset">重置默认</el-button>
          </div>
        </div>
      </template>

      <el-form :model="configForm" label-width="140px" style="max-width: 800px">
        <!-- 基础配置 -->
        <el-divider content-position="left">基础配置</el-divider>

        <el-form-item label="浏览器引擎">
          <el-input value="ruyipage" disabled />
        </el-form-item>

        <el-form-item label="邮箱后缀">
          <el-select v-model="configForm.email_suffix" style="width: 100%">
            <el-option label="@outlook.com" value="@outlook.com" />
            <el-option label="@hotmail.com" value="@hotmail.com" />
          </el-select>
        </el-form-item>

        <!-- 代理配置 -->
        <el-divider content-position="left">代理配置</el-divider>

        <el-form-item label="代理来源">
          <el-select v-model="configForm.proxy_source" style="width: 100%">
            <el-option label="无代理（直连）" value="none" />
            <el-option label="文件 (HOST:PORT:USER:PASS)" value="file" />
            <el-option label="免费文件 (HOST:PORT)" value="freefile" />
            <el-option label="API" value="api" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="configForm.proxy_source === 'file' || configForm.proxy_source === 'freefile'" label="代理文件路径">
          <el-input v-model="configForm.proxy_file" />
        </el-form-item>

        <el-form-item v-if="configForm.proxy_source === 'api'" label="代理 API 地址">
          <el-input v-model="configForm.proxy_api_url" placeholder="http://..." />
        </el-form-item>

        <el-form-item label="代理超时(秒)">
          <el-input-number v-model="configForm.proxy_api_timeout" :min="1" :max="30" />
        </el-form-item>

        <!-- 任务配置 -->
        <el-divider content-position="left">任务配置</el-divider>

        <el-form-item label="并发线程数">
          <el-input-number v-model="configForm.concurrent_flows" :min="1" :max="50" />
          <span class="form-tip">同时运行的浏览器实例数量</span>
        </el-form-item>

        <el-form-item label="最大任务数">
          <el-input-number v-model="configForm.max_tasks" :min="1" :max="1000" />
          <span class="form-tip">本次运行的最大注册数量</span>
        </el-form-item>

        <el-form-item label="风控等待(秒)">
          <el-input-number v-model="configForm.bot_protection_wait" :min="0" :max="30" />
          <span class="form-tip">注册时的随机等待时间</span>
        </el-form-item>

        <el-form-item label="验证码重试">
          <el-input-number v-model="configForm.max_captcha_retries" :min="0" :max="5" />
        </el-form-item>

        <!-- OAuth2 配置 -->
        <el-divider content-position="left">OAuth2 配置</el-divider>

        <el-form-item label="启用 OAuth2">
          <el-switch v-model="configForm.oauth2.enable_oauth2" />
          <span class="form-tip">注册成功后获取 Token</span>
        </el-form-item>

        <template v-if="configForm.oauth2.enable_oauth2">
          <el-form-item label="Client ID">
            <el-input v-model="configForm.oauth2.client_id" />
          </el-form-item>

          <el-form-item label="Redirect URL">
            <el-input v-model="configForm.oauth2.redirect_url" />
          </el-form-item>

          <el-form-item label="Scopes">
            <el-tag
              v-for="scope in configForm.oauth2.Scopes"
              :key="scope"
              closable
              @close="removeScope(scope)"
              style="margin-right: 8px; margin-bottom: 8px"
            >
              {{ scope }}
            </el-tag>
            <el-input
              v-if="scopeInputVisible"
              ref="scopeInputRef"
              v-model="scopeInputValue"
              size="small"
              style="width: 300px"
              @keyup.enter="addScope"
              @blur="addScope"
            />
            <el-button v-else size="small" @click="showScopeInput">+ 添加 Scope</el-button>
          </el-form-item>
        </template>

        <!-- 浏览器配置 -->
        <el-divider content-position="left">浏览器配置</el-divider>

        <el-form-item label="浏览器路径">
          <el-input v-model="configForm.ruyipage.browser_path" placeholder="留空使用默认" />
        </el-form-item>

        <el-form-item label="无头模式">
          <el-switch v-model="configForm.ruyipage.headless" />
          <span class="form-tip">不显示浏览器窗口</span>
        </el-form-item>

        <el-form-item label="XPath 选择器">
          <el-switch v-model="configForm.ruyipage.xpath_picker" />
        </el-form-item>

        <el-form-item label="操作可视化">
          <el-switch v-model="configForm.ruyipage.action_visual" />
          <span class="form-tip">显示调试信息</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { configApi } from '@/api'

const configForm = ref({
  email_suffix: '@outlook.com',
  proxy_source: 'api',
  proxy_file: 'proxies.txt',
  proxy_api_url: '',
  proxy_api_timeout: 8,
  bot_protection_wait: 11,
  max_captcha_retries: 2,
  concurrent_flows: 10,
  max_tasks: 20,
  oauth2: {
    enable_oauth2: false,
    client_id: '',
    redirect_url: 'http://localhost:8000',
    Scopes: [
      'offline_access',
      'https://graph.microsoft.com/Mail.ReadWrite',
      'https://graph.microsoft.com/Mail.Send',
      'https://graph.microsoft.com/User.Read',
    ],
  },
  ruyipage: {
    browser_path: '',
    profile_root: 'Profiles',
    headless: false,
    xpath_picker: false,
    action_visual: false,
  },
})

const scopeInputVisible = ref(false)
const scopeInputValue = ref('')
const scopeInputRef = ref(null)

onMounted(async () => {
  await loadConfig()
})

async function loadConfig() {
  try {
    const res = await configApi.get()
    if (res.code === 0) {
      // 合并配置，保留默认值
      const config = res.data
      Object.keys(config).forEach((key) => {
        if (key === 'oauth2' || key === 'ruyipage') {
          configForm.value[key] = { ...configForm.value[key], ...config[key] }
        } else {
          configForm.value[key] = config[key]
        }
      })
    }
  } catch (e) {
    console.error('Failed to load config:', e)
  }
}

async function handleSave() {
  try {
    const res = await configApi.update(configForm.value)
    if (res.code === 0) {
      ElMessage.success('配置已保存')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定要重置为默认配置吗？', '确认', {
      type: 'warning',
    })
    const res = await configApi.reset()
    if (res.code === 0) {
      ElMessage.success('已重置为默认配置')
      await loadConfig()
    } else {
      ElMessage.error(res.message || '重置失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('重置失败')
    }
  }
}

function removeScope(scope) {
  const index = configForm.value.oauth2.Scopes.indexOf(scope)
  if (index !== -1) {
    configForm.value.oauth2.Scopes.splice(index, 1)
  }
}

function showScopeInput() {
  scopeInputVisible.value = true
  nextTick(() => {
    scopeInputRef.value?.focus()
  })
}

function addScope() {
  if (scopeInputValue.value) {
    configForm.value.oauth2.Scopes.push(scopeInputValue.value)
  }
  scopeInputVisible.value = false
  scopeInputValue.value = ''
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  margin-left: 12px;
  color: #999;
  font-size: 12px;
}
</style>
