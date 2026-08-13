// 输入校验工具：图片真实像素校验 + 需求描述文本安全校验 + 枚举白名单校验。
// 所有函数返回当前语言的错误文案（经 i18n），供窗口内「待修正项」列表与 ElMessage 使用。
import { t } from '@/i18n'

// 与后端 constraints 对齐的默认值（后端 options 接口未就绪时的兜底）
export const DEFAULT_IMAGE_RULES = {
  max_bytes: 10 * 1024 * 1024,
  min_bytes: 10 * 1024,
  allowed_types: ['image/jpeg', 'image/png', 'image/webp'],
  min_side: 512,
  max_side: 8000,
  max_aspect_ratio: 3.0,
}

export const DEFAULT_REQUIREMENT_MAX_LENGTH = 300
export const DEFAULT_MAX_MODULES = 6
export const DEFAULT_VARIANT_MAX = 4

const TYPE_LABEL = {
  'image/jpeg': 'JPG',
  'image/png': 'PNG',
  'image/webp': 'WebP',
}

export function formatBytes(bytes) {
  if (bytes == null) return '—'
  if (bytes >= 1024 * 1024) {
    const mb = bytes / 1024 / 1024
    return (bytes % (1024 * 1024) === 0 ? mb.toFixed(0) : mb.toFixed(1)) + 'MB'
  }
  return Math.round(bytes / 1024) + 'KB'
}

export function describeImageRules(rules = DEFAULT_IMAGE_RULES) {
  const r = { ...DEFAULT_IMAGE_RULES, ...(rules || {}) }
  const types = (r.allowed_types || []).map((type) => TYPE_LABEL[type] || type).join('/')
  return t('validation.imageRules', {
    types,
    minBytes: formatBytes(r.min_bytes),
    maxBytes: formatBytes(r.max_bytes),
    minSide: r.min_side,
    maxSide: r.max_side,
  })
}

// ---------------------------------------------------------------- 文本安全校验

// 疑似个人信息：从更具体的形态开始匹配，保证提示文案准确
const PII_PATTERNS = [
  { re: /\d{17}[\dXx]/, hint: 'idcard' },
  { re: /[\w.+-]+@[\w-]+\.[\w.-]+/, hint: 'email' },
  { re: /1[3-9]\d{9}/, hint: 'mobile' },
  { re: /\d{3,4}[-\s]?\d{7,8}/, hint: 'phone' },
  { re: /(微信|weixin|wechat|qq)\s*[:：]?\s*[\w-]{5,}/i, hint: 'social' },
]

const URL_PATTERN = /(https?:\/\/|www\.)/i
const INJECTION_PATTERN = /[<>{}]/

/**
 * 校验需求描述，返回中文错误文案数组（空数组表示通过）。
 * requirement 为可选项：留空直接通过。
 */
export function validateRequirement(text, maxLength = DEFAULT_REQUIREMENT_MAX_LENGTH) {
  const errors = []
  const raw = text || ''
  const value = raw.trim()
  if (!value) return errors

  const limit = maxLength || DEFAULT_REQUIREMENT_MAX_LENGTH
  if (raw.length > limit) {
    errors.push(t('validation.reqTooLong', { limit, current: raw.length }))
  }
  const pii = PII_PATTERNS.find((p) => p.re.test(value))
  if (pii) {
    errors.push(t('validation.reqPii', { hint: t(`validation.pii.${pii.hint}`) }))
  }
  if (URL_PATTERN.test(value)) {
    errors.push(t('validation.reqUrl'))
  }
  if (INJECTION_PATTERN.test(value)) {
    errors.push(t('validation.reqInjection'))
  }
  return errors
}

// ---------------------------------------------------------------- 枚举白名单

/** 校验取值必须来自后端下发的枚举 */
export function validateEnum(value, allowed, label) {
  if (!value) return [t('validation.enumRequired', { label })]
  if (!Array.isArray(allowed) || allowed.length === 0) {
    // 枚举尚未加载完成时不阻塞，由页面统一提示「选项加载中」
    return []
  }
  if (!allowed.includes(value)) return [t('validation.enumInvalid', { label, value })]
  return []
}

// ---------------------------------------------------------------- 图片校验

/**
 * 读取图片真实像素尺寸（Image + createObjectURL，不依赖扩展名）。
 * 内部创建的临时 URL 一定会被 revoke。
 */
export function readImageSize(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const size = { width: img.naturalWidth, height: img.naturalHeight }
      URL.revokeObjectURL(url)
      resolve(size)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片无法解析，可能已损坏或不是有效的图片文件'))
    }
    img.src = url
  })
}

