<template>
  <n-layout class="page-layout">
    <n-layout-header class="page-header">
      <div class="header-left">
        <n-button @click="goBack" size="small" style="margin-right: 12px">
          <template #icon><n-icon><arrow-back-outline /></n-icon></template>
          返回
        </n-button>
        <h2>评估报告</h2>
      </div>
<!--      <n-space v-if="report">
        <n-button
          v-if="compareId"
          size="small"
          @click="showCompare = !showCompare"
        >
          {{ showCompare ? '隐藏对比' : '对比模式' }}
        </n-button>
        <n-select
          v-model:value="compareId"
          :options="compareOptions"
          placeholder="对比历史评估..."
          style="width: 200px"
          clearable
        />
      </n-space>-->
    </n-layout-header>

    <n-layout-content class="page-content">
      <n-spin :show="loading">
        <template v-if="report">
          <!-- 基本信息 -->
          <n-card title="基本信息" size="small" class="mb-16">
            <n-descriptions :column="3" bordered size="small">
              <n-descriptions-item label="知识库">{{ report.kb_name }}</n-descriptions-item>
              <n-descriptions-item label="测试集">{{ report.test_set_name }}</n-descriptions-item>
              <n-descriptions-item label="检索策略">{{ strategyLabel(report.strategy) }}</n-descriptions-item>
              <n-descriptions-item>
                <template #label>
                  Top-K
                  <n-tooltip trigger="hover" placement="right">
                    <template #trigger>
                      <n-icon size="14" style="margin-left: 2px; cursor: help; vertical-align: middle">
                        <information-circle-outline />
                      </n-icon>
                    </template>
                    检索返回的最相似文档数量
                  </n-tooltip>
                </template>
                {{ report.top_k }}
              </n-descriptions-item>
              <n-descriptions-item label="状态">
                <n-tag v-if="report.status === 'done'" type="success">完成</n-tag>
                <n-tag v-else-if="report.status === 'failed'" type="error">失败</n-tag>
                <n-tag v-else type="info">{{ report.status }}</n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="时间">{{ formatDate(report.created_at) }}</n-descriptions-item>
            </n-descriptions>
          </n-card>

          <!-- 指标卡片 -->
          <n-card title="评估指标" size="small" class="mb-16">
            <div class="metrics-row" v-if="report.status === 'done'">
              <div class="metric-card">
                <div class="metric-value" :style="{ color: recallColor }">
                  {{ (report.metrics.recall * 100).toFixed(1) }}%
                </div>
                <div class="metric-label">
                  召回率 Recall@{{ report.top_k }}
                  <n-tooltip trigger="hover" placement="bottom">
                    <template #trigger>
                      <n-icon size="14" style="margin-left: 2px; cursor: help; vertical-align: middle">
                        <information-circle-outline />
                      </n-icon>
                    </template>
                    命中的问题数占总问题数的比例
                  </n-tooltip>
                </div>
                <div class="metric-bar">
                  <div class="metric-bar-fill" :style="{ width: (report.metrics.recall * 100).toFixed(1) + '%' }"></div>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-value">{{ report.metrics.mrr.toFixed(4) }}</div>
                <div class="metric-label">
                  MRR
                  <n-tooltip trigger="hover" placement="bottom">
                    <template #trigger>
                      <n-icon size="14" style="margin-left: 2px; cursor: help; vertical-align: middle">
                        <information-circle-outline />
                      </n-icon>
                    </template>
                    平均倒数排名，衡量命中的排序质量，值越大表示命中的位置越靠前
                  </n-tooltip>
                </div>
              </div>
              <div class="metric-card">
                <div class="metric-value">{{ report.metrics.hit_count }} / {{ report.metrics.total }}</div>
                <div class="metric-label">命中数 / 总数</div>
              </div>
            </div>
            <n-empty v-else-if="report.status === 'failed'" description="评估执行失败">
              {{ report.error_message }}
            </n-empty>
            <n-spin v-else description="评估正在运行中..." />
          </n-card>

          <!-- 详情表格 -->
          <n-card size="small" class="mb-16">
            <template #header>
              <n-space align="center" justify="space-between">
                <span style="font-weight: 600">逐题详情</span>
                <n-button size="small" @click="exportCSV" :disabled="filteredDetails.length === 0">
                  <template #icon><n-icon><download-outline /></n-icon></template>
                  导出 CSV
                </n-button>
              </n-space>
            </template>
            <n-space vertical>
              <n-space>
                <n-tag :type="filterHit === null ? 'primary' : 'default'" @click="filterHit = null" style="cursor:pointer">全部 ({{ report.details.length }})</n-tag>
                <n-tag type="success" @click="filterHit = true" style="cursor:pointer">已召回 ({{ report.metrics.hit_count }})</n-tag>
                <n-tag type="error" @click="filterHit = false" style="cursor:pointer">未召回 ({{ report.metrics.total - report.metrics.hit_count }})</n-tag>
              </n-space>

              <n-input v-model:value="searchQuery" placeholder="搜索问题..." clearable />

              <div class="table-wrap">
                <n-table :bordered="true" :single-line="false" size="small">
                  <colgroup>
                    <col style="width: 44px" />
                    <col />
                    <col style="width: 120px" />
                    <col style="width: 80px" />
                    <col style="width: 56px" />
                    <col style="width: 64px" />
                    <col style="width: 30%" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th style="width: 44px">#</th>
                      <th>问题</th>
                      <th style="width: 120px">期望来源</th>
                      <th style="width: 80px">结果</th>
                      <th style="width: 56px">排名</th>
                      <th style="width: 64px">分数</th>
                      <th style="width: 30%">匹配文本</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(item, idx) in filteredDetails" :key="idx">
                      <td>{{ idx + 1 }}</td>
                      <td>{{ item.question }}</td>
                      <td>{{ item.expected_source }}</td>
                      <td>
                        <n-tag v-if="item.hit" type="success" size="small">已召回</n-tag>
                        <n-tag v-else type="error" size="small">未召回</n-tag>
                      </td>
                      <td>{{ item.rank || '-' }}</td>
                      <td>{{ item.score || '-' }}</td>
                      <td>{{ item.matched_chunk || '-' }}</td>
                    </tr>
                    <tr v-if="filteredDetails.length === 0">
                      <td colspan="7" style="text-align:center">无匹配结果</td>
                    </tr>
                  </tbody>
                </n-table>
              </div>
            </n-space>
          </n-card>
        </template>
      </n-spin>
    </n-layout-content>
  </n-layout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { ArrowBackOutline, InformationCircleOutline, DownloadOutline } from '@vicons/ionicons5'
