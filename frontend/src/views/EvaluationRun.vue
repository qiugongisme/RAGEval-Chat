<template>
  <n-layout class="page-layout">
    <n-layout-header class="page-header">
      <h2>评估运行</h2>
      <n-button type="primary" @click="showCreateModal = true">
        <template #icon><n-icon><play-outline /></n-icon></template>
        新建评估
      </n-button>
    </n-layout-header>

    <n-layout-content class="page-content">
      <!-- 筛选栏 -->
      <n-space align="center" :size="12" style="margin-bottom: 16px">
        <n-input v-model:value="filterKeyword" placeholder="搜索知识库名称..." clearable style="width: 200px">
          <template #prefix><n-icon><search-outline /></n-icon></template>
        </n-input>
        <n-select v-model:value="filterStatus" :options="statusFilterOptions" style="width: 120px" />
<!--        <n-date-picker v-model:value="filterDateRange" type="daterange" clearable style="width: 240px" />-->
      </n-space>

      <n-spin :show="loading">
        <n-empty v-if="!loading && evaluations.length === 0" description="暂无评估记录">
          <template #extra>
            <n-button type="primary" @click="showCreateModal = true">新建评估</n-button>
          </template>
        </n-empty>

        <n-data-table
          v-else
          :columns="columns"
          :data="filteredEvaluations"
          :pagination="pagination"
          :bordered="true"
          :single-line="false"
          size="small"
        />
      </n-spin>
    </n-layout-content>

    <!-- 新建评估弹窗 -->
    <n-modal v-model:show="showCreateModal" title="新建评估" preset="card" style="width: 520px" :mask-closable="false">
      <n-form :model="form" label-placement="left" label-width="100px">
        <n-form-item label="知识库" required>
          <n-select
            v-model:value="form.kb_id"
            :options="kbOptions"
            placeholder="选择知识库"
            filterable
          />
        </n-form-item>
        <n-form-item label="测试集" required>
          <n-select
            v-model:value="form.test_set_id"
            :options="tsOptions"
            placeholder="选择测试集"
            filterable
          />
        </n-form-item>
        <n-form-item label="检索策略">
          <n-radio-group v-model:value="form.strategy">
            <n-radio-button value="dense">稠密检索</n-radio-button>
            <n-radio-button value="hybrid" :disabled="!hybridSupported">混合检索</n-radio-button>
          </n-radio-group>
          <template v-if="form.kb_id && !hybridSupported" #feedback>
            <span style="font-size: 12px; color: #999">
              当前知识库使用 <n-tag size="tiny">{{ selectedKb?.embedding_model }}</n-tag> 嵌入模型，未启用混合检索，仅支持稠密检索
            </span>
          </template>
        </n-form-item>
        <n-form-item>
          <template #label>
            Top-K
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <n-icon size="16" style="margin-left: 4px; cursor: help; vertical-align: middle">
                  <information-circle-outline />
                </n-icon>
              </template>
              检索返回的最相似文档数量，K 值越大召回率越高但噪音也越多
            </n-tooltip>
          </template>
          <n-input-number v-model:value="form.top_k" :min="1" :max="20" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button @click="showCreateModal = false">取消</n-button>
          <n-button type="primary" :loading="creating" @click="handleCreate">开始评估</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 查看弹窗 -->
    <n-modal v-model:show="showDetailModal" title="评估详情" preset="card" style="width: 540px" :mask-closable="true">
      <n-spin v-if="detailLoading" />
      <template v-if="detailEval && !detailLoading">
        <n-space vertical :size="12">
          <n-descriptions :column="2" bordered size="small">
            <n-descriptions-item label="知识库">{{ detailEval.kb_name }}</n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag v-if="detailEval.status === 'running'" type="info" size="small">运行中</n-tag>
              <n-tag v-else-if="detailEval.status === 'done'" type="success" size="small">完成</n-tag>
              <n-tag v-else-if="detailEval.status === 'failed'" type="error" size="small">失败</n-tag>
              <n-tag v-else size="small">{{ detailEval.status }}</n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="测试集">{{ detailEval.test_set_name }}</n-descriptions-item>
            <n-descriptions-item label="策略">{{ strategyLabel(detailEval.strategy) }}</n-descriptions-item>
            <n-descriptions-item label="Top-K">{{ detailEval.top_k }}</n-descriptions-item>
            <n-descriptions-item label="开始时间">{{ formatDate(detailEval.created_at) }}</n-descriptions-item>
            <n-descriptions-item label="结束时间">{{ detailEval.finished_at ? formatDate(detailEval.finished_at) : '-' }}</n-descriptions-item>
          </n-descriptions>

          <template v-if="detailEval.status === 'done'">
            <n-divider style="margin: 4px 0">评估结果</n-divider>
            <n-descriptions :column="3" bordered size="small">
              <n-descriptions-item label="召回率">{{ (detailEval.metrics.recall * 100).toFixed(1) }}%</n-descriptions-item>
              <n-descriptions-item label="MRR">{{ detailEval.metrics.mrr.toFixed(4) }}</n-descriptions-item>
              <n-descriptions-item label="命中">{{ detailEval.metrics.hit_count }}/{{ detailEval.metrics.total }}</n-descriptions-item>
            </n-descriptions>
          </template>

          <template v-if="detailEval.status === 'failed'">
            <n-divider style="margin: 4px 0">错误信息</n-divider>
            <pre style="max-height: 250px; overflow: auto; font-size: 12px; background: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px; padding: 12px; white-space: pre-wrap; word-break: break-all; margin: 0">{{ detailEval.error_message || '无' }}</pre>
          </template>
        </n-space>
      </template>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDetailModal = false">关闭</n-button>
          <n-button v-if="detailEval?.status === 'done'" type="primary" @click="showDetailModal = false; router.push(`/evaluations/${detailEval?.id}`)">查看报告</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 评估进度遮罩 -->
    <div v-if="overlayEval" class="progress-overlay">
      <n-card style="max-width: 420px; text-align: center">
        <!-- 运行中 -->
        <template v-if="overlayEval.status === 'running'">
          <n-spin size="large" />
          <h3 style="margin: 16px 0 8px">评估运行中</h3>
          <p style="color: #999; font-size: 13px; margin-bottom: 4px">
            {{ overlayEval.kb_name }} &times; {{ overlayEval.test_set_name }}
          </p>
          <n-progress
            type="line"
            :percentage="overlayEval.progress_total ? Math.round(overlayEval.progress_current / overlayEval.progress_total * 100) : 0"
            :height="16"
            style="margin: 12px 0"
          />
          <p style="color: #666; font-size: 14px">
            正在检索 {{ overlayEval.progress_current || 0 }}/{{ overlayEval.progress_total || 0 }}...
          </p>
          <n-button style="margin-top: 12px" size="small" @click="dismissOverlay">后台运行</n-button>
        </template>

        <!-- 完成 -->
        <template v-else-if="overlayEval.status === 'done'">
          <div style="font-size: 48px; color: #18a058">&#x2713;</div>
          <h3 style="margin: 12px 0 8px">评估完成</h3>
          <p style="color: #666; font-size: 14px">
            召回率 <strong>{{ (overlayEval.metrics.recall * 100).toFixed(1) }}%</strong>
            ({{ overlayEval.metrics.hit_count }}/{{ overlayEval.metrics.total }})
          </p>
          <p style="color: #999; font-size: 13px">MRR {{ overlayEval.metrics.mrr.toFixed(4) }}</p>
          <n-space justify="center" style="margin-top: 16px">
            <n-button type="primary" @click="viewAndDismiss(overlayEval.id)">查看报告</n-button>
            <n-button @click="dismissOverlay">关闭</n-button>
          </n-space>
        </template>

        <!-- 失败 -->
        <template v-else-if="overlayEval.status === 'failed'">
          <div style="font-size: 48px; color: #d03050">&#x2717;</div>
          <h3 style="margin: 12px 0 8px">评估失败</h3>
          <p style="color: #d03050; font-size: 13px">{{ overlayEval.error_message || '未知错误' }}</p>
          <n-space justify="center" style="margin-top: 16px">
            <n-button @click="dismissOverlay">关闭</n-button>
          </n-space>
        </template>
      </n-card>
    </div>
  </n-layout>
