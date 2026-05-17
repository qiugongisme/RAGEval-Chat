<template>
  <div style="padding: 24px">
    <n-h2>知识库管理</n-h2>
    <n-space vertical :size="16">
      <n-space justify="end">
        <n-button type="primary" @click="handleCreate">创建知识库</n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="knowledgeBases"
        :loading="loading"
        :pagination="{ pageSize: 10 }"
        :bordered="true"
        size="medium"
      />
    </n-space>

    <!-- 创建知识库弹窗 -->
    <n-modal v-model:show="showModal" title="创建知识库" preset="card" style="width: 500px" :mask-closable="false">
      <n-form ref="formRef" :model="formData" :rules="rules" label-placement="left" label-width="auto">
        <n-form-item label="名称" path="name">
          <n-input v-model:value="formData.name" placeholder="例如: 金融法规库" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="formData.description" type="textarea" placeholder="知识库描述（可选）" />
        </n-form-item>
        <n-form-item label="嵌入模型">
          <n-select v-model:value="formData.embedding_model" :options="embeddingOptions" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleSubmit">创建</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 提示词设置弹窗 -->
    <n-modal v-model:show="showPromptModal" title="设置提示词" preset="card" style="width: 620px">
      <template #header>
        <span style="font-size: 16px; font-weight: 600;">设置提示词 — 【{{ currentPromptKb?.name }}】</span>
      </template>
      <n-space vertical :size="12">
        <div style="color: #999; font-size: 13px">
          自定义提示词模板，可用 <code>&#123;retrieve_context&#125;</code> 和 <code>&#123;question&#125;</code> 占位符。<br/>留空则使用 AI 生成默认，点击「保存」才生效。
        </div>
        <n-input
          v-model:value="promptText"
          type="textarea"
          :autosize="{ minRows: 8, maxRows: 20 }"
          :placeholder="generatingPrompt ? 'AI 正在生成...' : '输入自定义提示词，或点击「AI 生成默认」'"
          :disabled="generatingPrompt"
        />
      </n-space>
      <template #footer>
        <n-space justify="space-between">
          <n-button @click="handleGeneratePrompt" :loading="generatingPrompt">AI 生成默认</n-button>
          <n-space>
            <n-button @click="showPromptModal = false">取消</n-button>
            <n-button type="primary" @click="handleSavePrompt">保存</n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>

    <!-- 查看详情弹窗 -->
    <n-modal v-model:show="showDetailModal" title="知识库详情" preset="card" style="width: 620px" :mask-closable="true">
      <template v-if="detailKb">
        <n-tabs v-model:value="detailTab" type="line" @update:value="handleDetailTabChange">
          <!-- Tab 1: 基础信息 -->
          <n-tab-pane name="info" tab="基础信息">
            <n-space vertical :size="12">
              <n-descriptions :column="2" bordered size="small">
                <n-descriptions-item label="名称">{{ detailKb.name }}</n-descriptions-item>
                <n-descriptions-item label="状态">
                  <n-tag :type="statusMap[detailKb.status]?.type || 'default'" size="small">
                    {{ statusMap[detailKb.status]?.text || detailKb.status }}
                  </n-tag>
                </n-descriptions-item>
                <n-descriptions-item label="嵌入模型">{{ detailKb.embedding_model }}</n-descriptions-item>
                <n-descriptions-item label="混合检索">{{ detailKb.hybrid_search ? '启用' : '未启用' }}</n-descriptions-item>
                <n-descriptions-item label="描述" :span="2">{{ detailKb.description || '（无）' }}</n-descriptions-item>
                <n-descriptions-item label="文档数">{{ detailKb.doc_count || detailKb.file_count || 0 }}</n-descriptions-item>
                <n-descriptions-item label="向量块数">{{ detailKb.chunk_count || 0 }}</n-descriptions-item>
                <n-descriptions-item label="创建时间" :span="2">{{ formatDate(detailKb.created_at) }}</n-descriptions-item>
                <n-descriptions-item v-if="detailKb.updated_at" label="更新时间" :span="2">{{ formatDate(detailKb.updated_at) }}</n-descriptions-item>
              </n-descriptions>

              <n-divider style="margin: 8px 0">切分策略</n-divider>
              <n-descriptions :column="2" bordered size="small">
                <n-descriptions-item label="分隔符">{{ detailKb.split_config?.separators?.join(', ') || '使用默认' }}</n-descriptions-item>
                <n-descriptions-item label="分块大小">{{ detailKb.split_config?.chunk_size }}</n-descriptions-item>
                <n-descriptions-item label="重叠大小">{{ detailKb.split_config?.chunk_overlap }}</n-descriptions-item>
              </n-descriptions>

              <n-divider style="margin: 8px 0">索引配置</n-divider>
              <n-descriptions :column="2" bordered size="small">
                <template v-if="detailKb.index_config">
                  <n-descriptions-item label="密集索引类型">{{ detailKb.index_config.dense_index_type }}</n-descriptions-item>
                  <n-descriptions-item label="度量标准">{{ detailKb.index_config.dense_metric }}</n-descriptions-item>
                  <template v-if="detailKb.index_config.dense_index_type === 'HNSW'">
                    <n-descriptions-item label="M">{{ detailKb.index_config.M }}</n-descriptions-item>
                    <n-descriptions-item label="efConstruction">{{ detailKb.index_config.efConstruction }}</n-descriptions-item>
                  </template>
                  <template v-else>
                    <n-descriptions-item>
                      <template #label>
                        nlist
                        <n-tooltip trigger="hover">
                          <template #trigger>
                            <span style="color: #999; cursor: help; font-size: 13px"> ⓘ</span>
                          </template>
                          聚类数目。向量数据聚类为 nlist 个簇，值越大精度越高但建索引越慢。推荐：&lt;10万→100~1000，10万~100万→500~5000
                        </n-tooltip>
                      </template>
                      {{ detailKb.index_config.nlist }}
                    </n-descriptions-item>
                  </template>
                  <n-descriptions-item>
                    <template #label>
                      nprobe
                      <n-tooltip trigger="hover">
                        <template #trigger>
                          <span style="color: #999; cursor: help; font-size: 13px"> ⓘ</span>
                        </template>
                        查询时搜索的聚类数目。值越大召回率越高但速度越慢，通常设为 nlist 的 1/10 到 1/5
                      </n-tooltip>
                    </template>
                    {{ detailKb.index_config.nprobe }}
                  </n-descriptions-item>
                  <template v-if="detailKb.hybrid_search">
                    <n-descriptions-item label="稀疏索引类型">{{ detailKb.index_config.sparse_index_type }}</n-descriptions-item>
                    <n-descriptions-item label="稀疏度量">{{ detailKb.index_config.sparse_metric }}</n-descriptions-item>
                  </template>
                </template>
              </n-descriptions>
            </n-space>
          </n-tab-pane>

          <!-- Tab 2: 已上传文档 -->
          <n-tab-pane name="files" tab="已上传文档">
            <n-spin v-if="filesLoading" style="min-height: 100px; display: flex; align-items: center; justify-content: center" />
            <template v-else>
              <n-empty v-if="!detailFiles || detailFiles.length === 0" description="暂无文档" style="min-height: 150px; display: flex; align-items: center; justify-content: center" />
              <n-data-table
                v-else
                :columns="detailFileColumns"
                :data="detailFiles"
                :bordered="true"
                size="small"
                :pagination="{ pageSize: 10 }"
                :scroll-x="400"
                style="margin-top: 8px"
              />
            </template>
          </n-tab-pane>
        </n-tabs>
      </template>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDetailModal = false">关闭</n-button>
          <n-button type="primary" ghost @click="router.push(`/knowledge-bases/${detailKb?.id}`); showDetailModal = false">前往管理</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NPopconfirm, NSpace, NTag, NModal, NInput } from 'naive-ui'
