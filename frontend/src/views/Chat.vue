<template>
  <div class="chat-layout">
    <!-- 会话侧边栏 -->
    <div class="session-sidebar" :class="{ collapsed: !sidebarShow }" @click="handleSidebarClick">
      <div class="sidebar-header">
        <span v-if="sidebarShow" class="sidebar-title">会话</span>
        <n-button size="tiny" text @click.stop="sidebarShow = !sidebarShow">
          <svg v-if="sidebarShow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="7" x2="11" y2="7"></line><line x1="5" y1="12" x2="11" y2="12"></line><line x1="5" y1="17" x2="11" y2="17"></line><polyline points="15,10 18,12 15,14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></polyline></svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="13" y1="7" x2="19" y2="7"></line><line x1="13" y1="12" x2="19" y2="12"></line><line x1="13" y1="17" x2="19" y2="17"></line><polyline points="9,10 6,12 9,14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></polyline></svg>
        </n-button>
      </div>
      <template v-if="sidebarShow">
        <div class="sidebar-search">
          <n-input v-model:value="searchQuery" placeholder="搜索会话..." size="small" clearable />
        </div>
        <div class="sidebar-new-btn">
          <n-button size="small" block @click="handleNewChat">＋ 新对话</n-button>
        </div>
        <div class="sidebar-list">
          <div
            v-for="s in filteredSessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === currentSessionId }"
            @click="handleSwitchSession(s.id)"
          >
            <!-- 重命名模式 -->
            <template v-if="renameId === s.id">
              <div class="rename-wrapper">
                <n-input
                  v-model:value="renameText"
                  size="tiny"
                  @keyup.enter="confirmRename"
                  @blur="cancelRename"
                  @keyup.escape="cancelRename"
                  @click.stop
                  autofocus
                />
                <span class="rename-clear-btn" @click.stop="renameText = ''" title="清空">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </span>
              </div>
            </template>
            <template v-else>
              <div class="session-info">
                <div class="session-title" :title="s.title">{{ s.title }}</div>
                <div class="session-time">{{ formatTime(s.updated_at) }}</div>
              </div>
              <div class="session-actions" @click.stop>
                <n-popconfirm
                  :positive-text="'确认'"
                  :negative-text="'取消'"
                  @positive-click="handleDeleteSession(s.id)"
                >
                  <template #trigger>
                    <span class="session-action-btn" title="删除会话">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </span>
                  </template>
                  确认删除该会话？
                </n-popconfirm>
                <span class="session-action-btn" title="重命名" @click="startRename(s)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                </span>
              </div>
            </template>
          </div>
          <div v-if="filteredSessions.length === 0" class="sidebar-empty">
            {{ searchQuery ? '无匹配会话' : '暂无会话' }}
          </div>
        </div>
      </template>
    </div>

    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 顶部工具栏 -->
      <div class="chat-toolbar">
        <n-space align="center" style="flex: 1">
          <n-select
            v-model:value="selectedModel"
            :options="modelOptions"
            placeholder="选择模型"
            style="width: 200px"
            clearable
          />
          <n-select
            v-model:value="selectedKb"
            :options="kbOptions"
            placeholder="选择知识库（默认通用对话）"
            style="width: 240px"
            clearable
          />
        </n-space>
        <n-button size="small" @click="handleClearSession">清空会话</n-button>
      </div>

      <!-- 消息列表 -->
      <div ref="messageListRef" class="message-list">
        <div v-if="messages.length === 0" class="empty-state">
          <div class="empty-icon">💬</div>
          <div class="empty-text">选择模型后即可开始提问（可选知识库进行知识库问答）</div>
        </div>

        <div v-for="(msg, i) in messages" :key="i" class="message-wrapper" :class="msg.role">
          <div class="message-avatar">{{ msg.role === 'user' ? 'U' : 'A' }}</div>
          <div class="message-content">
            <div class="message-text">{{ msg.content }}</div>
            <div v-if="!streaming" class="message-actions-bar">
              <template v-if="msg.role === 'user'">
                <span class="action-icon" title="复制" @click="copyText(msg.content)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </span>
              </template>
              <template v-else>
                <span class="action-icon" title="复制文本" @click="copyText(msg.content)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </span>
                <span class="action-icon" title="复制 Markdown" @click="copyMarkdown(msg.content)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18v16H3V4z"></path><path d="M7 12l3-3 3 3"></path><path d="M13 12l3-3 3 3"></path><path d="M7 15h10"></path></svg>
                </span>
                <span class="action-icon-divider"></span>
                <span class="action-icon" title="重新生成" @click="handleRegenerate(i)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                </span>
              </template>
            </div>
            <SourceCard v-if="msg.sources && msg.sources.length" :sources="msg.sources" :chunks="msg.chunks || []" />
          </div>
        </div>

        <!-- 流式响应占位 -->
        <div v-if="streaming" class="message-wrapper assistant">
          <div class="message-avatar">A</div>
          <div class="message-content">
            <div class="message-text">{{ currentAnswer }}<span class="cursor-blink">▌</span></div>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <n-input
            v-model:value="inputText"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 10 }"
            placeholder="请输入你的问题..."
            :disabled="streaming"
            class="chat-textarea"
            @keydown.enter.prevent="handleSend"
          />
          <n-button
            class="send-btn"
            type="primary"
            circle
            :loading="streaming"
            :disabled="!inputText.trim() || !selectedModel"
            @click="handleSend"
          >
            <template #icon>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="19" x2="12" y2="5"></line>
                <polyline points="5 12 12 5 19 12"></polyline>
              </svg>
            </template>
          </n-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { getModels, getKnowledgeBases, chatStream } from '../api/index.js'
