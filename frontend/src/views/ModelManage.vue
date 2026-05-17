<template>
  <div style="padding: 24px">
    <n-h2>模型管理</n-h2>
    <n-space vertical :size="16">
      <n-space justify="end">
        <n-button type="primary" @click="handleAdd">新增模型</n-button>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="models"
        :loading="loading"
        :pagination="{ pageSize: 10 }"
        :bordered="true"
      />
    </n-space>

    <!-- 新增模型弹窗 -->
    <n-modal v-model:show="showModal" :title="editingId ? '编辑模型' : '新增模型'" preset="card" style="width: 560px">
      <n-form ref="formRef" :model="formData" :rules="rules" label-placement="left" label-width="auto">
        <n-form-item label="名称" path="name">
          <n-input v-model:value="formData.name" placeholder="例如: DeepSeek Chat" />
        </n-form-item>
        <n-form-item label="提供商" path="provider">
          <n-select
            v-model:value="formData.provider"
            :options="[
              { label: 'DeepSeek', value: 'deepseek' },
              { label: '通义千问 (Qwen)', value: 'qwen' },
            ]"
          />
        </n-form-item>
        <n-form-item label="API 密钥" path="api_key">
          <n-input v-model:value="formData.api_key" type="password" show-password-on="click" placeholder="输入 API Key" />
        </n-form-item>
        <n-form-item label="模型标识" path="model_name">
          <n-input v-model:value="formData.model_name" placeholder="例如: deepseek-chat" />
        </n-form-item>
        <n-form-item>
          <template #label>
            Temperature
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <span style="cursor:help;color:#999;margin-left:4px">ⓘ</span>
              </template>
              控制回答的随机性。越低回答越确定保守（适合事实问答），越高越有创意发散（适合头脑风暴）。建议 0.7 左右。
            </n-tooltip>
          </template>
          <n-input-number v-model:value="formData.temperature" :min="0" :max="2" :step="0.1" />
        </n-form-item>
        <n-form-item>
          <template #label>
            Max Tokens
            <n-tooltip trigger="hover" placement="right">
              <template #trigger>
                <span style="cursor:help;color:#999;margin-left:4px">ⓘ</span>
              </template>
              限制单次回答的最大字数。回答较长或需详细输出时可调高，简单问答保持默认即可。
            </n-tooltip>
          </template>
          <n-input-number v-model:value="formData.max_tokens" :min="1" :max="128000" :step="1" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleSubmit">确认</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { NButton, NPopconfirm, NSpace } from 'naive-ui'
import { getModels, createModel, updateModel, deleteModel } from '../api/index.js'

const models = ref([])
const loading = ref(false)
const showModal = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const editingId = ref(null)

const defaultForm = () => ({
  name: '',
  provider: 'deepseek',
  api_key: '',
  model_name: '',
  temperature: 0.7,
  max_tokens: 2048,
})

const formData = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入模型名称', trigger: 'blur' },
  provider: { required: true, message: '请选择提供商', trigger: 'change' },
  model_name: { required: true, message: '请输入模型标识', trigger: 'blur' },
}

const columns = [
  { title: '名称', key: 'name' },
  { title: '提供商', key: 'provider' },
  { title: '模型标识', key: 'model_name' },
  { title: 'API 密钥', key: 'api_key', ellipsis: { tooltip: true } },
  { title: 'Temperature', key: 'temperature', width: 120 },
  { title: 'Max Tokens', key: 'max_tokens', width: 120 },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render(row) {
      return h(NSpace, null, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', ghost: true, onClick: () => handleEdit(row) }, { default: () => '编辑' }),
          h(NPopconfirm, {
            onPositiveClick: () => handleDelete(row.id),
            positiveText: '确认',
            negativeText: '取消',
          }, {
            default: () => '确定删除此模型吗？',
            trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          }),
        ],
      })
    },
  },
]

async function fetchModels() {
  loading.value = true
  try {
    models.value = await getModels()
  } catch (e) {
    window.$message?.error(e.message)
  } finally {
    loading.value = false
  }
}

async function handleEdit(row) {
  editingId.value = row.id
  formData.value = {
    name: row.name,
    provider: row.provider,
    api_key: row.api_key,
    model_name: row.model_name,
    temperature: row.temperature,
    max_tokens: row.max_tokens,
  }
  showModal.value = true
}

function handleAdd() {
  editingId.value = null
  formData.value = defaultForm()
  showModal.value = true
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      await updateModel(editingId.value, formData.value)
      window.$message?.success('模型已更新')
    } else {
      await createModel(formData.value)
      window.$message?.success('模型已创建')
    }
    showModal.value = false
    formData.value = defaultForm()
    await fetchModels()
  } catch (e) {
    window.$message?.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await deleteModel(id)
    window.$message?.success('模型已删除')
    await fetchModels()
  } catch (e) {
    window.$message?.error(e.message)
  }
}

onMounted(fetchModels)
</script>
