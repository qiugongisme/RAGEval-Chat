<template>
  <div style="padding: 24px">
    <!-- 顶部导航栏 -->
    <n-space justify="space-between" align="center" style="margin-bottom: 16px">
      <n-space align="center">
        <n-button @click="goBack" style="padding: 0 8px">← 返回</n-button>
        <n-h2 style="margin: 0; display: inline">{{ kb?.name || '知识库详情' }}</n-h2>
        <n-tag v-if="kb" :type="statusTagType" size="small">{{ statusText }}</n-tag>
      </n-space>
<!--      <n-button @click="goBack">返回列表</n-button>-->
    </n-space>

    <!-- 加载中 -->
    <n-spin v-if="!kb" />

    <template v-if="kb">
      <!-- 步骤条（向导模式下显示） -->
      <n-steps v-if="currentStep > 0" :current="currentStep" style="margin-bottom: 32px; justify-content: center">
        <n-step title="文档管理" description="上传文档" />
        <n-step title="切分设置" description="配置参数" />
        <n-step title="索引配置" description="向量索引" />
        <n-step title="提交处理" description="执行处理" />
      </n-steps>

      <!-- 失败时的错误提示 -->
      <n-alert v-if="kb.status === 'failed'" type="error" closable style="margin-bottom: 16px" @close="kb.error_message = ''">
        {{ kb.error_message || '处理失败' }}
      </n-alert>

      <!-- ===== 默认视图：文档管理首页 ===== -->
      <div v-if="currentStep === 0">
        <n-space vertical :size="16">
          <n-space justify="space-between" align="center">
            <h3 style="margin: 0">已上传文档 <span style="font-size: 14px; color: #999; font-weight: normal">(共 {{ kb.files?.length || 0 }} 个文件)</span></h3>
            <n-button type="primary" @click="startNewProcess">上传文档</n-button>
          </n-space>
          <n-data-table
            :columns="fileColumns"
            :data="kb.files"
            :loading="fileLoading"
            :pagination="{ pageSize: 10 }"
            :bordered="true"
          />
        </n-space>
      </div>

      <!-- ===== Step 1: 文档管理（上传） ===== -->
      <div v-if="currentStep === 1">
        <n-space vertical :size="16">
          <n-upload
            :default-upload="false"
            :accept="'.pdf,.docx,.doc,.pptx,.ppt,.txt,.md'"
            multiple
            :show-file-list="false"
            @change="handleTempFileChange"
          >
            <n-upload-dragger>
              <div style="padding: 32px; text-align: center; color: #999">
                <div style="font-size: 40px; margin-bottom: 8px">📄</div>
                <p>拖拽文件到此处，或点击选择文件</p>
                <p style="font-size: 12px">支持 PDF / DOCX / DOC / PPTX / PPT / TXT / MD</p>
              </div>
            </n-upload-dragger>
          </n-upload>

          <n-data-table
            v-if="tempFiles.length > 0"
            :columns="tempFileColumns"
            :data="tempFiles"
            :bordered="true"
          />
        </n-space>
      </div>

      <!-- ===== Step 2: 切分设置 ===== -->
      <div v-if="currentStep === 2">
        <n-form
          ref="splitFormRef"
          :model="splitForm"
          :rules="splitRules"
          label-placement="left"
          label-width="auto"
          style="max-width: 500px"
        >
          <n-form-item label="分隔符" path="separator">
            <n-input
              v-model:value="splitForm.separator"
              placeholder="第\\S*条"
              clearable
            />
            <template #feedback>
              支持正则表达式，多个用逗号分隔。留空则使用默认分隔符
            </template>
          </n-form-item>
          <n-form-item label="分块大小" path="chunk_size">
            <n-input-number v-model:value="splitForm.chunk_size" :min="1" :max="10000" :step="50" style="width: 160px" />
          </n-form-item>
          <n-form-item label="重叠大小" path="chunk_overlap">
            <n-input-number v-model:value="splitForm.chunk_overlap" :min="0" :max="1000" :step="10" style="width: 160px" />
          </n-form-item>
        </n-form>
      </div>

      <!-- ===== Step 3: 索引配置 ===== -->
      <div v-if="currentStep === 3">
        <n-space vertical :size="16">
          <n-radio-group v-model:value="indexMode">
            <n-space vertical>
              <n-radio value="default">使用推荐配置</n-radio>
              <n-radio value="custom">自定义</n-radio>
            </n-space>
          </n-radio-group>

          <template v-if="indexMode === 'custom'">
            <n-divider />
            <div style="font-weight: 600; margin-bottom: 12px">密集向量索引</div>
            <n-form label-placement="left" label-width="auto" :model="indexForm" style="max-width: 500px">
              <n-form-item label="索引类型">
                <n-select v-model:value="indexForm.dense_index_type" :options="denseIndexOptions" />
              </n-form-item>
              <n-form-item label="度量标准">
                <n-select v-model:value="indexForm.dense_metric" :options="metricOptions" />
              </n-form-item>
              <n-space>
                <template v-if="isHNSW">
                  <n-form-item label="M">
                    <n-input-number v-model:value="indexForm.M" :min="4" :max="64" style="width: 120px" />
                  </n-form-item>
                  <n-form-item label="efConstruction">
                    <n-input-number v-model:value="indexForm.efConstruction" :min="8" :max="512" style="width: 140px" />
                  </n-form-item>
                </template>
                <template v-else>
                  <n-form-item label="nlist">
                    <n-input-number v-model:value="indexForm.nlist" :min="1" :max="10000" style="width: 120px" />
                  </n-form-item>
                </template>
                <n-form-item label="nprobe">
                  <n-input-number v-model:value="indexForm.nprobe" :min="1" :max="100" style="width: 120px" />
                </n-form-item>
              </n-space>
            </n-form>

            <template v-if="hybridEnabled">
              <n-divider />
              <div style="font-weight: 600; margin-bottom: 12px">稀疏向量索引</div>
              <n-form label-placement="left" label-width="auto" :model="indexForm" style="max-width: 500px">
                <n-form-item label="索引类型">
                  <n-select v-model:value="indexForm.sparse_index_type" :options="sparseIndexOptions" />
                </n-form-item>
                <n-form-item label="度量标准">
                  <n-select v-model:value="indexForm.sparse_metric" :options="metricOptions" />
                </n-form-item>
              </n-form>
            </template>
          </template>
        </n-space>
      </div>

      <!-- ===== Step 4: 提交处理 ===== -->
      <div v-if="currentStep === 4">
        <n-card title="处理概览" style="max-width: 600px">
          <div class="summary-row"><span class="summary-label">文档数量</span><span>{{ kb.files.length + tempFiles.length }} 个文件</span></div>
          <div class="summary-row" v-if="tempFiles.length > 0"><span class="summary-label">新增文件</span><span>{{ tempFiles.length }} 个待上传</span></div>
          <div class="summary-row"><span class="summary-label">分隔符</span><span>{{ displaySeparator }}</span></div>
          <div class="summary-row"><span class="summary-label">分块大小</span><span>{{ splitForm.chunk_size }}</span></div>
          <div class="summary-row"><span class="summary-label">重叠大小</span><span>{{ splitForm.chunk_overlap }}</span></div>
          <div class="summary-row">
            <span class="summary-label">密集索引</span>
            <span>{{ displayDenseIndex }}</span>
          </div>
          <template v-if="hybridEnabled">
            <div class="summary-row">
              <span class="summary-label">稀疏索引</span>
              <span>{{ displaySparseIndex }}</span>
            </div>
          </template>
          <div class="summary-row">
            <span class="summary-label">处理方式</span>
            <span>
              <n-tag v-if="kb.status === 'ready'" type="warning" size="small">重新处理（将删除现有向量数据）</n-tag>
              <n-tag v-else type="info" size="small">首次处理</n-tag>
            </span>
          </div>
        </n-card>
      </div>

      <!-- ===== Processing Overlay ===== -->
      <div v-if="processing" class="processing-overlay">
        <n-card style="max-width: 450px; text-align: center">
          <template v-if="kb.status === 'ready'">
            <div style="font-size: 48px; color: #18a058">✓</div>
            <h3 style="margin: 12px 0 8px">处理完成</h3>
            <p style="color: #999">
              共处理 {{ kb.doc_count }} 个文档，{{ kb.chunk_count }} 个文本块
            </p>
          </template>
          <template v-else-if="kb.status === 'failed'">
            <div style="font-size: 48px; color: #d03050">✕</div>
            <h3 style="margin: 12px 0 8px">处理失败</h3>
            <p style="color: #d03050">{{ kb.error_message || '未知错误' }}</p>
          </template>
          <template v-else>
            <n-spin size="large" />
            <h3 style="margin: 16px 0 8px">正在处理...</h3>
            <p style="color: #999">加载中 → 切分中 → 嵌入中 → 建索引</p>
          </template>
          <n-space justify="center" style="margin-top: 20px">
            <n-button @click="goBack">返回列表</n-button>
            <n-button v-if="kb.status !== 'processing'" type="primary" @click="resetAfterProcessing">
              继续编辑
            </n-button>
          </n-space>
        </n-card>
      </div>

      <!-- ===== 向导底部操作按钮 ===== -->
      <div v-if="currentStep > 0" style="margin-top: 24px; border-top: 1px solid #eee; padding-top: 16px">
        <n-space justify="space-between">
          <n-space>
            <n-button v-if="currentStep > 1" @click="prevStep">上一步</n-button>
            <n-button v-if="currentStep === 1" @click="cancelWizard">取消</n-button>
          </n-space>
          <n-space>
            <n-button
              v-if="currentStep < 4"
              type="primary"
              @click="nextStep"
            >
              下一步
            </n-button>
            <n-button
              v-if="currentStep === 4"
              type="primary"
              :loading="submitting"
              :disabled="kb.files.length + tempFiles.length === 0"
              @click="handleSubmit"
            >
              提交处理
            </n-button>
          </n-space>
        </n-space>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NPopconfirm, NSpace, NTag, NUpload, NUploadDragger, NAlert, NSteps, NStep, NCard } from 'naive-ui'
