<template>
  <n-layout has-sider style="height: 100vh">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="200"
      :collapsed="collapsed"
      show-trigger="bar"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="sider-header">
        <span v-if="!collapsed" class="logo-text">知识库-智能问答</span>
        <span v-else class="logo-text-short">N</span>
      </div>
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="20"
        :value="activeKey"
        :options="menuOptions"
        @update:value="handleMenuSelect"
      />
    </n-layout-sider>
    <n-layout>
      <router-view />
    </n-layout>
  </n-layout>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NIcon } from 'naive-ui'
import { ChatboxOutline, SettingsOutline, LibraryOutline, CheckmarkCircleOutline, DocumentTextOutline } from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()
const collapsed = ref(false)

const activeKey = computed(() => {
  if (route.path === '/models') return 'models'
  if (route.path.startsWith('/knowledge-bases')) return 'knowledge-bases'
  if (route.path === '/test-sets') return 'test-sets'
  if (route.path.startsWith('/evaluations')) return 'evaluations'
  return 'chat'
})

const menuOptions = [
  {
    label: '对话',
    key: 'chat',
    icon: () => h(NIcon, null, { default: () => h(ChatboxOutline) }),
  },
  {
    label: '模型管理',
    key: 'models',
    icon: () => h(NIcon, null, { default: () => h(SettingsOutline) }),
  },
  {
    label: '知识库管理',
    key: 'knowledge-bases',
    icon: () => h(NIcon, null, { default: () => h(LibraryOutline) }),
  },
  {
    label: '测试集',
    key: 'test-sets',
    icon: () => h(NIcon, null, { default: () => h(DocumentTextOutline) }),
  },
  {
    label: '评估运行',
    key: 'evaluations',
    icon: () => h(NIcon, null, { default: () => h(CheckmarkCircleOutline) }),
  },
]

function handleMenuSelect(key) {
  const pathMap = { chat: '/', models: '/models', 'knowledge-bases': '/knowledge-bases', 'test-sets': '/test-sets', evaluations: '/evaluations' }
  router.push(pathMap[key])
}
</script>

<script>
import { h } from 'vue'
</script>

<style>
body {
  margin: 0;
  padding: 0;
}
.sider-header {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  font-size: 16px;
  font-weight: 700;
  color: #18a058;
  border-bottom: 1px solid #eee;
}
.logo-text-short {
  font-size: 20px;
}
</style>
