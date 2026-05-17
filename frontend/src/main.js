import { createApp } from 'vue'
import naive, { createDiscreteApi } from 'naive-ui'
import App from './App.vue'
import router from './router'

// 全局注册 Naive UI 的 message 等离散 API，供组件外使用
const { message } = createDiscreteApi(['message'])
window.$message = message

const app = createApp(App)
app.use(router)
app.use(naive)
app.mount('#app')
