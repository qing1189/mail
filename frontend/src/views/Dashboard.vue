<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #1890ff">
              <el-icon :size="32"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ taskStore.status.total_tasks }}</div>
              <div class="stat-label">总任务</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #52c41a">
              <el-icon :size="32"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ taskStore.status.succeeded }}</div>
              <div class="stat-label">成功</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #ff4d4f">
              <el-icon :size="32"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ taskStore.status.failed }}</div>
              <div class="stat-label">失败</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #722ed1">
              <el-icon :size="32"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ taskStore.status.success_rate }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 进度和图表 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>任务进度</span>
          </template>
          <div class="progress-section">
            <el-progress
              :percentage="taskStore.progress"
              :stroke-width="24"
              :text-inside="true"
              status="success"
            />
            <div class="progress-info">
              <span>已提交: {{ taskStore.status.submitted }}</span>
              <span>剩余: {{ taskStore.status.remaining }}</span>
              <span>活跃线程: {{ taskStore.status.active_threads }}</span>
            </div>
          </div>
          <!-- 成功率图表 -->
          <div ref="chartRef" style="height: 300px; margin-top: 20px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>成功注册</span>
          </template>
          <div class="success-list">
            <div
              v-for="(email, index) in taskStore.successEmails.slice(0, 20)"
              :key="index"
              class="success-item"
            >
              <el-icon color="#52c41a"><CircleCheck /></el-icon>
              <span>{{ email }}</span>
            </div>
            <el-empty v-if="taskStore.successEmails.length === 0" description="暂无成功记录" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 日志区域 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="log-header">
          <span>实时日志</span>
          <el-button size="small" @click="taskStore.clearLogs()">清空</el-button>
        </div>
      </template>
      <div class="log-container" ref="logRef">
        <div v-for="(log, index) in taskStore.logs" :key="index" class="log-line">
          {{ log }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useTaskStore } from '@/stores/task'

const taskStore = useTaskStore()
const chartRef = ref(null)
const logRef = ref(null)
let chart = null

// 初始化图表
onMounted(() => {
  initChart()
  taskStore.fetchLogs()
  taskStore.fetchSuccessEmails()
})

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart) return
  const option = {
    tooltip: {
      trigger: 'axis',
    },
    xAxis: {
      type: 'category',
      data: ['总任务', '已提交', '成功', '失败'],
    },
    yAxis: {
      type: 'value',
    },
    series: [
      {
        type: 'bar',
        data: [
          taskStore.status.total_tasks,
          taskStore.status.submitted,
          taskStore.status.succeeded,
          taskStore.status.failed,
        ],
        itemStyle: {
          color: (params) => {
            const colors = ['#1890ff', '#faad14', '#52c41a', '#ff4d4f']
            return colors[params.dataIndex]
          },
        },
      },
    ],
  }
  chart.setOption(option)
}

// 监听状态变化更新图表
watch(
  () => taskStore.status,
  () => {
    updateChart()
  },
  { deep: true }
)

// 自动滚动日志
watch(
  () => taskStore.logs.length,
  () => {
    nextTick(() => {
      if (logRef.value) {
        logRef.value.scrollTop = logRef.value.scrollHeight
      }
    })
  }
)
</script>

<style scoped>
.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 100%;
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 4px;
}

.progress-section {
  padding: 10px 0;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  color: #666;
  font-size: 14px;
}

.success-list {
  height: 400px;
  overflow-y: auto;
}

.success-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-container {
  height: 300px;
  overflow-y: auto;
  background: #1e1e1e;
  border-radius: 4px;
  padding: 12px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
}

.log-line {
  color: #d4d4d4;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
