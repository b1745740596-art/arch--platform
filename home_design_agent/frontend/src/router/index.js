import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/render', name: 'render', component: () => import('@/views/RenderView.vue') },
  { path: '/studio', name: 'studio', component: () => import('@/views/StudioView.vue') },
  { path: '/intake', name: 'intake', component: () => import('@/views/IntakeView.vue') },
  { path: '/projects', name: 'projects', component: () => import('@/views/ProjectsView.vue') },
  { path: '/requirement', name: 'requirement', component: () => import('@/views/RequirementView.vue') },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
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

const PUBLIC_PATHS = ['/', '/login', '/register']

router.beforeEach(async (to) => {
  if (PUBLIC_PATHS.includes(to.path)) return true
  const auth = useAuthStore()
  const user = await auth.fetchMe()
  if (!user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