</template>

<script setup>
import { ref, reactive, computed, watch, h, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, NPopconfirm, NTag, NButton, NSpace } from 'naive-ui'
import { PlayOutline, InformationCircleOutline, SearchOutline } from '@vicons/ionicons5'
import {
  getEvaluations, getEvaluation, createEvaluation, deleteEvaluation,
  getKnowledgeBases, getTestSets,
} from '../api/index.js'

const router = useRouter()
const message = useMessage()

const loading = ref(false)
const evaluations = ref([])
const showCreateModal = ref(false)
const creating = ref(false)

const knowledgeBases = ref([])
const testSets = ref([])

// 进度遮罩：跟踪当前关注的评估
const currentEvalId = ref(null)

// 查看弹窗
const showDetailModal = ref(false)
const detailEval = ref(null)
const detailLoading = ref(false)

// 筛选
const filterKeyword = ref('')
const filterStatus = ref('all')
const filterDateRange = ref(null)

const statusFilterOptions = [
  { label: '全部状态', value: 'all' },
  // { label: '运行中', value: 'running' },
  { label: '完成', value: 'done' },
  { label: '失败', value: 'failed' },
]

const pagination = reactive({
  pageSize: 15,
})

const overlayEval = computed(() => {
  if (!currentEvalId.value) return null
  return evaluations.value.find(e => e.id === currentEvalId.value) || null
})

