const BASE_URL = '/api/v1'

async function request(url, options = {}) {
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { ...headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const text = await res.text()
  return text ? JSON.parse(text) : null
}

// ─── 模型管理 ───

export function getModels() {
  return request('/models')
}

export function createModel(data) {
  return request('/models', { method: 'POST', body: JSON.stringify(data) })
}

export function updateModel(id, data) {
  return request(`/models/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteModel(id) {
  return request(`/models/${id}`, { method: 'DELETE' })
}

// ─── 知识库管理 ───

/** 获取知识库列表 */
export function getKnowledgeBases() {
  return request('/knowledge-bases')
}

/** 获取知识库详情 */
export function getKnowledgeBase(id) {
  return request(`/knowledge-bases/${id}`)
}

/** 创建知识库（仅元数据） */
export function createKnowledgeBase(data) {
  return request('/knowledge-bases', { method: 'POST', body: JSON.stringify(data) })
}

/** 更新知识库（名称/描述/切分配置等） */
export function updateKnowledgeBase(id, data) {
  return request(`/knowledge-bases/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

/** 删除知识库（含向量库和文件） */
export function deleteKnowledgeBase(id) {
  return request(`/knowledge-bases/${id}`, { method: 'DELETE' })
}

// ─── 知识库文件管理 ───

/** 获取知识库的文件列表 */
export function getKnowledgeBaseFiles(kbId) {
  return request(`/knowledge-bases/${kbId}/files`)
}

/** 上传文件到知识库 */
export function uploadKnowledgeBaseFile(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request(`/knowledge-bases/${kbId}/files`, { method: 'POST', body: formData })
}

/** 删除知识库中的文件 */
export function deleteKnowledgeBaseFile(kbId, fileId) {
  return request(`/knowledge-bases/${kbId}/files/${fileId}`, { method: 'DELETE' })
}

// ─── 知识库提交流程 ───

/** 提交知识库处理 */
export function submitKnowledgeBase(kbId) {
  return request(`/knowledge-bases/${kbId}/submit`, { method: 'POST', body: '{}' })
}

/** 获取知识库处理状态 */
export function getKnowledgeBaseStatus(kbId) {
  return request(`/knowledge-bases/${kbId}/status`)
}

// ─── 会话管理 ───

export function getSessions() {
  return request('/sessions')
}

export function createSession(data) {
  return request('/sessions', { method: 'POST', body: JSON.stringify(data) })
}

export function updateSession(id, data) {
  return request(`/sessions/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteSession(id) {
  return request(`/sessions/${id}`, { method: 'DELETE' })
}

export function getSessionMessages(id) {
  return request(`/sessions/${id}/messages`)
}

export function saveSessionMessages(id, data) {
  return request(`/sessions/${id}/messages`, { method: 'PUT', body: JSON.stringify(data) })
}

/** 生成知识库提示词模板 */
export function generateKBPrompt(kbId) {
  return request(`/knowledge-bases/${kbId}/generate-prompt`, { method: 'POST' })
}

// ─── 对话 ───

export async function chatStream(question, modelId, kbId, onToken, onDone, onError) {
  const res = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, model_id: modelId, kb_id: kbId }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    onError(new Error(err.detail || `HTTP ${res.status}`))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        if (data.type === 'token') {
          onToken(data.token)
        } else if (data.type === 'done') {
          onDone(data.answer, data.context, data.chunks || [])
        } else if (data.type === 'error') {
          onError(new Error(data.message))
        }
      }
    }
  }
}

// ─── 测试集管理 ───

export function getTestSets() {
  return request('/test-sets')
}

export function uploadTestSet(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/test-sets/upload', { method: 'POST', body: formData })
}

export function deleteTestSet(id) {
  return request(`/test-sets/${id}`, { method: 'DELETE' })
}

// ─── 评估管理 ───

export function getEvaluations() {
  return request('/evaluations')
}

export function createEvaluation(data) {
  return request('/evaluations', { method: 'POST', body: JSON.stringify(data) })
}

export function getEvaluation(id) {
  return request(`/evaluations/${id}`)
}

export function deleteEvaluation(id) {
  return request(`/evaluations/${id}`, { method: 'DELETE' })
}

export function compareEvaluations(id1, id2) {
  return request(`/evaluations/${id1}/compare/${id2}`)
}