import {
  getSessions,
  createSession,
  updateSession,
  deleteSession,
  getSessionMessages,
  saveSessionMessages,
} from '../api/index.js'
import SourceCard from '../components/SourceCard.vue'

const models = ref([])
const knowledgeBases = ref([])
const selectedModel = ref(null)
const selectedKb = ref(null)
const messages = ref([])
const inputText = ref('')
const streaming = ref(false)
const currentAnswer = ref('')
const messageListRef = ref(null)

// ─── 会话管理状态 ───
const sessions = ref([])
const currentSessionId = ref(null)
const sidebarShow = ref(true)
const searchQuery = ref('')
const renameId = ref(null)
const renameText = ref('')

const modelOptions = computed(() =>
  models.value.map(m => ({ label: m.name, value: m.id }))
)

const kbOptions = computed(() => [
  { label: '通用对话（默认）', value: null },
  ...knowledgeBases.value.map(k => ({ label: k.name, value: k.id })),
])

// ─── 会话搜索过滤 ───
const filteredSessions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sessions.value
  return sessions.value.filter(s => s.title.toLowerCase().includes(q))
})

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^>+\s*/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(stripMarkdown(text))
    window.$message?.success('文本已复制')
  } catch {
    window.$message?.error('复制失败')
  }
}

async function copyMarkdown(text) {
  try {
    await navigator.clipboard.writeText(text)
    window.$message?.success('Markdown 已复制')
  } catch {
    window.$message?.error('复制失败')
  }
}

