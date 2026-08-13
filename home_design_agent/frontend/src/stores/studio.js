import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { api } from '@/api/client'
import { t } from '@/i18n'
import {
  DEFAULT_IMAGE_RULES,
  DEFAULT_MAX_MODULES,
  DEFAULT_REQUIREMENT_MAX_LENGTH,
  DEFAULT_VARIANT_MAX,
  validateEnum,
  validateRequirement,
} from '@/utils/validation'

// 多窗口工作台的窗口上限与生成并发上限
export const MAX_WINDOWS = 6
export const MAX_CONCURRENT = 3

// 窗口状态机：draft(草稿) → validating(校验中) → queued(排队中) → running(生成中) → success / failed
// label 通过 i18n key 惰性取值，切换语言后随之更新
export const STATUS_META = {
  draft: { key: 'status.draft', type: 'info' },
  validating: { key: 'status.validating', type: 'warning' },
  queued: { key: 'status.queued', type: 'warning' },
  running: { key: 'status.running', type: 'primary' },
  success: { key: 'status.success', type: 'success' },
  failed: { key: 'status.failed', type: 'danger' },
}

// 后端 options 接口不可用时的兜底枚举，保证页面仍可用
export const FALLBACK_OPTIONS = {
  room_types: ['客厅', '主卧', '次卧', '厨房', '卫生间', '书房', '餐厅'],
  styles: ['现代简约', '现代轻奢', '意式极简', '北欧', '中式', '日式'],
  budget_tiers: ['经济', '品质', '高端'],
  modules: [],
  groups: [],
  constraints: {
    requirement_max_length: DEFAULT_REQUIREMENT_MAX_LENGTH,
    image: { ...DEFAULT_IMAGE_RULES },
    max_modules: DEFAULT_MAX_MODULES,
    variant_max: DEFAULT_VARIANT_MAX,
  },
}

let seq = 0
function nextId() {
  seq += 1
  return seq
}

let titleSeq = 0

function createWindow(preset = {}) {
  return {
    id: nextId(),
    title: '',
    status: 'draft',
    // 表单
    form: {
      room_type: preset.room_type || '',
      style: preset.style || '',
      budget_tier: preset.budget_tier || '',
      requirement: preset.requirement || '',
    },
    moduleCodes: Array.isArray(preset.moduleCodes) ? [...preset.moduleCodes] : [],
    // 生图工作流 id（空则由后端用默认工作流）
    workflowId: preset.workflowId ?? null,
    // 图片（复制窗口时不复制图片）
    file: null,
    previewUrl: '',
    imageMeta: null,
    imageErrors: [],
    // 发散建议
    variants: [],
    variantLoading: false,
    variantHint: '',
    // 运行态
    result: null,
    error: '',
    elapsed: 0,
    startedAt: 0,
    projectId: null,
  }
}

