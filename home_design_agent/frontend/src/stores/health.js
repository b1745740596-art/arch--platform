import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export const useHealthStore = defineStore('health', () => {
  const status = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function check() {
    loading.value = true
    error.value = null
    try {
      status.value = await api.health()
    } catch (e) {
      error.value = e.message || String(e)
    } finally {
      loading.value = false
    }
  }

  return { status, loading, error, check }
})
