<template>
  <div class="task-control">
    <el-row :gutter="20">
      <!-- 任务配置 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>任务配置</span>
          </template>
          <el-form :model="taskForm" label-width="120px">
            <el-form-item label="邮箱后缀">
              <el-select v-model="taskForm.email_suffix" style="width: 100%">
                <el-option label="@outlook.com" value="@outlook.com" />
                <el-option label="@hotmail.com" value="@hotmail.com" />
              </el-select>
            </el-form-item>

            <el-form-item label="代理来源">
              <el-select v-model="taskForm.proxy_source" style="width: 100%">
                <el-option label="文件 (HOST:PORT:USER:PASS)" value="file" />
                <el-option label="免费文件 (HOST:PORT)" value="freefile" />
                <el-option label="API" value="api" />
              </el-select>
            </el-form-item>

            <el-form-item v-if="taskForm.proxy_source === 'file' || taskForm.proxy_source === 'freefile'" label="代理文件">
              <el-input v-model="taskForm.proxy_file" placeholder="proxies.txt" />
            </el-form-item>

            <el-form-item v-if="taskForm.proxy_source === 'api'" label="代理 API">
              <el-input v-model="taskForm.proxy_api_url" placeholder="http://..." />
            </el-form-item>

            <el-form-item label="并发线程数">
              <el-input-number v-model="taskForm.concurrent_flows" :min="1" :max="50" />
            </el-form-item>

            <el-form-item label="最大任务数">
              <el-input-number v-model="taskForm.max_tasks" :min="1" :max="1000" />
            </el-form-item>

            <el-divider>OAuth2 配置</el-divider>

            <el-form-item label="启用 OAuth2">
              <el-switch v-model="taskForm.enable_oauth2" />
            </el-form-item>

            <el-form-item v-if="taskForm.enable_oauth2" label="Client ID">
              <el-input v-model="taskForm.client_id" placeholder="输入 Client ID" />
            </el-form-item>

            <el-form-item v-if="taskForm.enable_oauth2" label="Redirect URL">
              <el-input v-model="taskForm.redirect_url" placeholder="http://localhost:8000" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 任务控制 -->
      <el-col :span="12">
        <!-- 控制按钮 -->
        <el-card style="margin-bottom: 20px">
          <template #header>
            <span>任务控制</span>
          </template>
          <div class="control-buttons">
            <el-button
              type="success"
              size="large"
              :icon="VideoPlay"
              :disabled="taskStore.isRunning"
              @click="handleStart"
            >
              启动任务
            </el-button>
            <el-button
              type="danger"
              size="large"
              :icon="VideoPause"
              :disabled="!taskStore.isRunning"
              @click="handleStop"
            >
              停止任务
            </el-button>
          </div>
        </el-card>

        <!-- 实时状态 -->
        <el-card>
          <template #header>
            <span>实时状态</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="运行状态">
              <el-tag :type="taskStore.isRunning ? 'success' : 'info'">
                {{ taskStore.isRunning ? (taskStore.isStopping ? '正在停止' : '运行中') : '已停止' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="总任务">
              {{ taskStore.status.total_tasks }}
            </el-descriptions-item>
            <el-descriptions-item label="已提交">
              {{ taskStore.status.submitted }}
            </el-descriptions-item>
            <el-descriptions-item label="剩余">
              {{ taskStore.status.remaining }}
            </el-descriptions-item>
            <el-descriptions-item label="成功">
              <span style="color: #52c41a">{{ taskStore.status.succeeded }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="失败">
              <span style="color: #ff4d4f">{{ taskStore.status.failed }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="成功率">
              {{ taskStore.status.success_rate }}%
            </el-descriptions-item>
            <el-descriptions-item label="活跃线程">
              {{ taskStore.status.active_threads }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- 进度条 -->
          <div style="margin-top: 20px">
            <el-progress
              :percentage="taskStore.progress"
              :stroke-width="20"
              :text-inside="true"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { configApi } from '@/api'

const taskStore = useTaskStore()

const taskForm = ref({
  email_suffix: '@outlook.com',
  proxy_source: 'api',
  proxy_file: 'proxies.txt',
  proxy_api_url: '',
  concurrent_flows: 10,
  max_tasks: 20,
  enable_oauth2: false,
  client_id: '',
  redirect_url: 'http://localhost:8000',
})

onMounted(async () => {
  // 加载当前配置
  try {
    const res = await configApi.get()
    if (res.code === 0) {
      const config = res.data
      taskForm.value.email_suffix = config.email_suffix || '@outlook.com'
      taskForm.value.proxy_source = config.proxy_source || 'api'
      taskForm.value.proxy_file = config.proxy_file || 'proxies.txt'
      taskForm.value.proxy_api_url = config.proxy_api_url || ''
      taskForm.value.concurrent_flows = config.concurrent_flows || 10
      taskForm.value.max_tasks = config.max_tasks || 20
      if (config.oauth2) {
        taskForm.value.enable_oauth2 = config.oauth2.enable_oauth2 || false
        taskForm.value.client_id = config.oauth2.client_id || ''
        taskForm.value.redirect_url = config.oauth2.redirect_url || 'http://localhost:8000'
      }
    }
  } catch (e) {
    console.error('Failed to load config:', e)
  }
})

async function handleStart() {
  try {
    await ElMessageBox.confirm('确定要启动任务吗？', '确认', {
      type: 'info',
    })
    const res = await taskStore.startTask(taskForm.value)
    if (res.code === 0) {
      ElMessage.success('任务已启动')
    } else {
      ElMessage.error(res.message || '启动失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('启动失败')
    }
  }
}

async function handleStop() {
  try {
    await ElMessageBox.confirm('确定要停止任务吗？', '确认', {
      type: 'warning',
    })
    const res = await taskStore.stopTask()
    if (res.code === 0) {
      ElMessage.success('正在停止任务...')
    } else {
      ElMessage.error(res.message || '停止失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('停止失败')
    }
  }
}
</script>

<style scoped>
.control-buttons {
  display: flex;
  justify-content: center;
  gap: 20px;
  padding: 20px 0;
}

.control-buttons .el-button {
  width: 160px;
  height: 60px;
  font-size: 16px;
}
</style>