import {
  getKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBaseFile,
  uploadKnowledgeBaseFile,
  submitKnowledgeBase,
} from '../api/index.js'

const route = useRoute()
const router = useRouter()
const kbId = route.params.id

const kb = ref(null)
const currentStep = ref(0)
const submitting = ref(false)
const fileLoading = ref(false)
const processing = ref(false)
const splitFormRef = ref(null)
const tempFiles = ref([])
let pollTimer = null

const statusMap = {
  empty: { type: 'default', text: '待处理' },
  processing: { type: 'info', text: '构建中' },
  ready: { type: 'success', text: '已完成' },
  failed: { type: 'error', text: '构建失败' },
}

const statusTagType = computed(() => statusMap[kb.value?.status]?.type || 'default')
const statusText = computed(() => statusMap[kb.value?.status]?.text || kb.value?.status || '')

const displaySeparator = computed(() => {
  return splitForm.value.separator || '使用默认分隔符'
})

const hybridEnabled = computed(() => kb.value?.embedding_model === 'BAAI/bge-m3')

// 切分配置表单
const splitForm = ref({
  separator: '',
  chunk_size: 500,
  chunk_overlap: 100,
})

const splitRules = {
  chunk_size: {
    type: 'number', required: true, min: 1,
    message: '分块大小必须大于 0', trigger: 'blur',
  },
  chunk_overlap: {
    type: 'number', required: true, min: 0,
    message: '重叠大小不能为负数', trigger: 'blur',
  },
}

