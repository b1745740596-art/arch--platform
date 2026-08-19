import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

const REMEMBER_KEY = 'arch_ai_remember_token'

function readRememberToken() {
  try {
    return localStorage.getItem(REMEMBER_KEY)
  } catch {
    return null
  }
}

function saveRememberToken(token) {
  try {
    localStorage.setItem(REMEMBER_KEY, token)
  } catch {
    // 忽略 localStorage 不可用（例如无痕模式）
  }
}

function clearRememberToken() {
  try {
    localStorage.removeItem(REMEMBER_KEY)
  } catch {
    // 忽略
  }
}

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

  async function persistLogin() {
    try {
      const data = await api.createRememberToken()
      if (data?.token) saveRememberToken(data.token)
    } catch {
      // 创建持久令牌失败不阻断登录
    }
  }

  async function login(data) {
    user.value = await api.login(data)
    await persistLogin()
    return user.value
  }

  async function phoneLogin(data) {
    user.value = await api.phoneLogin(data)
    await persistLogin()
    return user.value
  }

  async function emailLogin(data) {
    user.value = await api.emailLogin(data)
    await persistLogin()
    return user.value
  }

  async function restoreSession() {
    if (user.value !== undefined && user.value) return user.value

    try {
      user.value = await api.getMe()
      if (user.value) return user.value
    } catch {
      user.value = null
    }

    const token = readRememberToken()
    if (!token) {
      user.value = null
      return null
    }

    try {
      user.value = await api.tokenLogin(token)
      return user.value
    } catch {
      clearRememberToken()
      user.value = null
      return null
    }
  }

  async function register(data) {
    return api.register(data)
  }

  async function logout() {
    const token = readRememberToken()
    if (token) {
      try {
        await api.revokeRememberToken(token)
      } catch {
        // 会话可能已经失效，忽略注销令牌失败
      }
    }
    clearRememberToken()
    try {
      await api.logout()
    } finally {
      user.value = null
    }
  }

  return { user, fetchMe, restoreSession, login, phoneLogin, emailLogin, register, logout }
})