import { getKnowledgeBases, getKnowledgeBase, createKnowledgeBase, updateKnowledgeBase, deleteKnowledgeBase, generateKBPrompt } from '../api/index.js'

const router = useRouter()
const knowledgeBases = ref([])
const loading = ref(false)
const showModal = ref(false)
const submitting = ref(false)
const formRef = ref(null)

// 查看详情
const showDetailModal = ref(false)
const detailKb = ref(null)
const detailTab = ref('info')
const detailFiles = ref([])
const filesLoading = ref(false)

const embeddingOptions = [
  { label: 'BAAI/bge-base-zh-v1.5', value: 'BAAI/bge-base-zh-v1.5' },
  { label: 'BAAI/bge-large-zh-v1.5', value: 'BAAI/bge-large-zh-v1.5' },
  { label: 'BAAI/bge-m3', value: 'BAAI/bge-m3' },
]

const statusMap = {
  empty: { type: 'default', text: '待处理' },
  processing: { type: 'info', text: '构建中' },
  ready: { type: 'success', text: '已完成' },
  failed: { type: 'error', text: '构建失败' },
}

const columns = [
  {
    title: '名称', key: 'name', width: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态', key: 'status', width: 90,
    render(row) {
      const s = statusMap[row.status] || { type: 'default', text: row.status }
      return h(NTag, { type: s.type, size: 'small' }, { default: () => s.text })
    },
  },
  {
    title: '嵌入模型', key: 'embedding_model', width: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: '混合检索', key: 'hybrid_search', width: 90,
    render(row) {
      return row.hybrid_search ? '启用' : '未启用'
    },
  },
  {
    title: '文档数', key: 'file_count', width: 70,
  },
  { title: '向量数', key: 'chunk_count', width: 70 },
  {
    title: '创建时间', key: 'created_at', width: 170,
    render(row) {
      if (!row.created_at) return ''
      const d = new Date(row.created_at)
      const pad = (n) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    },
  },
  {
    title: '操作', key: 'actions', width: 280,
    render(row) {
      return h(NSpace, null, {
        default: () => [
          h(NButton, {
            size: 'small',
            onClick: () => openDetailModal(row),
          }, { default: () => '查看' }),
          h(NButton, {
            size: 'small', type: 'primary', ghost: true,
            onClick: () => router.push(`/knowledge-bases/${row.id}`),
          }, { default: () => '管理' }),
          h(NButton, {
            size: 'small',
            onClick: () => openPromptModal(row),
          }, { default: () => '设置提示词' }),
          h(NPopconfirm, {
            onPositiveClick: () => handleDelete(row.id),
            positiveText: '确认',
            negativeText: '取消',
          }, {
            default: () => '确定删除此知识库吗？（含向量数据和文件）',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          }),
        ],
      })
    },
  },
]

