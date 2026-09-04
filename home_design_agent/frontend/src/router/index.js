import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { appDefaultRoute } from '@/utils/app'

const routes = [
  { path: '/', redirect: '/my-home' },
  { path: '/my-home', name: 'my-home', component: () => import('@/views/MyHomeView.vue') },
  { path: '/render', name: 'render', component: () => import('@/views/RenderView.vue') },
  {
    path: '/studio',
    name: 'studio',
    redirect: (to) => ({ path: '/my-home', query: to.query, hash: to.hash }),
  },
  {
    path: '/community/:id',
    name: 'community-post',
    component: () => import('@/views/CommunityPostView.vue'),
  },
  { path: '/intake', name: 'intake', component: () => import('@/views/IntakeView.vue') },
  { path: '/projects', name: 'projects', component: () => import('@/views/ProjectsView.vue') },
  { path: '/requirement', name: 'requirement', component: () => import('@/views/RequirementView.vue') },
  { path: '/talk', name: 'talk', component: () => import('@/views/TalkView.vue') },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/account', name: 'account', component: () => import('@/views/AccountView.vue') },
  { path: '/billing', name: 'billing', component: () => import('@/views/BillingView.vue') },
  { path: '/forgot-password', name: 'forgot-password', component: () => import('@/views/ForgotPasswordView.vue') },
  { path: '/reset-password', name: 'reset-password', component: () => import('@/views/ResetPasswordView.vue') },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/AdminUsersView.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/admin/payments',
    name: 'admin-payments',
    component: () => import('@/views/AdminPaymentsView.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/projects/:id',
    name: 'project-detail',
    component: () => import('@/views/ProjectDetailView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const PUBLIC_PATHS = ['/login', '/register', '/forgot-password', '/reset-password']

router.beforeEach(async (to) => {
  if (PUBLIC_PATHS.includes(to.path)) return true
  const auth = useAuthStore()
  const user = await auth.restoreSession()
  if (!user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !user.is_staff && !user.is_superuser) {
    return { path: appDefaultRoute(), replace: true }
  }
  return true
})

export default router
