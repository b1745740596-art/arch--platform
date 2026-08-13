import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/render', name: 'render', component: () => import('@/views/RenderView.vue') },
  { path: '/studio', name: 'studio', component: () => import('@/views/StudioView.vue') },
  { path: '/intake', name: 'intake', component: () => import('@/views/IntakeView.vue') },
  { path: '/projects', name: 'projects', component: () => import('@/views/ProjectsView.vue') },
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

export default router
