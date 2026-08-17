import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export const useAccountStore = defineStore('account', () => {
  const profile = ref(undefined)
  const loading = ref(false)

  async function fetchProfile(force = false) {
    if (profile.value !== undefined && !force) return profile.value
    loading.value = true
    try {
      profile.value = await api.getProfile()
    } finally {
      loading.value = false
    }
    return profile.value
  }

  async function updateProfile(data) {
    profile.value = await api.updateProfile(data)
    return profile.value
  }

  async function changePassword(data) {
    return api.changePassword(data)
  }

  async function requestPasswordReset(data) {
    return api.requestPasswordReset(data)
  }

  async function confirmPasswordReset(data) {
    return api.confirmPasswordReset(data)
  }

  return {
    profile,
    loading,
    fetchProfile,
    updateProfile,
    changePassword,
    requestPasswordReset,
    confirmPasswordReset,
  }
})
