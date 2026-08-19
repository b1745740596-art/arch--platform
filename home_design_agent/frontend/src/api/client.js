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

// 用户系统独立实例：与设计域接口分开，便于后续拆分/替换认证域。
const usersClient = axios.create({
  baseURL: '/api/users',
  timeout: 360000,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  withCredentials: true,
})

usersClient.interceptors.request.use((config) => {
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

usersClient.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
)

// 支付与额度独立实例：/api/payments
const paymentsClient = axios.create({
  baseURL: '/api/payments',
  timeout: 60000,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  withCredentials: true,
})

paymentsClient.interceptors.request.use((config) => {
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

paymentsClient.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
)

export const api = {
  health: () => client.get('/health/'),
  appVersion: () => client.get('/app-version/'),
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
  // 「我的家」报告书与项目订单
  saveReport: (data) => client.post('/reports/', data),
  listReports: () => client.get('/reports/'),
  getReport: (id) => client.get(`/reports/${id}/`),
  createOrder: (data) => client.post('/orders/', data),
  listOrders: () => client.get('/orders/'),
  // 用户端账号
  register: (data) => client.post('/auth/register/', data),
  login: (data) => client.post('/auth/login/', data),
  logout: () => client.post('/auth/logout/'),
  getMe: () => client.get('/auth/me/'),
  // 用户系统：个人资料 / 密码
  getProfile: () => usersClient.get('/me/'),
  updateProfile: (data) => usersClient.patch('/me/', data),
  changePassword: (data) => usersClient.post('/change-password/', data),
  requestPasswordReset: (data) => usersClient.post('/password-reset/', data),
  confirmPasswordReset: (data) => usersClient.post('/password-reset/confirm/', data),
  // 手机号绑定 / 验证码登录
  sendPhoneBindCode: (phone) => usersClient.post('/phone/bind-code/', { phone }),
  bindPhone: (data) => usersClient.post('/phone/bind/', data),
  sendPhoneLoginCode: (phone) => usersClient.post('/phone/login-code/', { phone }),
  phoneLogin: (data) => usersClient.post('/phone/login/', data),
  // 邮箱验证 / 验证码登录
  sendEmailBindCode: (email) => usersClient.post('/email/bind-code/', { email }),
  bindEmail: (data) => usersClient.post('/email/bind/', data),
  sendEmailLoginCode: (email) => usersClient.post('/email/login-code/', { email }),
  emailLogin: (data) => usersClient.post('/email/login/', data),
  // 持久登录令牌
  createRememberToken: () => usersClient.post('/remember/'),
  tokenLogin: (token) => usersClient.post('/token-login/', { token }),
  revokeRememberToken: (token) => usersClient.delete('/remember/', { data: { token } }),
  // 后台用户管理（staff/superuser）
  listAdminUsers: (params) => usersClient.get('/admin/users/', { params }),
  createAdminUser: (data) => usersClient.post('/admin/users/', data),
  updateAdminUser: (id, data) => usersClient.patch(`/admin/users/${id}/`, data),
  deleteAdminUser: (id) => usersClient.delete(`/admin/users/${id}/`),
  getAdminUserCredits: (id) => paymentsClient.get(`/admin/users/${id}/credits/`),
  setAdminUserCredits: (id, data) => paymentsClient.post(`/admin/users/${id}/credits/`, data),
  adjustAdminUserCredits: (id, data) => paymentsClient.post(`/admin/users/${id}/credits/adjust/`, data),
  // 支付与额度
  listPlans: () => paymentsClient.get('/plans/'),
  getBalance: () => paymentsClient.get('/balance/'),
  listTransactions: () => paymentsClient.get('/transactions/'),
  createPaymentOrder: (data) => paymentsClient.post('/orders/', data),
  listPaymentOrders: () => paymentsClient.get('/orders/'),
  getPaymentOrder: (id) => paymentsClient.get(`/orders/${id}/`),
  mockPayOrder: (id) => paymentsClient.post(`/orders/${id}/mock_pay/`),
  listAdminPaymentOrders: (params) => paymentsClient.get('/admin/orders/', { params }),
  getAdminPaymentStats: () => paymentsClient.get('/admin/stats/'),
  getAdminPaymentDiagnostics: () => paymentsClient.get('/admin/diagnostics/'),
  adminMarkPaid: (id, data) => paymentsClient.post(`/admin/orders/${id}/mark-paid/`, data),
}

export default client