const form = ref({
  kb_id: null,
  test_set_id: null,
  strategy: 'dense',
  top_k: 3,
})

const kbOptions = computed(() =>
  knowledgeBases.value.map(kb => ({
    label: kb.name,
    value: kb.id,
  }))
)

const selectedKb = computed(() =>
  knowledgeBases.value.find(kb => kb.id === form.value.kb_id) || null
)

const hybridSupported = computed(() =>
  selectedKb.value?.hybrid_search === true && selectedKb.value?.embedding_model === 'BAAI/bge-m3'
)

watch(() => form.value.kb_id, () => {
  if (form.value.strategy === 'hybrid' && !hybridSupported.value) {
    form.value.strategy = 'dense'
  }
})

const tsOptions = computed(() =>
  testSets.value.map(ts => ({
    label: `${ts.name} (${ts.count} 题)`,
    value: ts.id,
  }))
)

const filteredEvaluations = computed(() => {
  let list = evaluations.value
  if (filterKeyword.value) {
    const kw = filterKeyword.value.toLowerCase()
    list = list.filter(e => e.kb_name.toLowerCase().includes(kw))
  }
  if (filterStatus.value !== 'all') {
    list = list.filter(e => e.status === filterStatus.value)
  }
  if (filterDateRange.value && filterDateRange.value.length === 2) {
    const [start, end] = filterDateRange.value
    const startMs = new Date(start).getTime()
    const endMs = new Date(end).getTime() + 86400000
    list = list.filter(e => {
      const d = new Date(e.created_at).getTime()
      return d >= startMs && d < endMs
    })
  }
  return list
})

