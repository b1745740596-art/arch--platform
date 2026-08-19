/** 运行环境识别工具。 */
export function isNativeApp() {
  if (typeof window === 'undefined') return false
  if (window.Capacitor?.isNativePlatform?.()) return true
  return (
    window.matchMedia?.('(display-mode: standalone)').matches === true ||
    window.navigator?.standalone === true
  )
}

/** App 端的默认落地页：打开后直接进入核心生成能力。 */
export function appDefaultRoute() {
  return isNativeApp() ? '/my-home' : '/'
}

/** 读取原生壳版本号；非原生环境或插件不可用时返回 0.0.0。 */
export async function getAppVersion() {
  if (typeof window === 'undefined') return '0.0.0'
  const app = window.Capacitor?.Plugins?.App
  if (app?.getInfo) {
    try {
      const info = await app.getInfo()
      return info?.version || '0.0.0'
    } catch {
      return '0.0.0'
    }
  }
  return '0.0.0'
}

/** 简单的三段式版本比较：latest 大于 current 返回正数。 */
export function compareVersions(latest, current) {
  const left = String(latest || '0.0.0').replace(/^v/, '').split('.')
  const right = String(current || '0.0.0').replace(/^v/, '').split('.')
  for (let index = 0; index < 3; index += 1) {
    const delta = Number.parseInt(left[index] || '0', 10) - Number.parseInt(right[index] || '0', 10)
    if (delta) return delta
  }
  return 0
}

/** 是否有比当前原生壳更新的版本。 */
export function hasNewVersion(latest, current) {
  return compareVersions(latest, current) > 0
}