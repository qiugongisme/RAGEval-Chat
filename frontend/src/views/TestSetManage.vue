<template>
  <n-layout class="page-layout">
    <n-layout-header class="page-header">
      <h2>测试集管理</h2>
    </n-layout-header>
    <div style="margin-bottom: 16px">
      <n-upload
        :default-upload="false"
        accept=".xlsx,.xls"
        @change="handleUpload"
      >
        <n-button type="primary">
          <template #icon><n-icon><add-outline /></n-icon></template>
          上传测试集
        </n-button>
      </n-upload>
    </div>

    <n-layout-content class="page-content">
      <n-spin :show="loading">
        <n-empty v-if="!loading && testSets.length === 0" description="暂无测试集，请上传 .xlsx 文件">
          <template #extra>
            <n-button type="primary" @click="triggerUpload">上传测试集</n-button>
          </template>
        </n-empty>

        <n-table v-else :bordered="true" :single-line="false">
          <thead>
            <tr>
              <th>名称</th>
              <th>Sheet</th>
              <th>问题数</th>
              <th>上传时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ts in testSets" :key="ts.id">
              <td>{{ ts.name }}</td>
              <td>{{ ts.sheet_names?.join(', ') || '-' }}</td>
              <td>{{ ts.count }}</td>
              <td>{{ formatDate(ts.created_at) }}</td>
              <td>
                <n-popconfirm @positive-click="handleDelete(ts.id)" positive-text="确认" negative-text="取消">
                  <template #trigger>
                    <n-button size="small" type="error" ghost>删除</n-button>
                  </template>
                  确定删除此测试集吗？
                </n-popconfirm>
              </td>
            </tr>
          </tbody>
        </n-table>
      </n-spin>
    </n-layout-content>
  </n-layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, NPopconfirm } from 'naive-ui'
import { AddOutline } from '@vicons/ionicons5'
import { getTestSets, uploadTestSet, deleteTestSet } from '../api/index.js'

const message = useMessage()
const loading = ref(false)
const testSets = ref([])

async function loadTestSets() {
  loading.value = true
  try {
    testSets.value = await getTestSets()
  } catch (e) {
    message.error('加载测试集失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

async function handleUpload({ file }) {
  if (!file?.file) return
  try {
    await uploadTestSet(file.file)
    message.success('上传成功')
    await loadTestSets()
  } catch (e) {
    message.error('上传失败: ' + e.message)
  }
}

async function handleDelete(id) {
  try {
    await deleteTestSet(id)
    message.success('删除成功')
    await loadTestSets()
  } catch (e) {
    message.error('删除失败: ' + e.message)
  }
}

function triggerUpload() {
  // 触发文件选择
  document.querySelector('.n-upload-trigger')?.click()
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(loadTestSets)
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
</style>