const defaultForm = () => ({
  name: '',
  description: '',
  embedding_model: 'BAAI/bge-base-zh-v1.5',
})

const formData = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入知识库名称', trigger: 'blur' },
}

async function fetchKnowledgeBases() {
  loading.value = true
  try {
    knowledgeBases.value = await getKnowledgeBases()
  } catch (e) {
    window.$message?.error(e.message)
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  formData.value = defaultForm()
  showModal.value = true
}

async function handleSubmit() {
  submitting.value = true
  try {
    await createKnowledgeBase(formData.value)
    window.$message?.success('知识库已创建，可在详情页上传文档并配置切分与索引')
    showModal.value = false
    await fetchKnowledgeBases()
  } catch (e) {
    window.$message?.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await deleteKnowledgeBase(id)
    window.$message?.success('知识库已删除')
    await fetchKnowledgeBases()
  } catch (e) {
    window.$message?.error(e.message)
  }
}

// ─── 查看详情 ───

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const detailFileColumns = [
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true }, width: 250 },
  { title: '格式', key: 'type', width: 70 },
  {
    title: '大小', key: 'size', width: 100,
    render(row) {
      const kb = row.size / 1024
      return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
    },
  },
]

function openDetailModal(row) {
  detailKb.value = row
  detailTab.value = 'info'
  detailFiles.value = []
  showDetailModal.value = true
}

async function handleDetailTabChange(tab) {
  if (tab !== 'files') return
  if (detailFiles.value.length > 0) return  // 已加载过
  filesLoading.value = true
  try {
    const data = await getKnowledgeBase(detailKb.value.id)
    detailFiles.value = data.files || []
  } catch (e) {
    window.$message?.error('加载文件列表失败: ' + e.message)
  } finally {
    filesLoading.value = false
  }
}

// ─── 提示词设置 ───

const showPromptModal = ref(false)
const currentPromptKb = ref(null)
const promptText = ref('')
const generatingPrompt = ref(false)

function openPromptModal(row) {
  currentPromptKb.value = row
  promptText.value = row.prompt_template || ''
  showPromptModal.value = true
}

async function handleGeneratePrompt() {
  if (!currentPromptKb.value) return
  generatingPrompt.value = true
  try {
    const result = await generateKBPrompt(currentPromptKb.value.id)
    promptText.value = result.prompt_template
  } catch (e) {
    window.$message?.error('生成提示词失败: ' + e.message)
  } finally {
    generatingPrompt.value = false
  }
}

async function handleSavePrompt() {
  if (!currentPromptKb.value) return

  // 留空时自动 AI 生成
  if (!promptText.value.trim()) {
    generatingPrompt.value = true
    try {
      const result = await generateKBPrompt(currentPromptKb.value.id)
      promptText.value = result.prompt_template
    } catch (e) {
      window.$message?.error('AI 生成失败: ' + e.message)
      generatingPrompt.value = false
      return
    }
    generatingPrompt.value = false
  }

  try {
    await updateKnowledgeBase(currentPromptKb.value.id, { prompt_template: promptText.value })
    // 更新列表中的本地数据
    const target = knowledgeBases.value.find(k => k.id === currentPromptKb.value.id)
    if (target) target.prompt_template = promptText.value
    window.$message?.success('提示词已保存')
    showPromptModal.value = false
  } catch (e) {
    window.$message?.error(e.message)
  }
}

onMounted(fetchKnowledgeBases)
</script>
