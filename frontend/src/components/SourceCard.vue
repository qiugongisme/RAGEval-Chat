<template>
  <div v-if="sources.length" class="source-card">
    <div class="source-title">—— 参考来源 ——</div>
    <div
      v-for="(src, i) in sources"
      :key="i"
      class="source-item"
      @click="showSourceChunks(src)"
    >
      📎 {{ src }}
    </div>
  </div>

  <!-- 原文查看抽屉 -->
  <n-drawer v-model:show="drawerVisible" :width="560" placement="right">
    <n-drawer-content :title="selectedSource" closable>
      <div class="chunk-list">
        <div v-for="(chunk, i) in selectedChunks" :key="i" class="chunk-item">
          <div class="chunk-text">{{ chunk.text }}</div>
          <div class="chunk-meta">相似度: {{ chunk.score }}</div>
        </div>
        <div v-if="selectedChunks.length === 0" class="chunk-empty">暂无原文信息</div>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { ref } from 'vue'
import { NDrawer, NDrawerContent } from 'naive-ui'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  chunks: { type: Array, default: () => [] },
})

const drawerVisible = ref(false)
const selectedSource = ref('')
const selectedChunks = ref([])

function showSourceChunks(sourceName) {
  selectedSource.value = sourceName
  selectedChunks.value = props.chunks.filter(c => c.source === sourceName)
  drawerVisible.value = true
}
</script>

<style scoped>
.source-card {
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  color: #666;
}
.source-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}
.source-item {
  padding: 2px 0;
  cursor: pointer;
  transition: color 0.15s;
}
.source-item:hover {
  color: #2080f0;
  text-decoration: underline;
}
.chunk-list {
  overflow-y: auto;
}
.chunk-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #f8f9fb;
  border-radius: 6px;
  border-left: 3px solid #2080f0;
}
.chunk-text {
  font-size: 14px;
  line-height: 1.7;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
}
.chunk-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}
.chunk-empty {
  color: #999;
  text-align: center;
  padding: 24px;
}
</style>
