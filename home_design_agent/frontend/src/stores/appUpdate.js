import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import { getAppVersion, hasNewVersion, isNativeApp } from '@/utils/app'

export const useAppUpdateStore = defineStore('appUpdate', () => {
  const loading = ref(false)
  const checked = ref(false)
  const currentVersion = ref('0.0.0')
  const latest = ref(null)
  const error = ref('')

  const updateAvailable = computed(
    () => Boolean(latest.value) && hasNewVersion(latest.value.version, currentVersion.value),
  )

  async function check() {
    if (!isNativeApp()) return null
    loading.value = true
    error.value = ''
    try {
      currentVersion.value = await getAppVersion()
      latest.value = await api.appVersion()
      checked.value = true
      return latest.value
    } catch (e) {
      error.value = e?.message || String(e)
      return null
    } finally {
      loading.value = false
    }
  }

  function downloadLatest() {
    if (!latest.value?.apk_url) return
    const url = new URL(latest.value.apk_url, window.location.origin).href
    // 原生壳内 WebView 不会触发 <a download> 下载，交给系统浏览器打开下载地址。
    if (isNativeApp()) {
      window.open(url, '_system', 'location=yes')
      return
    }
    const link = document.createElement('a')
    link.href = url
    link.target = '_blank'
    link.rel = 'noopener'
    link.download = 'arch-ai.apk'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return {
    loading,
    checked,
    currentVersion,
    latest,
    error,
    updateAvailable,
    check,
    downloadLatest,
  }
})