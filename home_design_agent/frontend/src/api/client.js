import axios from 'axios'

// 单端口部署：同域 /api
const client = axios.create({
  baseURL: '/api/design',
  // 真实生图为同步等待：文生图约 30-90s，图生图（带参考图）可达 2-4 分钟，
  // 多窗口并行时服务商侧还会排队。需大于后端轮询上限 MAIZI_POLL_TIMEOUT(300s)
  timeout: 360000,
  // Django CSRF：从 cookie 读取 token 并作为请求头发送
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  withCredentials: true,
})

// 兜底：显式从 cookie 读取 csrftoken 注入不安全请求头，
// 避免登录 admin 后带 sessionid 触发 DRF SessionAuthentication 的 CSRF 403。
function readCookie(name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)')
  return match ? decodeURIComponent(match.pop()) : ''
}

client.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase()
  if (!['get', 'head', 'options', 'trace'].includes(method)) {
    const token = readCookie('csrftoken')
    if (token) {
      config.headers = config.headers || {}
      config.headers['X-CSRFToken'] = token
    }
  }
  return config
})

client.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
)

export const api = {
  health: () => client.get('/health/'),
  // 项目
  listProjects: () => client.get('/projects/'),
  getProject: (id) => client.get(`/projects/${id}/`),
  createProject: (data, config) => client.post('/projects/', data, config),
  createProjectForm: (formData) =>
    client.post('/projects/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  generateSchemes: (id) => client.post(`/projects/${id}/generate_schemes/`),
  // 方案
  toggleFavorite: (id) => client.post(`/schemes/${id}/toggle_favorite/`),
  // 留资
  createLead: (data) => client.post('/leads/', data),
  // 服务商
  listProviders: () => client.get('/providers/'),
  // 效果图渲染
  createRender: (formData, config = {}) =>
    client.post('/renders/', formData, {
      ...config,
      headers: { 'Content-Type': 'multipart/form-data', ...(config.headers || {}) },
    }),
  getRender: (id) => client.get(`/renders/${id}/`),
  regenerateRender: (id, config) => client.post(`/renders/${id}/regenerate/`, null, config),
  listRenders: (projectId) =>
    client.get('/renders/', { params: projectId ? { project: projectId } : {} }),
  listFurnitures: (params) => client.get('/furnitures/', { params }),
  listDesigners: () => client.get('/designers/'),
  // 发散选项（prompt 控制模块）
  // 枚举 / 可勾选模块 / 分组规则 / 输入约束
  getPromptOptions: () => client.get('/prompt-modules/options/'),
  // 按 room_type + style + budget_tier 给出发散方案建议
  suggestPromptVariants: (params) => client.get('/prompt-modules/suggest/', { params }),
  // 生图工作流（后台编排，前端只读；mode 区分图生图 / 文生图）
  listWorkflows: () => client.get('/workflows/'),
  // 用户需求收集
  createRequirement: (data) => client.post('/requirements/', data),
  listRequirements: (params) => client.get('/requirements/', { params }),
}

export default client
