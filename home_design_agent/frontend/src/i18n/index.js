import { computed, ref } from 'vue'
import { createI18n } from 'vue-i18n'
import elementZhCn from 'element-plus/es/locale/lang/zh-cn'
import elementEn from 'element-plus/es/locale/lang/en'
import zhCN from './zh-CN'
import enUS from './en-US'
import { translateTerm } from './terms'

export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', label: '中文', short: '中' },
  { value: 'en-US', label: 'English', short: 'EN' },
]

const STORAGE_KEY = 'archai.locale'
const DEFAULT_LOCALE = 'zh-CN'

function detectLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && SUPPORTED_LOCALES.some((l) => l.value === saved)) return saved
  } catch {
    // localStorage 不可用（隐身模式等）时退回默认语言
  }
  const nav = (navigator.language || '').toLowerCase()
  if (nav && !nav.startsWith('zh')) return 'en-US'
  return DEFAULT_LOCALE
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: { 'zh-CN': zhCN, 'en-US': enUS },
})

const ELEMENT_LOCALES = { 'zh-CN': elementZhCn, 'en-US': elementEn }

export const currentLocale = ref(i18n.global.locale.value)
export const elementLocale = computed(() => ELEMENT_LOCALES[currentLocale.value] || elementZhCn)

export function setLocale(locale) {
  if (!SUPPORTED_LOCALES.some((l) => l.value === locale)) return
  i18n.global.locale.value = locale
  currentLocale.value = locale
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // 持久化失败不影响本次切换
  }
  document.documentElement.setAttribute('lang', locale)
}

/** 组合式便捷方法：把后端中文术语按当前语言转换 */
export function useTerm() {
  return (value) => translateTerm(value, currentLocale.value)
}

/** 非组件上下文（store / 工具函数）中取翻译函数 */
export function t(key, params) {
  return i18n.global.t(key, params || {})
}

export function term(value) {
  return translateTerm(value, currentLocale.value)
}

document.documentElement.setAttribute('lang', i18n.global.locale.value)
