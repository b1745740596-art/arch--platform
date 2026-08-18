import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(undefined)

  async function fetchMe(force = false) {
    if (user.value !== undefined && !force) return user.value
    try {
      user.value = await api.getMe()
    } catch {
      user.value = null
    }
    return user.value
  }

  async function login(data) {
    user.value = await api.login(data)
    return user.value
  }

  async function phoneLogin(data) {
    user.value = await api.phoneLogin(data)
    return user.value
  }

  async function emailLogin(data) {
    user.value = await api.emailLogin(data)
    return user.value
  }

  async function register(data) {
    return api.register(data)
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      user.value = null
    }
  }

  return { user, fetchMe, login, phoneLogin, emailLogin, register, logout }
})
