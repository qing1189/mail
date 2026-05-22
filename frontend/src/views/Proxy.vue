<template>
  <div class="proxy-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>代理管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="showAddDialog = true">添加代理</el-button>
            <el-button type="danger" plain @click="handleClear">清空</el-button>
          </div>
        </div>
      </template>

      <!-- 批量输入 -->
      <el-card shadow="never" style="margin-bottom: 20px">
        <template #header>
          <span>批量导入</span>
        </template>
        <el-input
          v-model="batchInput"
          type="textarea"
          :rows="6"
          placeholder="每行一个代理，格式：&#10;HOST:PORT&#10;HOST:PORT:USERNAME:PASSWORD&#10;&#10;示例：&#10;192.168.1.1:8080&#10;192.168.1.2:8080:user:pass"
        />
        <div style="margin-top: 12px">
          <el-button type="primary" @click="handleBatchImport">导入</el-button>
          <el-button @click="handleAppend">追加</el-button>
        </div>
      </el-card>

      <!-- 代理列表 -->
      <el-table :data="proxies" style="width: 100%" max-height="400">
        <el-table-column type="index" width="60" />
        <el-table-column prop="host" label="主机" min-width="150" />
        <el-table-column prop="port" label="端口" width="100" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="password" label="密码" width="120">
          <template #default="{ row }">
            {{ row.password ? '******' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="proxies.length > 0" style="margin-top: 16px; color: #666">
        共 {{ proxies.length }} 个代理
      </div>
    </el-card>

    <!-- 添加代理对话框 -->
    <el-dialog v-model="showAddDialog" title="添加代理" width="500">
      <el-form :model="newProxy" label-width="80px">
        <el-form-item label="主机" required>
          <el-input v-model="newProxy.host" placeholder="192.168.1.1" />
        </el-form-item>
        <el-form-item label="端口" required>
          <el-input v-model="newProxy.port" placeholder="8080" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="newProxy.username" placeholder="可选" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="newProxy.password" type="password" placeholder="可选" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { proxyApi } from '@/api'

const proxies = ref([])
const showAddDialog = ref(false)
const batchInput = ref('')
const newProxy = ref({
  host: '',
  port: '',
  username: '',
  password: '',
})

onMounted(() => {
  loadProxies()
})

async function loadProxies() {
  try {
    const res = await proxyApi.get()
    if (res.code === 0) {
      proxies.value = res.data
    }
  } catch (e) {
    console.error('Failed to load proxies:', e)
  }
}

async function handleAdd() {
  if (!newProxy.value.host || !newProxy.value.port) {
    ElMessage.warning('请输入主机和端口')
    return
  }
  try {
    const res = await proxyApi.add(newProxy.value)
    if (res.code === 0) {
      ElMessage.success('代理已添加')
      showAddDialog.value = false
      newProxy.value = { host: '', port: '', username: '', password: '' }
      await loadProxies()
    } else {
      ElMessage.error(res.message || '添加失败')
    }
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

async function handleDelete(proxy) {
  try {
    await ElMessageBox.confirm(`确定删除代理 ${proxy.host}:${proxy.port}？`, '确认')
    const res = await proxyApi.delete(proxy.host, proxy.port)
    if (res.code === 0) {
      ElMessage.success('已删除')
      await loadProxies()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm('确定清空所有代理？', '确认', { type: 'warning' })
    const res = await proxyApi.clear()
    if (res.code === 0) {
      ElMessage.success('已清空')
      await loadProxies()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

function parseProxyLine(line) {
  line = line.trim()
  if (!line || line.startsWith('#')) return null
  
  const parts = line.split(':')
  if (parts.length < 2) return null
  
  return {
    host: parts[0],
    port: parts[1],
    username: parts[2] || '',
    password: parts[3] || '',
  }
}

async function handleBatchImport() {
  const lines = batchInput.value.split('\n')
  const newProxies = []
  
  for (const line of lines) {
    const proxy = parseProxyLine(line)
    if (proxy) newProxies.push(proxy)
  }
  
  if (newProxies.length === 0) {
    ElMessage.warning('没有有效的代理数据')
    return
  }
  
  try {
    await ElMessageBox.confirm(`确定导入 ${newProxies.length} 个代理？（将覆盖现有数据）`, '确认')
    const res = await proxyApi.save(newProxies)
    if (res.code === 0) {
      ElMessage.success(res.message)
      batchInput.value = ''
      await loadProxies()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('导入失败')
    }
  }
}

async function handleAppend() {
  const lines = batchInput.value.split('\n')
  const newProxies = []
  
  for (const line of lines) {
    const proxy = parseProxyLine(line)
    if (proxy) newProxies.push(proxy)
  }
  
  if (newProxies.length === 0) {
    ElMessage.warning('没有有效的代理数据')
    return
  }
  
  // 合并现有代理
  const allProxies = [...proxies.value, ...newProxies]
  
  try {
    const res = await proxyApi.save(allProxies)
    if (res.code === 0) {
      ElMessage.success(`已追加 ${newProxies.length} 个代理`)
      batchInput.value = ''
      await loadProxies()
    }
  } catch (e) {
    ElMessage.error('追加失败')
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 12px;
}
</style>