export const useStudioStore = defineStore('studio', () => {
  const windows = reactive([])
  const options = ref({ ...FALLBACK_OPTIONS })
  const optionsLoading = ref(false)
  const optionsDegraded = ref(false)
  const optionsError = ref('')
  // 生图工作流（后台编排，前端只读展示与选择）
  const workflows = ref([])

  // 等待执行的窗口 id 队列（FIFO）
  const queue = reactive([])
  // 正在生成中的窗口 id
  const running = reactive(new Set())
  const runningCount = ref(0)
  // 每个窗口的 AbortController，用于关闭窗口时取消请求
  const controllers = new Map()
  let timer = null

  const constraints = computed(() => ({
    ...FALLBACK_OPTIONS.constraints,
    ...(options.value.constraints || {}),
    image: { ...DEFAULT_IMAGE_RULES, ...((options.value.constraints || {}).image || {}) },
  }))
  const imageRules = computed(() => constraints.value.image)
  const requirementMaxLength = computed(
    () => constraints.value.requirement_max_length || DEFAULT_REQUIREMENT_MAX_LENGTH,
  )
  const maxModules = computed(() => constraints.value.max_modules || DEFAULT_MAX_MODULES)
  const variantMax = computed(() => constraints.value.variant_max || DEFAULT_VARIANT_MAX)

  const modules = computed(() => options.value.modules || [])
  const groups = computed(() => {
    const declared = options.value.groups || []
    // 若某些模块的 group 未在 groups 中声明，补一个宽松分组，避免选项渲染丢失
    const extra = []
    for (const m of modules.value) {
      const key = m.group || 'other'
      if (!declared.some((g) => g.key === key) && !extra.some((g) => g.key === key)) {
        extra.push({ key, label: m.group_display || t('studio.otherGroup'), multiple: true, max_select: null })
      }
    }
    return [...declared, ...extra]
  })
  const modulesByGroup = computed(() =>
    groups.value.map((g) => ({
      ...g,
      modules: modules.value.filter((m) => (m.group || 'other') === g.key),
    })).filter((g) => g.modules.length > 0),
  )

  const canAddWindow = computed(() => windows.length < MAX_WINDOWS)
  const busyCount = computed(() => windows.filter((w) => w.status === 'running').length)
  const queuedCount = computed(() => windows.filter((w) => w.status === 'queued').length)

  function defaultPreset() {
    return {
      room_type: options.value.room_types?.[0] || '',
      style: options.value.styles?.[0] || '',
      budget_tier: options.value.budget_tiers?.[1] || options.value.budget_tiers?.[0] || '',
      moduleCodes: modules.value.filter((m) => m.is_default).map((m) => m.code),
      workflowId: defaultWorkflowId.value,
    }
  }

  // 默认工作流：后端标记 is_default 的那条；取不到则不下发，由后端兜底
  const defaultWorkflowId = computed(() => {
    const list = workflows.value
    return (list.find((w) => w.is_default) || list[0] || {}).id ?? null
  })

  function workflowById(id) {
    return workflows.value.find((w) => w.id === id) || null
  }

  // ------------------------------------------------------------ 选项加载

  async function loadOptions() {
    optionsLoading.value = true
    optionsError.value = ''
    try {
      const [data] = await Promise.all([api.getPromptOptions(), loadWorkflows()])
      options.value = {
        room_types: data.room_types?.length ? data.room_types : FALLBACK_OPTIONS.room_types,
        styles: data.styles?.length ? data.styles : FALLBACK_OPTIONS.styles,
        budget_tiers: data.budget_tiers?.length ? data.budget_tiers : FALLBACK_OPTIONS.budget_tiers,
        modules: data.modules || [],
        groups: data.groups || [],
        constraints: data.constraints || FALLBACK_OPTIONS.constraints,
      }
      optionsDegraded.value = false
    } catch (e) {
      // 接口 404 / 报错时降级到内置枚举，页面保持可用
      options.value = { ...FALLBACK_OPTIONS }
      optionsDegraded.value = true
      optionsError.value =
        e?.response?.status === 404 ? t('studio.optionsOffline') : e.message || String(e)
    } finally {
      optionsLoading.value = false
      // 用最新枚举补齐已存在窗口的空表单项
      for (const w of windows) {
        const preset = defaultPreset()
        if (!w.form.room_type) w.form.room_type = preset.room_type
        if (!w.form.style) w.form.style = preset.style
        if (!w.form.budget_tier) w.form.budget_tier = preset.budget_tier
        if (w.workflowId == null) w.workflowId = preset.workflowId
      }
    }
  }

  /** 工作流列表取不到时静默降级：不下发 workflow，由后端使用默认工作流 */
  async function loadWorkflows() {
    try {
      const data = await api.listWorkflows()
      workflows.value = Array.isArray(data) ? data : data?.results || []
    } catch (e) {
      workflows.value = []
    }
  }

  // ------------------------------------------------------------ 窗口增删改

  function addWindow(preset) {
    if (!canAddWindow.value) return null
    const win = createWindow({ ...defaultPreset(), ...(preset || {}) })
    titleSeq += 1
    win.title = t('studio.windowSeq', { seq: titleSeq })
    windows.push(win)
    return win
  }

  /** 复制窗口：复制表单参数与发散选项，不复制图片 */
  function duplicateWindow(id) {
    const src = windows.find((w) => w.id === id)
    if (!src || !canAddWindow.value) return null
    const win = addWindow({
      room_type: src.form.room_type,
      style: src.form.style,
      budget_tier: src.form.budget_tier,
      requirement: src.form.requirement,
      moduleCodes: [...src.moduleCodes],
      workflowId: src.workflowId,
    })
    if (win) win.title = t('studio.windowCopy', { title: src.title })
    return win
  }

  function closeWindow(id) {
    const idx = windows.findIndex((w) => w.id === id)
    if (idx < 0) return
    const win = windows[idx]
    // 释放预览 URL、取消进行中的请求、移出队列
    releasePreview(win)
    const controller = controllers.get(id)
    if (controller) {
      controller.abort()
      controllers.delete(id)
    }
    if (running.has(id)) {
      running.delete(id)
      runningCount.value = running.size
    }
    const qi = queue.indexOf(id)
    if (qi >= 0) queue.splice(qi, 1)
    windows.splice(idx, 1)
    pump()
  }

  function releasePreview(win) {
    if (win?.previewUrl) {
      URL.revokeObjectURL(win.previewUrl)
      win.previewUrl = ''
    }
  }

  function setImage(id, file, meta) {
    const win = windows.find((w) => w.id === id)
    if (!win) return
    releasePreview(win)
    win.file = file || null
    win.imageMeta = meta || null
    win.previewUrl = file ? URL.createObjectURL(file) : ''
  }

  function clearImage(id) {
    setImage(id, null, null)
  }

  function resetAll() {
    for (const w of [...windows]) closeWindow(w.id)
  }

  // ------------------------------------------------------------ 校验

  /** 返回窗口的「待修正项」列表 */
  function windowIssues(win) {
    const issues = []
    if (!win.file) issues.push(t('validation.imageMissing'))
    if (win.imageErrors?.length) issues.push(...win.imageErrors)
    issues.push(...validateEnum(win.form.room_type, options.value.room_types, t('studio.fieldRoom')))
    issues.push(...validateEnum(win.form.style, options.value.styles, t('studio.fieldStyle')))
    issues.push(...validateEnum(win.form.budget_tier, options.value.budget_tiers, t('studio.fieldBudget')))
    issues.push(...validateRequirement(win.form.requirement, requirementMaxLength.value))
    if (win.moduleCodes.length > maxModules.value) {
      issues.push(
        t('studio.moduleOverLimit', { max: maxModules.value, current: win.moduleCodes.length }),
      )
    }
    return issues
  }

  function isSubmittable(win) {
    return windowIssues(win).length === 0 && !['queued', 'running', 'validating'].includes(win.status)
  }

  // ------------------------------------------------------------ 并发队列

  /** 入队：校验通过则进入排队，由 pump() 按并发上限调度 */
  function enqueue(id) {
    const win = windows.find((w) => w.id === id)
    if (!win) return false
    if (['queued', 'running'].includes(win.status)) return false
    if (windowIssues(win).length) return false
    win.status = 'queued'
    win.error = ''
    win.elapsed = 0
    if (!queue.includes(id)) queue.push(id)
    pump()
    return true
  }

  /** 全部提交：把所有校验通过的草稿/失败窗口一次性入队 */
  function enqueueAll() {
    let count = 0
    for (const win of windows) {
      if (['queued', 'running'].includes(win.status)) continue
      if (windowIssues(win).length) continue
      if (enqueue(win.id)) count += 1
    }
    return count
  }

  /** 调度器：只要并发未满且队列非空就取队首执行 */
  function pump() {
    while (running.size < MAX_CONCURRENT && queue.length > 0) {
      const id = queue.shift()
      const win = windows.find((w) => w.id === id)
      if (!win || win.status !== 'queued') continue
      void execute(win)
    }
    ensureTimer()
  }

  async function execute(win) {
    running.add(win.id)
    runningCount.value = running.size
    win.status = 'running'
    win.startedAt = Date.now()
    win.elapsed = 0
    win.error = ''
    ensureTimer()

    const controller = new AbortController()
    controllers.set(win.id, controller)

    try {
      const projectId = await ensureProject(win, controller.signal)
      const fd = new FormData()
      fd.append('project', projectId)
      fd.append('room_type', win.form.room_type)
      fd.append('style', win.form.style)
      fd.append('budget_tier', win.form.budget_tier)
      fd.append('requirement', win.form.requirement || '')
      fd.append('raw_photo', win.file)
      if (win.moduleCodes.length) {
        fd.append('module_codes', win.moduleCodes.join(','))
      }
      if (win.workflowId != null) {
        fd.append('workflow', win.workflowId)
      }
      const res = await api.createRender(fd, { signal: controller.signal })
      win.result = res
      if (res?.status === 'failed') {
        win.status = 'failed'
        win.error = res.error || t('studio.genFailed')
      } else {
        win.status = 'success'
      }
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') {
        // 窗口已关闭，无需回写状态
        return
      }
      win.status = 'failed'
      win.error = extractError(e)
    } finally {
      controllers.delete(win.id)
      running.delete(win.id)
      runningCount.value = running.size
      if (win.startedAt) {
        win.elapsed = Math.max(0, Math.round((Date.now() - win.startedAt) / 1000))
      }
      // 前面完成后自动出队执行下一个
      pump()
    }
  }

  async function ensureProject(win, signal) {
    if (win.projectId) return win.projectId
    const project = await api.createProject(
      { title: t('render.projectTitle', { room: win.form.room_type, style: win.form.style }) },
      { signal },
    )
    win.projectId = project.id
    return project.id
  }

  /** 重试：已有 render 则调 regenerate，否则重新入队提交 */
  async function retry(id) {
    const win = windows.find((w) => w.id === id)
    if (!win) return
    if (!win.result?.id) {
      enqueue(id)
      return
    }
    if (running.size >= MAX_CONCURRENT) {
      enqueue(id)
      return
    }
    running.add(win.id)
    runningCount.value = running.size
    win.status = 'running'
    win.startedAt = Date.now()
    win.elapsed = 0
    win.error = ''
    ensureTimer()
    const controller = new AbortController()
    controllers.set(win.id, controller)
    try {
      const res = await api.regenerateRender(win.result.id, { signal: controller.signal })
      win.result = res
      if (res?.status === 'failed') {
        win.status = 'failed'
        win.error = res.error || t('studio.genFailed')
      } else {
        win.status = 'success'
      }
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
      win.status = 'failed'
      win.error = extractError(e)
    } finally {
      controllers.delete(win.id)
      running.delete(win.id)
      runningCount.value = running.size
      win.elapsed = Math.max(0, Math.round((Date.now() - win.startedAt) / 1000))
      pump()
    }
  }

  function extractError(e) {
    const data = e?.response?.data
    if (data) {
      if (typeof data === 'string') return data
      if (data.detail) return String(data.detail)
      if (data.error) return String(data.error)
      const first = Object.entries(data)[0]
      if (first) return `${first[0]}: ${[].concat(first[1]).join('; ')}`
    }
    if (e?.code === 'ECONNABORTED') return t('studio.timeout')
    return e?.message || String(e)
  }

  // ------------------------------------------------------------ 计时器

  // 单一定时器统一驱动所有「生成中」窗口的耗时秒数
  function ensureTimer() {
    const active = windows.some((w) => w.status === 'running')
    if (active && !timer) {
      timer = setInterval(() => {
        let stillActive = false
        for (const w of windows) {
          if (w.status === 'running' && w.startedAt) {
            w.elapsed = Math.max(0, Math.round((Date.now() - w.startedAt) / 1000))
            stillActive = true
          }
        }
        if (!stillActive) stopTimer()
      }, 1000)
    } else if (!active && timer) {
      stopTimer()
    }
  }

  function stopTimer() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  /**
   * 离开页面时清理：停表、取消进行中的请求、释放预览 URL。
   * store 是应用级单例，被中断的窗口回落为草稿，避免再次进入时卡在「生成中」。
   */
  function dispose() {
    stopTimer()
    for (const controller of controllers.values()) controller.abort()
    controllers.clear()
    running.clear()
    runningCount.value = 0
    queue.splice(0, queue.length)
    for (const w of windows) {
      releasePreview(w)
      if (['running', 'queued', 'validating'].includes(w.status)) {
        w.status = 'draft'
        w.startedAt = 0
        w.elapsed = 0
      }
    }
  }

  /** 重新进入页面时，为仍持有文件的窗口重建预览 URL */
  function rehydratePreviews() {
    for (const w of windows) {
      if (w.file && !w.previewUrl) {
        w.previewUrl = URL.createObjectURL(w.file)
      }
    }
  }

  // ------------------------------------------------------------ 发散建议

  async function fetchVariants(id) {
    const win = windows.find((w) => w.id === id)
    if (!win) return
    win.variantLoading = true
    win.variantHint = ''
    try {
      const data = await api.suggestPromptVariants({
        room_type: win.form.room_type,
        style: win.form.style,
        budget_tier: win.form.budget_tier,
      })
      const list = (data?.variants || []).slice(0, variantMax.value)
      win.variants = list
      if (!list.length) win.variantHint = t('studio.noVariants')
    } catch (e) {
      win.variants = []
      win.variantHint =
        e?.response?.status === 404
          ? t('studio.variantsOffline')
          : t('studio.variantsFailed', { msg: extractError(e) })
    } finally {
      win.variantLoading = false
    }
  }

  return {
    // state
    windows,
    options,
    optionsLoading,
    optionsDegraded,
    optionsError,
    workflows,
    queue,
    runningCount,
    // computed
    constraints,
    imageRules,
    requirementMaxLength,
    maxModules,
    variantMax,
    modules,
    groups,
    modulesByGroup,
    canAddWindow,
    busyCount,
    queuedCount,
    defaultWorkflowId,
    // actions
    loadOptions,
    loadWorkflows,
    workflowById,
    addWindow,
    duplicateWindow,
    closeWindow,
    setImage,
    clearImage,
    releasePreview,
    resetAll,
    windowIssues,
    isSubmittable,
    enqueue,
    enqueueAll,
    retry,
    fetchVariants,
    dispose,
    rehydratePreviews,
    defaultPreset,
    MAX_WINDOWS,
    MAX_CONCURRENT,
  }
})