// 索引配置表单
const indexForm = ref({
  dense_index_type: 'IVF_FLAT',
  dense_metric: 'IP',
  nlist: 100,
  nprobe: 10,
  M: 16,
  efConstruction: 200,
  sparse_index_type: 'SPARSE_INVERTED_INDEX',
  sparse_metric: 'IP',
})
const indexMode = ref('default')
const isHNSW = computed(() => indexForm.value.dense_index_type === 'HNSW')

const denseIndexOptions = [
  { label: 'IVF_FLAT（倒排文件+精确搜索）', value: 'IVF_FLAT' },
  { label: 'IVF_SQ8（倒排文件+量化压缩）', value: 'IVF_SQ8' },
  { label: 'HNSW（分层导航小世界）', value: 'HNSW' },
]

const sparseIndexOptions = [
  { label: 'SPARSE_INVERTED_INDEX', value: 'SPARSE_INVERTED_INDEX' },
  { label: 'SPARSE_WAND', value: 'SPARSE_WAND' },
]

const metricOptions = [
  { label: 'IP（内积）', value: 'IP' },
  { label: 'L2（欧氏距离）', value: 'L2' },
]

const displayDenseIndex = computed(() => {
  if (indexMode.value === 'default') return '使用推荐配置'
  if (isHNSW.value) {
    return `${indexForm.value.dense_index_type} / ${indexForm.value.dense_metric} / M=${indexForm.value.M} ef=${indexForm.value.efConstruction}`
  }
  return `${indexForm.value.dense_index_type} / ${indexForm.value.dense_metric} / nlist=${indexForm.value.nlist}`
})