import { getEvaluation, getEvaluations, compareEvaluations } from '../api/index.js'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const loading = ref(false)
const report = ref(null)
const searchQuery = ref('')
const filterHit = ref(null)
const compareId = ref(null)
const showCompare = ref(false)
const compareReport = ref(null)
const allEvaluations = ref([])

const compareOptions = computed(() =>
  allEvaluations.value
    .filter(e => e.id !== route.params.id && e.status === 'done')
    .map(e => ({
      label: `${e.kb_name} - ${e.strategy} (${(e.metrics.recall * 100).toFixed(1)}%)`,
      value: e.id,
    }))
)

const filteredDetails = computed(() => {
  let items = report.value?.details || []
  if (filterHit.value !== null) {
    items = items.filter(d => d.hit === filterHit.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(d => d.question.toLowerCase().includes(q))
  }
  return items
})

const recallColor = computed(() => {
  if (!report.value) return '#18a058'
  const r = report.value.metrics.recall
  if (r >= 0.8) return '#18a058'
  if (r >= 0.5) return '#d03050'
  return '#d03050'
})

async function loadReport() {
  loading.value = true
  try {
    report.value = await getEvaluation(route.params.id)
    allEvaluations.value = await getEvaluations()
  } catch (e) {
    message.error('加载报告失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// 当选择对比时加载对比报告
watch(compareId, async (newId) => {
  if (newId) {
    try {
      const result = await compareEvaluations(route.params.id, newId)
      compareReport.value = result.eval_2
      showCompare.value = true
    } catch (e) {
      message.error('加载对比数据失败: ' + e.message)
    }
  } else {
    compareReport.value = null
    showCompare.value = false
  }
})

function goBack() {
  router.push('/evaluations')
}

function strategyLabel(s) {
  const map = { hybrid: '混合检索', dense: '稠密检索' }
  return map[s] || s
}

function csvEscape(val) {
  if (val == null) return ''
  const str = String(val)
  return '"' + str.replace(/"/g, '""') + '"'
}

function exportCSV() {
  if (!report.value) return
  const rows = filteredDetails.value
  if (rows.length === 0) return

  const headers = ['序号', '问题', '期望来源', '结果', '排名', '分数', '匹配文本']
  const lines = [headers.join(',')]

  rows.forEach((item, idx) => {
    lines.push([
      idx + 1,
      csvEscape(item.question),
      csvEscape(item.expected_source),
      item.hit ? '已召回' : '未召回',
      item.rank || '-',
      item.score || '-',
      csvEscape(item.matched_chunk || ''),
    ].join(','))
  })

  const bom = '\uFEFF'
  const blob = new Blob([bom + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `评估报告_${report.value.kb_name}_${report.value.test_set_name}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(loadReport)
</script>

<style scoped>
.page-layout {
  padding: 20px;
  height: 100%;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: center;
}
.header-left h2 {
  margin: 0;
  font-size: 20px;
}
.page-content {
  background: #fff;
  padding: 16px;
  border-radius: 4px;
}
.mb-16 {
  margin-bottom: 16px;
}
.metrics-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.metric-card {
  flex: 1;
  min-width: 180px;
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
  text-align: center;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 8px;
}
.metric-label {
  font-size: 13px;
  color: #666;
}
.metric-bar {
  height: 8px;
  background: #eee;
  border-radius: 4px;
  margin-top: 12px;
  overflow: hidden;
}
.metric-bar-fill {
  height: 100%;
  background: #18a058;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.table-wrap {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.table-wrap :deep(.n-table) {
  max-height: 520px;
  overflow-y: auto;
  overflow-x: auto;
  border: none;
  margin: 0;
}

.table-wrap :deep(.n-table thead th) {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #fafafa;
  box-shadow: 0 1px 0 #e0e0e0;
}

.table-wrap :deep(.n-table td:last-child) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
