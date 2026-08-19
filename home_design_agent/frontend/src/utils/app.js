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