function formatTime(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const hhmm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (d.toDateString() === now.toDateString()) {
    return hhmm
  }
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hhmm}`
}

function handleSidebarClick() {
  if (!sidebarShow.value) sidebarShow.value = true
}

// ─── 会话 CRUD ───

async function loadSessions() {
  try {
    sessions.value = await getSessions()
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

async function ensureSession() {
  if (currentSessionId.value) return
  try {
    const result = await createSession({
      model_id: selectedModel.value,
      kb_id: selectedKb.value === null ? undefined : selectedKb.value,
    })
    currentSessionId.value = result.id
    await loadSessions()
  } catch (e) {
    window.$message?.error('创建会话失败')
    throw e
  }
}

async function handleSwitchSession(id) {
  if (id === currentSessionId.value || streaming.value) return
  try {
    const msgs = await getSessionMessages(id)
    messages.value = msgs
    currentSessionId.value = id
    const session = sessions.value.find(s => s.id === id)
    if (session) {
      selectedModel.value = session.model_id
      selectedKb.value = session.kb_id
    }
    await nextTick()
    scrollToBottom()
  } catch (e) {
    window.$message?.error('加载会话失败')
  }
}

async function handleClearSession() {
  if (streaming.value) return
  if (!currentSessionId.value) return
  if (messages.value.length === 0) return

  messages.value = []
  currentAnswer.value = ''
  streaming.value = false
  await saveMessages()
  window.$message?.success('会话已清空')
}

async function handleNewChat() {
  if (streaming.value) return
  try {
    const result = await createSession({
      model_id: selectedModel.value,
      kb_id: selectedKb.value === null ? undefined : selectedKb.value,
    })
    currentSessionId.value = result.id
    messages.value = []
    currentAnswer.value = ''
    streaming.value = false
    await loadSessions()
  } catch (e) {
    window.$message?.error('创建会话失败')
  }
}

function startRename(session) {
  renameId.value = session.id
  renameText.value = session.title
}

async function confirmRename() {
  const id = renameId.value
  const title = renameText.value.trim()
  if (id && title) {
    try {
      await updateSession(id, { title })
      await loadSessions()
    } catch (e) {
      window.$message?.error('重命名失败')
    }
  }
  renameId.value = null
  renameText.value = ''
}

function cancelRename() {
  renameId.value = null
  renameText.value = ''
}

async function handleDeleteSession(id) {
  try {
    await deleteSession(id)
    if (currentSessionId.value === id) {
      currentSessionId.value = null
      messages.value = []
    }
    await loadSessions()
    window.$message?.success('会话已删除')
  } catch (e) {
    window.$message?.error('删除失败')
  }
}

// ─── 对话 ───

async function handleRegenerate(index) {
  const userMsg = messages.value[index - 1]
  if (!userMsg || userMsg.role !== 'user' || !selectedModel.value) return

  messages.value = messages.value.slice(0, index)

  streaming.value = true
  currentAnswer.value = ''
  scrollToBottom()

  const kbId = selectedKb.value === null ? undefined : selectedKb.value

  chatStream(
    userMsg.content,
    selectedModel.value,
    kbId,
    (token) => {
      currentAnswer.value += token
      scrollToBottom()
    },
    async (answer, context, chunks) => {
      const sources = context ? parseSources(context) : []
      messages.value.push({ role: 'assistant', content: answer, sources, chunks })
      currentAnswer.value = ''
      streaming.value = false
      scrollToBottom()
      await saveMessages()
    },
    async (err) => {
      window.$message?.error(err.message)
      currentAnswer.value = ''
      streaming.value = false
      scrollToBottom()
    },
  )
}

function parseSources(context) {
  if (!context) return []
  const lines = context.split('\n')
  const sources = []
  for (const line of lines) {
    const match = line.match(/来源于国家金融监督管理总局发布文件\s*(.+)/)
    if (match) {
      sources.push(match[1].trim())
    }
  }
  return [...new Set(sources)]
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

async function saveMessages() {
  if (!currentSessionId.value) return
  try {
    await saveSessionMessages(currentSessionId.value, { messages: messages.value })
    await loadSessions()
  } catch (e) {
    console.error('保存消息失败', e)
  }
}

async function handleSend() {
  const question = inputText.value.trim()
  if (!question || !selectedModel.value) return

  // 自动创建会话
  try {
    await ensureSession()
  } catch {
    return
  }

  messages.value.push({ role: 'user', content: question })
  inputText.value = ''
  streaming.value = true
  currentAnswer.value = ''
  scrollToBottom()

  const kbId = selectedKb.value === null ? undefined : selectedKb.value

  chatStream(
    question,
    selectedModel.value,
    kbId,
    (token) => {
      currentAnswer.value += token
      scrollToBottom()
    },
    async (answer, context, chunks) => {
      const sources = context ? parseSources(context) : []
      messages.value.push({ role: 'assistant', content: answer, sources, chunks })
      currentAnswer.value = ''
      streaming.value = false
      scrollToBottom()
      await saveMessages()
    },
    async (err) => {
      window.$message?.error(err.message)
      messages.value.push({ role: 'assistant', content: `错误: ${err.message}`, sources: [] })
      currentAnswer.value = ''
      streaming.value = false
      scrollToBottom()
      await saveMessages()
    },
  )
}

onMounted(async () => {
  try {
    const [m, kbs, sess] = await Promise.all([
      getModels(),
      getKnowledgeBases(),
      getSessions(),
    ])
    models.value = m
    knowledgeBases.value = kbs
    sessions.value = sess
    if (models.value.length) selectedModel.value = models.value[0].id

    // 有历史会话则恢复最后一个
    if (sessions.value.length > 0) {
      await handleSwitchSession(sessions.value[0].id)
    }
  } catch (e) {
    window.$message?.error('加载数据失败: ' + (e.message || e))
  }
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100%;
}

/* ─── 会话侧边栏 ─── */
.session-sidebar {
  width: 260px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #eee;
  background: #fafbfc;
  transition: all 0.2s ease;
  overflow: hidden;
}
.session-sidebar.collapsed {
  width: 72px;
  min-width: 72px;
  background: #f0f2f5;
  cursor: pointer;
}
.session-sidebar.collapsed:hover {
  background: #e8eaed;
}
.session-sidebar.collapsed .sidebar-header {
  justify-content: center;
  padding: 20px 0;
  height: auto;
}
.session-sidebar.collapsed .sidebar-header .n-button {
  transform: scale(1.4);
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
}
.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.sidebar-search {
  padding: 0 12px 8px;
}
.sidebar-new-btn {
  padding: 0 12px 8px;
}
.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
  gap: 4px;
}
.session-item:hover {
  background: #eef0f2;
}
.session-item.active {
  background: #e8f4ff;
}
.session-item.active .session-title {
  color: #2080f0;
  font-weight: 500;
}
.session-info {
  flex: 1;
  min-width: 0;
}
.session-title {
  font-size: 13px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}
.session-time {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}
.session-actions {
  display: none;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.session-item:hover .session-actions {
  display: flex;
}
.session-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  transition: all 0.15s;
}
.session-action-btn:hover {
  background: #ddd;
  color: #333;
}
.sidebar-empty {
  text-align: center;
  color: #bbb;
  font-size: 13px;
  padding: 24px 0;
}
.rename-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}
.rename-wrapper .n-input {
  flex: 1;
}
.rename-clear-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.rename-clear-btn:hover {
  background: #ddd;
  color: #333;
}

/* ─── 主聊天区域 ─── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid #eee;
  background: #fff;
  gap: 12px;
}
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f8f9fb;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-text {
  font-size: 14px;
}
.message-wrapper {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.message-wrapper.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.message-wrapper.user .message-avatar {
  background: #18a058;
  color: #fff;
}
.message-wrapper.assistant .message-avatar {
  background: #2080f0;
  color: #fff;
}
.message-content {
  max-width: 70%;
}
.message-wrapper.user .message-content {
  text-align: right;
}
.message-text {
  background: #fff;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.message-wrapper.user .message-text {
  background: #18a058;
  color: #fff;
}

/* 图标操作栏 */
.message-actions-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 4px;
  min-height: 28px;
}
.message-wrapper.user .message-actions-bar {
  justify-content: flex-end;
}
.action-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  color: #bbb;
  cursor: pointer;
  transition: all 0.15s;
}
.action-icon:hover {
  background: #f0f0f0;
  color: #333;
}
.action-icon-divider {
  display: inline-block;
  width: 1px;
  height: 16px;
  background: #e0e0e0;
  margin: 0 4px;
}
.cursor-blink {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid #eee;
  background: #fff;
}
.input-wrapper {
  position: relative;
}
.chat-textarea {
  --n-border-radius: 12px;
}
.chat-textarea textarea {
  padding-right: 48px !important;
  border-radius: 12px !important;
}
.send-btn {
  position: absolute;
  right: 8px;
  bottom: 8px;
  z-index: 1;
}
</style>
