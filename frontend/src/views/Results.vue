<template>
  <div class="results-page">
    <!-- 统计信息 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <el-icon :size="40" color="#1890ff"><Document /></el-icon>
            <div>
              <div class="stat-value">{{ stats.email_count }}</div>
              <div class="stat-label">邮箱账号</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <el-icon :size="40" color="#52c41a"><Key /></el-icon>
            <div>
              <div class="stat-value">{{ stats.token_count }}</div>
              <div class="stat-label">Token</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="stat-item">
            <el-icon :size="40" color="#722ed1"><Download /></el-icon>
            <div>
              <div class="stat-value">导出</div>
              <div class="stat-label">
                <el-button type="primary" size="small" @click="handleExport('email')">邮箱</el-button>
                <el-button type="success" size="small" @click="handleExport('token')">Token</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 结果列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <el-radio-group v-model="resultType" @change="loadResults">
              <el-radio-button value="email">邮箱账号</el-radio-button>
              <el-radio-button value="token">Token</el-radio-button>
            </el-radio-group>
          </div>
          <div class="header-actions">
            <el-input
              v-model="searchText"
              placeholder="搜索..."
              clearable
              style="width: 200px; margin-right: 12px"
              @keyup.enter="loadResults"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="danger" plain @click="handleClear">清空</el-button>
          </div>
        </div>
      </template>

      <el-table :data="results" style="width: 100%" max-height="500">
        <el-table-column type="index" width="60" />
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleCopy(row.content)">
              复制
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 20px; justify-content: flex-end"
        @size-change="loadResults"
        @current-change="loadResults"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { resultApi } from '@/api'

const resultType = ref('email')
const searchText = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const results = ref([])
const stats = ref({ email_count: 0, token_count: 0 })

onMounted(() => {
  loadResults()
  loadStats()
})

async function loadResults() {
  try {
    const res = await resultApi.get({
      type: resultType.value,
      page: currentPage.value,
      size: pageSize.value,
      search: searchText.value,
    })
    if (res.code === 0) {
      total.value = res.data.total
      results.value = res.data.items.map((item) => ({ content: item }))
    }
  } catch (e) {
    console.error('Failed to load results:', e)
  }
}

async function loadStats() {
  try {
    const res = await resultApi.getStats()
    if (res.code === 0) {
      stats.value = res.data
    }
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

async function handleExport(type) {
  try {
    const res = await resultApi.export({ type, format: 'txt' })
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.download = `${type}_results.txt`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败')
  }
}

async function handleClear() {
  try {
    await ElMessageBox.confirm(
      `确定要清空${resultType.value === 'email' ? '邮箱' : 'Token'}数据吗？`,
      '确认',
      { type: 'warning' }
    )
    const res = await resultApi.clear(resultType.value)
    if (res.code === 0) {
      ElMessage.success('已清空')
      loadResults()
      loadStats()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

function handleCopy(content) {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}
</script>

<style scoped>
.stat-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}
</style>