const displaySparseIndex = computed(() => {
  if (indexMode.value === 'default') return '使用推荐配置'
  return `${indexForm.value.sparse_index_type} / ${indexForm.value.sparse_metric}`
})

// 临时文件表格列（向导模式下使用）
const tempFileColumns = [
  { title: '文件名', key: 'name', ellipsis: { tooltip: true } },
  { title: '格式', key: 'type', width: 70 },
  {
    title: '大小', key: 'size', width: 110,
    render(row) {
      const kbSize = row.size / 1024
      return kbSize > 1024 ? `${(kbSize / 1024).toFixed(1)} MB` : `${kbSize.toFixed(0)} KB`
    },
  },
  {
    title: '操作', key: 'actions', width: 90,
    render(_, index) {
      return h(NButton, { size: 'small', type: 'error', onClick: () => removeTempFile(index) }, { default: () => '移除' })
    },
  },
]

// 已上传文件表格列
const fileColumns = [
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true } },
  { title: '格式', key: 'type', width: 70 },
  {
    title: '大小', key: 'size', width: 110,
    render(row) {
      const kbSize = row.size / 1024
      return kbSize > 1024 ? `${(kbSize / 1024).toFixed(1)} MB` : `${kbSize.toFixed(0)} KB`
    },
  },
  {
    title: '操作', key: 'actions', width: 90,
    render(row) {
      return h(NPopconfirm, {
        onPositiveClick: () => handleDeleteFile(row.id),
        positiveText: '确认',
        negativeText: '取消',
      }, {
        default: () => '确定删除此文件吗？',
        trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
      })
    },
  },
]

// ─── 向导管理 ───

function startNewProcess() {
  currentStep.value = 1
}

function cancelWizard() {
  tempFiles.value = []
  currentStep.value = 0
}

