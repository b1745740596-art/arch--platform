import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { Capacitor } from '@capacitor/core'
import { api } from '@/api/client'
import { getAppVersion, hasNewVersion, isNativeApp } from '@/utils/app'
import ApkUpdater from '@/plugins/apk-updater'

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

  function openBrowserDownload(url) {
    const link = document.createElement('a')
    link.href = url
    link.target = '_blank'
    link.rel = 'noopener'
    link.download = 'arch-ai.apk'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  async function downloadLatest() {
    if (!latest.value?.apk_url) return
    const url = new URL(latest.value.apk_url, window.location.origin).href
    if (!Capacitor.isNativePlatform()) {
      openBrowserDownload(url)
      return
    }

    let fallbackReason = 'plugin_unavailable'
    if (Capacitor.isPluginAvailable('ApkUpdater')) {
      try {
        const result = await ApkUpdater.downloadAndInstall({ url })
        console.info('[ApkUpdater] result=started', {
          status: result?.value || 'unknown',
          urlHost: new URL(url).host,
        })
        return
      } catch (cause) {
        fallbackReason = cause?.code || 'plugin_error'
        console.error('[ApkUpdater] result=error', {
          code: cause?.code || 'UNKNOWN',
          message: cause?.message || String(cause),
        })
      }
    }

    const externalUrl = latest.value.external_apk_url
    if (!externalUrl) {
      error.value = 'APK updater is unavailable and no external download URL is configured'
      console.error('[ApkUpdater] result=fallback_unavailable', { reason: fallbackReason })
      return
    }
    const fallbackUrl = new URL(externalUrl, window.location.origin).href
    console.info('[ApkUpdater] result=external_fallback', {
      reason: fallbackReason,
      urlHost: new URL(fallbackUrl).host,
    })
    window.location.assign(fallbackUrl)
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