const columns = [
  {
    title: '知识库', key: 'kb_name', width: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '测试集', key: 'test_set_name', width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '策略', key: 'strategy', width: 70,
    render(row) { return strategyLabel(row.strategy) },
  },
  { title: 'Top-K', key: 'top_k', width: 60 },
  {
    title: '状态', key: 'status', width: 80,
    render(row) {
      const map = { running: { type: 'info', text: '运行中' }, done: { type: 'success', text: '完成' }, failed: { type: 'error', text: '失败' } }
      const s = map[row.status] || { type: 'default', text: row.status }
      return h(NTag, { type: s.type, round: true, size: 'small' }, { default: () => s.text })
    },
  },
  {
    title: '召回率', key: 'recall', width: 100,
    render(row) {
      if (row.status !== 'done') return '-'
      return `${(row.metrics.recall * 100).toFixed(1)}% (${row.metrics.hit_count}/${row.metrics.total})`
    },
  },
  {
    title: 'MRR', key: 'mrr', width: 70,
    render(row) { return row.status === 'done' ? row.metrics.mrr.toFixed(4) : '-' },
  },
  {
    title: '开始时间', key: 'created_at', width: 150,
    render(row) { return formatDate(row.created_at) },
  },
  {
    title: '结束时间', key: 'finished_at', width: 150,
    render(row) { return row.finished_at ? formatDate(row.finished_at) : '-' },
  },
  {
    title: '操作', key: 'actions', width: 170,
    render(row) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'small', onClick: () => openDetailModal(row.id) }, { default: () => '查看' }),
          row.status === 'done' ? h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => viewReport(row.id) }, { default: () => '报告' }) : null,
          h(NPopconfirm, {
            positiveText: '确认', negativeText: '取消',
            onPositiveClick: () => handleDelete(row.id),
          }, {
            default: () => '确定删除此评估记录吗？',
            trigger: () => h(NButton, { size: 'small', type: 'error', ghost: true }, { default: () => '删除' }),
          }),
        ],
      })
    },
  },
]

// NaN/undefined 安全
function safeNumber(v) { return (v == null || Number.isNaN(v)) ? 0 : v }

let pollTimer = null

async function loadData() {
  try {
    const [evals, kbs, ts] = await Promise.all([
      getEvaluations(),
      getKnowledgeBases(),
      getTestSets(),
    ])
    evaluations.value = evals
    knowledgeBases.value = kbs
    testSets.value = ts
  } catch (e) {
    message.error('加载数据失败: ' + e.message)
  }
}

async function loadEvals() {
  try {
    evaluations.value = await getEvaluations()
  } catch {
    // 轮询静默失败
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    loadEvals().then(() => {
      // 检查是否还有运行中的任务，没有则停止轮询
      if (!evaluations.value.some(e => e.status === 'running')) {
        stopPolling()
      }
    })
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function handleCreate() {
  if (!form.value.kb_id) {
    message.warning('请选择知识库')
    return
  }
  if (!form.value.test_set_id) {
    message.warning('请选择测试集')
    return
  }

  creating.value = true
  try {
    const result = await createEvaluation(form.value)
    // 立刻关闭弹窗、解除按钮 loading
    showCreateModal.value = false
    creating.value = false

    // 拉一次列表获取初始状态
    await loadEvals()

    // 显示进度遮罩
    const running = evaluations.value.find(e => e.id === result.id)
    if (running) {
      currentEvalId.value = result.id
    }
    message.success('评估任务已提交')
    startPolling()
  } catch (e) {
    message.error('提交失败: ' + e.message)
    creating.value = false
  }
}

function dismissOverlay() {
  currentEvalId.value = null
}

function viewAndDismiss(id) {
  currentEvalId.value = null
  router.push(`/evaluations/${id}`)
}

async function handleDelete(id) {
  try {
    await deleteEvaluation(id)
    message.success('删除成功')
    await loadEvals()
  } catch (e) {
    message.error('删除失败: ' + e.message)
  }
}

async function openDetailModal(id) {
  detailLoading.value = true
  showDetailModal.value = true
  detailEval.value = null
  try {
    detailEval.value = await getEvaluation(id)
  } catch (e) {
    message.error('加载详情失败: ' + e.message)
    showDetailModal.value = false
  } finally {
    detailLoading.value = false
  }
}

function viewReport(id) {
  router.push(`/evaluations/${id}`)
}

function strategyLabel(s) {
  const map = { hybrid: '混合检索', dense: '稠密检索' }
  return map[s] || s
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  await loadData()
  loading.value = false
  startPolling()
})

onUnmounted(stopPolling)
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
.page-header h2 {
  margin: 0;
  font-size: 20px;
}
.page-content {
  background: #fff;
  padding: 16px;
  border-radius: 4px;
}
.progress-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
</style>