async function nextStep() {
  if (currentStep.value === 2) {
    // 离开切分设置页时自动保存
    await saveConfig(false)
  }
  if (currentStep.value === 3) {
    // 离开索引配置页时自动保存
    await saveIndexConfig(false)
  }
  if (currentStep.value < 4) {
    currentStep.value++
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

async function saveConfig(showMessage = true) {
  try {
    await splitFormRef.value?.validate()
  } catch {
    return false
  }
  try {
    const separators = splitForm.value.separator
      ? splitForm.value.separator.split(',').map(s => s.trim()).filter(Boolean)
      : []
    await updateKnowledgeBase(kbId, {
      split_config: {
        separators: separators.length > 0 ? separators : null,
        chunk_size: splitForm.value.chunk_size,
        chunk_overlap: splitForm.value.chunk_overlap,
      },
    })
    if (showMessage) {
      window.$message?.success('切分配置已保存')
    }
    return true
  } catch (e) {
    if (showMessage) {
      window.$message?.error(e.message)
    }
    return false
  }
}

async function saveIndexConfig(showMessage = true) {
  try {
    await updateKnowledgeBase(kbId, {
      index_config: indexMode.value === 'default' ? {
        dense_index_type: 'IVF_FLAT',
        dense_metric: 'IP',
        nlist: 100,
        nprobe: 10,
        M: 16,
        efConstruction: 200,
        sparse_index_type: 'SPARSE_INVERTED_INDEX',
        sparse_metric: 'IP',
      } : {
        dense_index_type: indexForm.value.dense_index_type,
        dense_metric: indexForm.value.dense_metric,
        nlist: indexForm.value.nlist,
        nprobe: indexForm.value.nprobe,
        M: indexForm.value.M,
        efConstruction: indexForm.value.efConstruction,
        sparse_index_type: indexForm.value.sparse_index_type,
        sparse_metric: indexForm.value.sparse_metric,
      },
    })
    if (showMessage) {
      window.$message?.success('索引配置已保存')
    }
    return true
  } catch (e) {
    if (showMessage) {
      window.$message?.error(e.message)
    }
    return false
  }
}

// ─── 加载数据 ───

async function fetchKB() {
  try {
    const data = await getKnowledgeBase(kbId)
    kb.value = data
    if (data.split_config) {
      splitForm.value.separator = (data.split_config.separators || []).join(', ')
      splitForm.value.chunk_size = data.split_config.chunk_size
      splitForm.value.chunk_overlap = data.split_config.chunk_overlap
    }
    if (data.index_config) {
      indexForm.value.dense_index_type = data.index_config.dense_index_type || 'IVF_FLAT'
      indexForm.value.dense_metric = data.index_config.dense_metric || 'IP'
      indexForm.value.nlist = data.index_config.nlist || 100
      indexForm.value.nprobe = data.index_config.nprobe || 10
      indexForm.value.sparse_index_type = data.index_config.sparse_index_type || 'SPARSE_INVERTED_INDEX'
      indexForm.value.sparse_metric = data.index_config.sparse_metric || 'IP'
      indexForm.value.M = data.index_config.M || 16
      indexForm.value.efConstruction = data.index_config.efConstruction || 200
      // 非默认值时切到自定义模式
      if (data.index_config.dense_index_type !== 'IVF_FLAT' || data.index_config.dense_metric !== 'IP' || data.index_config.nlist !== 100) {
        indexMode.value = 'custom'
      }
      if (data.index_config.dense_index_type === 'HNSW') {
        indexMode.value = 'custom'
      }
    }
    if (data.status === 'processing') {
      processing.value = true
      startPolling()
    }
  } catch (e) {
    window.$message?.error('加载知识库失败: ' + e.message)
    router.push('/knowledge-bases')
  }
}

// ─── 临时文件管理（向导模式下使用） ───

function handleTempFileChange({ fileList }) {
  for (const f of fileList) {
    if (f.file && !tempFiles.value.find(t => t.name === f.name && t.size === f.file.size)) {
      tempFiles.value.push({
        name: f.name,
        size: f.file.size,
        type: (f.name.split('.').pop() || '').toUpperCase(),
        file: f.file,
      })
    }
  }
}

function removeTempFile(index) {
  tempFiles.value.splice(index, 1)
}

// ─── 已上传文件删除 ───

async function handleDeleteFile(fileId) {
  try {
    await deleteKnowledgeBaseFile(kbId, fileId)
    window.$message?.success('文件已删除')
    await fetchKB()
  } catch (e) {
    window.$message?.error(e.message)
  }
}

// ─── 提交处理 ───

async function handleSubmit() {
  if (tempFiles.value.length === 0 && kb.value.files.length === 0) return

  // 先保存切分配置和索引配置
  await saveConfig(false)
  await saveIndexConfig(false)

  // 上传临时文件
  fileLoading.value = true
  let uploaded = 0
  for (const t of tempFiles.value) {
    try {
      await uploadKnowledgeBaseFile(kbId, t.file)
      uploaded++
    } catch (e) {
      window.$message?.error(`上传失败: ${t.name} - ${e.message}`)
    }
  }
  fileLoading.value = false
  tempFiles.value = []

  if (uploaded > 0) {
    await fetchKB()
  }

  submitting.value = true
  try {
    await submitKnowledgeBase(kbId)
    processing.value = true
    window.$message?.info('处理任务已提交')
    await fetchKB()
    startPolling()
  } catch (e) {
    window.$message?.error(e.message)
  } finally {
    submitting.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const data = await getKnowledgeBase(kbId)
      kb.value = data
      if (data.status === 'ready') {
        window.$message?.success('知识库处理完成')
        stopPolling()
      } else if (data.status === 'failed') {
        window.$message?.error('处理失败: ' + (data.error_message || '未知错误'))
        stopPolling()
      }
    } catch {
      stopPolling()
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function resetAfterProcessing() {
  processing.value = false
  tempFiles.value = []
  currentStep.value = 0
}

function goBack() {
  router.push('/knowledge-bases')
}

onMounted(fetchKB)
onUnmounted(stopPolling)
</script>

<script>
import { h } from 'vue'
</script>

<style scoped>
.processing-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.summary-row:last-child {
  border-bottom: none;
}
.summary-label {
  color: #666;
  font-size: 14px;
}
</style>
