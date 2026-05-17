import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '../views/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      { path: '', name: 'Chat', component: () => import('../views/Chat.vue') },
      { path: 'models', name: 'Models', component: () => import('../views/ModelManage.vue') },
      { path: 'knowledge-bases', name: 'KnowledgeBases', component: () => import('../views/KnowledgeBase.vue') },
      { path: 'knowledge-bases/:id', name: 'KBDetail', component: () => import('../views/KBDetail.vue') },
      { path: 'test-sets', name: 'TestSets', component: () => import('../views/TestSetManage.vue') },
      { path: 'evaluations', name: 'Evaluations', component: () => import('../views/EvaluationRun.vue') },
      { path: 'evaluations/:id', name: 'EvaluationReport', component: () => import('../views/EvaluationReport.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