/**
 * 完整校验一张图片：MIME 白名单 → 体积区间 → 真实像素边长 → 宽高比。
 * @returns {Promise<{ok: boolean, errors: string[], meta?: object}>}
 */
export async function validateImageFile(file, rules = DEFAULT_IMAGE_RULES) {
  const r = { ...DEFAULT_IMAGE_RULES, ...(rules || {}) }
  const errors = []

  if (!file) return { ok: false, errors: [t('validation.imageMissing')] }

  const allowed = r.allowed_types && r.allowed_types.length ? r.allowed_types : DEFAULT_IMAGE_RULES.allowed_types
  if (!allowed.includes(file.type)) {
    const types = allowed.map((type) => TYPE_LABEL[type] || type).join(' / ')
    errors.push(t('validation.imageType', { types }))
    return { ok: false, errors }
  }
  if (file.size > r.max_bytes) {
    errors.push(t('validation.imageTooLarge', { max: formatBytes(r.max_bytes), current: formatBytes(file.size) }))
  }
  if (file.size < r.min_bytes) {
    errors.push(t('validation.imageTooSmall', { min: formatBytes(r.min_bytes), current: formatBytes(file.size) }))
  }
  if (errors.length) return { ok: false, errors }

  let size
  try {
    size = await readImageSize(file)
  } catch {
    return { ok: false, errors: [t('validation.imageBroken')] }
  }

  const { width, height } = size
  if (!width || !height) {
    return { ok: false, errors: [t('validation.imageBroken')] }
  }
  if (width < r.min_side || height < r.min_side) {
    errors.push(t('validation.imageSideSmall', { min: r.min_side, width, height }))
  }
  if (width > r.max_side || height > r.max_side) {
    errors.push(t('validation.imageSideLarge', { max: r.max_side, width, height }))
  }
  const maxRatio = Number(r.max_aspect_ratio) || DEFAULT_IMAGE_RULES.max_aspect_ratio
  const ratio = width / height
  if (ratio > maxRatio || ratio < 1 / maxRatio) {
    errors.push(t('validation.imageAspect', { max: maxRatio, current: ratio.toFixed(2) }))
  }

  return {
    ok: errors.length === 0,
    errors,
    meta: { width, height, size: file.size, type: file.type },
  }
}

// ---------------------------------------------------------------- 发散模块选择

/**
 * 判断某个模块能否再被勾选（分组 multiple / max_select + 全局 max_modules）。
 * 单选组返回 replace 数组，调用方据此做替换语义。
 * @returns {{allowed: boolean, reason?: string, replace?: string[]}}
 */
export function canSelectModule({ module, selectedCodes = [], modules = [], groups = [], maxModules }) {
  if (!module) return { allowed: false, reason: t('validation.moduleUnknown') }
  if (selectedCodes.includes(module.code)) return { allowed: true }

  const group = groups.find((g) => g.key === module.group)
  const sameGroupSelected = selectedCodes.filter((code) => {
    const m = modules.find((x) => x.code === code)
    return m && m.group === module.group
  })

  // 单选组：用替换语义，不占用新增额度
  if (group && group.multiple === false) {
    return { allowed: true, replace: sameGroupSelected }
  }

  const limit = maxModules || DEFAULT_MAX_MODULES
  if (selectedCodes.length >= limit) {
    return { allowed: false, reason: t('validation.moduleMax', { max: limit }) }
  }
  if (group && group.max_select && sameGroupSelected.length >= group.max_select) {
    return {
      allowed: false,
      reason: t('validation.moduleGroupMax', { group: group.label || group.key, max: group.max_select }),
    }
  }
  return { allowed: true }
}

/**
 * 按约束裁剪一组模块 code（用于套用 variant 建议时的安全过滤）。
 * @returns {{codes: string[], dropped: string[]}}
 */
export function clampModuleCodes(codes = [], { modules = [], groups = [], maxModules } = {}) {
  const accepted = []
  const dropped = []
  for (const code of codes) {
    const module = modules.find((m) => m.code === code)
    if (!module) {
      dropped.push(code)
      continue
    }
    const check = canSelectModule({ module, selectedCodes: accepted, modules, groups, maxModules })
    if (check.allowed) {
      if (check.replace && check.replace.length) {
        for (const old of check.replace) {
          const idx = accepted.indexOf(old)
          if (idx >= 0) accepted.splice(idx, 1)
        }
      }
      accepted.push(code)
    } else {
      dropped.push(code)
    }
  }
  return { codes: accepted, dropped }
}
