<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useStudioStore } from '@/stores/studio'
import { useTerm } from '@/i18n'
import { resolveMediaUrl } from '@/utils/media'
import { clampModuleCodes, validateImageFile } from '@/utils/validation'
import { isNativeApp } from '@/utils/app'
import { Capacitor } from '@capacitor/core'
import CameraCapture from '@/plugins/camera-capture'
import DesignCoach from '@/components/DesignCoach.vue'

const router = useRouter()
const studio = useStudioStore()
const { t } = useI18n()
const term = useTerm()
const isApp = computed(() => isNativeApp())
const cameraInput = ref(null)
const galleryInput = ref(null)
const capturing = ref(false)

const steps = [
  { key: 'upload', labelKey: 'plan.stepUpload' },
  { key: 'config', labelKey: 'plan.stepConfig' },
  { key: 'review', labelKey: 'plan.stepReview' },
]

const step = ref(0)
const submitting = ref(false)
const records = ref([])
const recordsLoading = ref(false)
const batchJobs = ref([])
const projectId = ref(studio.sessionProjectId || null)
const projectName = ref('')
const selectedRecordId = ref(null)
const nameRequired = ref(false)
const designerVersion = ref(0)
let imageSequence = 0

const draft = reactive({
  plan_name: '',
  images: [],
  imageErrors: [],
  room_type: '',
  style: '',
  budget_tier: '',
  requirement: '',
  moduleCodes: [],
  workflowId: null,
})

const currentStep = computed(() => steps[step.value])
const selectedRecord = computed(
  () => records.value.find((record) => record.id === selectedRecordId.value) || records.value[0] || null,
)
const recordImageUrls = computed(() =>
  records.value
    .map((record) => resolveMediaUrl(record.result?.result_url))
    .filter(Boolean),
)
const furnitureImageUrls = computed(() =>
  (selectedRecord.value?.result?.furnitures || [])
    .map((item) => resolveMediaUrl(item.image_url))
    .filter(Boolean),
)

function applyDesignerPatch(patch) {
  if (!patch || typeof patch !== 'object') return
  if (Array.isArray(patch.image_rooms)) {
    for (const assignment of patch.image_rooms) {
      const image = draft.images.find((item) => String(item.id) === String(assignment?.image_id))
      if (image && studio.options.room_types.includes(assignment?.room_type)) {
        image.room_type = assignment.room_type
      }
    }
    draft.room_type = draft.images.find((image) => image.room_type)?.room_type || ''
  }
  if (studio.options.room_types.includes(patch.room_type)) draft.room_type = patch.room_type
  if (studio.options.styles.includes(patch.style)) draft.style = patch.style
  if (studio.options.budget_tiers.includes(patch.budget_tier)) draft.budget_tier = patch.budget_tier
  if (typeof patch.requirement === 'string') {
    draft.requirement = patch.requirement.slice(0, studio.requirementMaxLength)
  }
  if (Array.isArray(patch.module_codes)) {
    const { codes } = clampModuleCodes(patch.module_codes, {
      modules: studio.modules,
      groups: studio.groups,
      maxModules: studio.maxModules,
    })
    draft.moduleCodes = codes
  }
  if (patch.workflow_id != null && studio.workflows.some((item) => item.id === patch.workflow_id)) {
    draft.workflowId = patch.workflow_id
  }
}

function recordName(record) {
  return record.room_type ? term(record.room_type) : t('plan.unnamed')
}

function money(value) {
  return value == null ? t('common.dash') : '¥' + Number(value).toLocaleString()
}

function expectedWorkflowMode(record) {
  if (record?.workflow_mode) return record.workflow_mode
  const workflowId = record?.result?.workflow
  return workflowId == null ? '' : studio.workflowById(workflowId)?.mode || ''
}

function renderModeDowngraded(record) {
  return expectedWorkflowMode(record) === 'img2img' && record?.result?.render_mode === 'text2img'
}

function modeLabel(mode) {
  return mode === 'img2img' ? t('win.modeImg2Img') : t('win.modeText2Img')
}

function statusTagType(status) {
  return {
    queued: 'warning',
    running: 'primary',
    success: 'success',
    failed: 'danger',
  }[status] || 'info'
}

function renderToRecord(result) {
  const workflowMode = result?.workflow == null ? '' : studio.workflowById(result.workflow)?.mode || ''
  return {
    id: String(result.id),
    title: recordName(result),
    room_type: result.room_type,
    style: result.style,
    budget_tier: result.budget_tier,
    result,
    workflow_mode: workflowMode,
    created_at: result.created_at || new Date().toISOString(),
  }
}

function ensureDraftDefaults() {
  const preset = studio.defaultPreset()
  draft.plan_name = draft.plan_name || projectName.value
  draft.style = draft.style || preset.style
  draft.budget_tier = draft.budget_tier || preset.budget_tier
  if (draft.workflowId == null) draft.workflowId = preset.workflowId
}

onMounted(async () => {
  if (!projectId.value) projectId.value = studio.sessionProjectId || null
  await studio.loadOptions()
  ensureDraftDefaults()
  if (!projectId.value) return

  recordsLoading.value = true
  try {
    const [projectState, rendersState] = await Promise.allSettled([
      api.getProject(projectId.value),
      api.listRenders(projectId.value),
    ])
    if (
      projectState.status === 'rejected'
      && [403, 404].includes(projectState.reason?.response?.status)
    ) {
      projectId.value = null
      studio.sessionProjectId = null
      records.value = []
      return
    }
    if (rendersState.status === 'rejected') throw rendersState.reason

    const project = projectState.status === 'fulfilled' ? projectState.value : null
    const data = rendersState.value
    projectName.value = project?.title || ''
    const list = Array.isArray(data) ? data : data?.results || []
    records.value = list
      .filter((result) => result?.status === 'success')
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .map(renderToRecord)
    selectedRecordId.value = records.value[0]?.id || null
  } catch (error) {
    if ([403, 404].includes(error?.response?.status)) {
      projectId.value = null
      studio.sessionProjectId = null
      records.value = []
      return
    }
    const data = error?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : error.message)
    ElMessage.warning(t('plan.recordsLoadFailed', { msg }))
  } finally {
    recordsLoading.value = false
  }
})

function releaseDraftImages() {
  for (const image of draft.images) {
    if (image.url) URL.revokeObjectURL(image.url)
  }
  draft.images = []
}

function resetDraft() {
  releaseDraftImages()
  batchJobs.value = []
  draft.imageErrors = []
  draft.room_type = ''
  draft.style = ''
  draft.budget_tier = ''
  draft.requirement = ''
  draft.moduleCodes = []
  draft.workflowId = null
  designerVersion.value += 1
  ensureDraftDefaults()
}

function uploadValid() {
  return Boolean(
    draft.plan_name.trim()
    && draft.images.length
    && draft.images.every((image) => studio.options.room_types.includes(image.room_type))
    && !draft.imageErrors.length,
  )
}

function configValid() {
  return Boolean(draft.style && draft.budget_tier)
}

function stepValid() {
  if (step.value === 0) return uploadValid()
  if (step.value === 1) return configValid()
  return true
}

function nextStep() {
  if (step.value === 0) {
    if (!draft.plan_name.trim()) {
      nameRequired.value = true
      ElMessage.warning(t('plan.nameRequired'))
      return
    }
    nameRequired.value = false
  }
  if (!stepValid()) {
    ElMessage.warning(t('plan.stepIncomplete'))
    return
  }
  if (step.value < steps.length - 1) step.value += 1
}

function previousStep() {
  if (step.value > 0) step.value -= 1
}

function goToStep(index) {
  if (index < step.value) step.value = index
}

const MAX_UPLOAD_IMAGES = 8

async function addImage(raw) {
  if (!raw || submitting.value) return
  if (draft.images.length >= MAX_UPLOAD_IMAGES) {
    ElMessage.warning(t('plan.uploadLimit', { max: MAX_UPLOAD_IMAGES }))
    return
  }
  draft.imageErrors = []
  const { ok, errors, meta } = await validateImageFile(raw, studio.imageRules)
  if (!ok) {
    draft.imageErrors = errors
    ElMessage.error(errors[0])
    return
  }
  if (draft.images.length >= MAX_UPLOAD_IMAGES) {
    ElMessage.warning(t('plan.uploadLimit', { max: MAX_UPLOAD_IMAGES }))
    return
  }
  draft.images.push({
    id: `image-${Date.now()}-${imageSequence += 1}`,
    file: raw,
    url: URL.createObjectURL(raw),
    meta,
    room_type: '',
    status: 'draft',
    error: '',
    elapsed: 0,
  })
}

function onFileChange(file) {
  void addImage(file?.raw)
}

async function onNativeFiles(event) {
  const input = event.currentTarget
  const files = Array.from(input?.files || [])
  // 允许连续拍摄或重复选择同一张图片。
  if (input) input.value = ''
  for (const file of files) {
    if (draft.images.length >= MAX_UPLOAD_IMAGES) {
      ElMessage.warning(t('plan.uploadLimit', { max: MAX_UPLOAD_IMAGES }))
      break
    }
    await addImage(file)
  }
}

function capturedPhotoToFile(photo) {
  const encoded = String(photo?.base64 || '')
  if (!encoded) throw new Error('Camera returned no image data')
  const binary = window.atob(encoded)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new File(
    [bytes],
    photo?.fileName || `camera-${Date.now()}.jpg`,
    { type: photo?.mimeType || 'image/jpeg', lastModified: Date.now() },
  )
}

async function openCamera() {
  if (capturing.value) return
  const nativePlatform = Capacitor.isNativePlatform()
  const pluginAvailable = Capacitor.isPluginAvailable('CameraCapture')
  if (!nativePlatform) {
    cameraInput.value?.click()
    return
  }
  if (!pluginAvailable) {
    console.error('[CameraCapture] result=unavailable', {
      platform: Capacitor.getPlatform(),
      pluginAvailable,
    })
    ElMessage.error(t('plan.cameraUnavailable'))
    return
  }

  capturing.value = true
  try {
    const photo = await CameraCapture.capturePhoto()
    const file = capturedPhotoToFile(photo)
    console.info('[CameraCapture] result=success', {
      fileName: file.name,
      mimeType: file.type,
      sizeBytes: file.size,
    })
    await addImage(file)
  } catch (error) {
    if (error?.code === 'CAPTURE_CANCELLED') {
      console.info('[CameraCapture] result=cancelled', { code: error.code })
    } else {
      console.error('[CameraCapture] result=error', {
        code: error?.code || 'UNKNOWN',
        message: error?.message || String(error),
      })
      ElMessage.error(t('plan.cameraFailed'))
    }
  } finally {
    capturing.value = false
  }
}

function openGallery() {
  galleryInput.value?.click()
}

function removeImage(index) {
  const [removed] = draft.images.splice(index, 1)
  if (removed?.url) URL.revokeObjectURL(removed.url)
  draft.room_type = draft.images.find((image) => image.room_type)?.room_type || ''
  draft.imageErrors = []
}

async function ensureProject() {
  if (projectId.value) {
    if (studio.sessionProjectId !== projectId.value) studio.sessionProjectId = projectId.value
    return projectId.value
  }
  const title = draft.plan_name.trim() || t('render.projectTitle', { room: draft.room_type, style: draft.style })
  const project = await api.createProject({ title })
  projectId.value = project.id
  projectName.value = title
  studio.sessionProjectId = project.id
  return project.id
}

async function generate() {
  if (!uploadValid() || !configValid()) {
    ElMessage.warning(t('plan.stepIncomplete'))
    return
  }
  submitting.value = true
  batchJobs.value = []
  try {
    const pid = await ensureProject()
    const sourceImages = [...draft.images]
    const workflowMode = studio.workflowById(draft.workflowId)?.mode || ''
    const jobs = sourceImages.map((image) => {
      const task = studio.enqueueJob({
        projectId: pid,
        projectTitle: draft.plan_name.trim(),
        room_type: image.room_type,
        style: draft.style,
        budget_tier: draft.budget_tier,
        requirement: draft.requirement || '',
        moduleCodes: [...draft.moduleCodes],
        workflowId: draft.workflowId,
        rawPhoto: image.file,
      })
      return {
        id: task.id,
        title: recordName({ room_type: image.room_type }),
        image,
        room_type: image.room_type,
        style: draft.style,
        budget_tier: draft.budget_tier,
        workflow_mode: workflowMode,
        task,
      }
    })
    batchJobs.value = jobs

    const completed = await Promise.all(
      jobs.map(async (job) => {
        try {
          const result = await job.task.wait()
          const record = {
            ...renderToRecord(result),
            title: job.title,
            room_type: result?.room_type || job.room_type,
            style: result?.style || job.style,
            budget_tier: result?.budget_tier || job.budget_tier,
            workflow_mode: job.workflow_mode || expectedWorkflowMode({ result }),
          }
          if (!records.value.some((item) => item.id === record.id)) records.value.unshift(record)
          return record
        } catch {
          return null
        }
      }),
    )

    const created = completed.filter(Boolean)
    const failedIds = new Set(
      jobs.filter((job) => job.task.status === 'failed').map((job) => job.image.id),
    )
    if (created.length) selectedRecordId.value = records.value[0]?.id || null

    if (!failedIds.size) {
      ElMessage.success(t('plan.batchAdded', { count: created.length }))
      resetDraft()
      step.value = 0
      return
    }

    for (const image of sourceImages) {
      if (!failedIds.has(image.id) && image.url) URL.revokeObjectURL(image.url)
    }
    draft.images = sourceImages.filter((image) => failedIds.has(image.id))
    draft.room_type = draft.images.find((image) => image.room_type)?.room_type || ''
    if (created.length) {
      ElMessage.warning(t('plan.batchPartial', { success: created.length, failed: failedIds.size }))
    } else {
      ElMessage.error(t('plan.batchFailed', { count: failedIds.size }))
    }
  } catch (error) {
    const data = error?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : error.message)
    ElMessage.error(t('common.generateFailed', { msg }))
  } finally {
    submitting.value = false
  }
}

async function packageRecords() {
  if (!records.value.length) {
    ElMessage.warning(t('plan.noRecords'))
    return
  }
  submitting.value = true
  try {
    const first = records.value[0]
    const pid = await ensureProject()
    const title = projectName.value || draft.plan_name.trim() || t('plan.packageTitle', { count: records.value.length })
    const furnitures = records.value.reduce((list, record) => {
      for (const item of record.result?.furnitures || []) {
        if (!list.some((existing) => existing.id === item.id)) list.push(item)
      }
      return list
    }, [])
    const total = furnitures.reduce((sum, item) => sum + (Number(item.price) || 0), 0)
    const payload = {
      title,
      plan_name: title,
      room_type: first.room_type,
      style: first.style,
      budget_tier: first.budget_tier,
      result_url: resolveMediaUrl(first.result?.result_url),
      windows: records.value.map((record) => ({
        title: record.title,
        room_type: record.room_type,
        style: record.style,
        budget_tier: record.budget_tier,
        result_url: resolveMediaUrl(record.result?.result_url),
        furnitures: record.result?.furnitures || [],
        designer: record.result?.designer || null,
        contractor: record.result?.contractor || null,
        design_note: record.result?.design_note || '',
      })),
      furnitures,
      furniture_total: total,
      design_note: records.value
        .map((record) => `【${record.title}】${record.result?.design_note || ''}`)
        .filter(Boolean)
        .join('\n\n'),
      window_count: records.value.length,
    }

    const report = await api.saveReport({
      project: pid,
      render_job: first.result?.id,
      title: payload.title,
      room_type: first.room_type,
      style: first.style,
      budget_tier: first.budget_tier,
      report: payload,
    })

    await api.createOrder({
      consent: true,
      project: pid,
      report: report.id,
      title: payload.title,
      amount_min: payload.budget_min,
      amount_max: payload.budget_max,
      items: furnitures.map((item) => ({
        name: item.name,
        category: item.category_display,
        price: item.price,
        quantity: 1,
        amount: item.price,
      })),
      payload,
    })
    ElMessage.success(t('plan.packageSuccess'))
    router.push({ path: '/my-home', query: { tab: 'report' } })
  } catch (error) {
    const data = error?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : error.message)
    ElMessage.error(t('plan.packageFailed', { msg }))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="plan-workspace">
    <section class="plan-main">
      <div class="plan-flow">
        <nav class="step-indicator" :aria-label="t('plan.progressLabel')">
          <button
            v-for="(item, index) in steps"
            :key="item.key"
            type="button"
            class="step-dot"
            :class="{ active: item.key === currentStep.key, completed: index < step }"
            :disabled="index > step || submitting"
            :aria-current="item.key === currentStep.key ? 'step' : undefined"
            @click="goToStep(index)"
          >
            <span>{{ index + 1 }}</span>
            <small>{{ t(item.labelKey) }}</small>
          </button>
        </nav>

        <div class="step-content">
        <div v-show="step === 0" class="step-panel">
          <div class="plan-name-field" :class="{ 'has-error': nameRequired }">
            <label>{{ t('plan.nameLabel') }}</label>
            <el-input
              v-model="draft.plan_name"
              :disabled="submitting"
              :maxlength="40"
              show-word-limit
              :placeholder="t('plan.namePlaceholder')"
              @input="nameRequired = false"
            />
            <span v-if="nameRequired" class="name-error-text">{{ t('plan.nameRequired') }}</span>
          </div>
          <div v-if="draft.images.length" class="upload-grid">
            <div v-for="(image, index) in draft.images" :key="image.id" class="upload-tile">
              <img :src="image.url" alt="" />
              <span class="upload-function" :class="{ pending: !image.room_type }">
                {{ image.room_type ? term(image.room_type) : t('plan.awaitingDesigner') }}
              </span>
              <span class="upload-meta">{{ image.meta.width }}×{{ image.meta.height }}px · {{ (image.meta.size / 1024 / 1024).toFixed(2) }}MB</span>
              <el-button
                size="small"
                circle
                type="danger"
                class="upload-remove"
                :disabled="submitting"
                @click="removeImage(index)"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
            <template v-if="isApp && draft.images.length < MAX_UPLOAD_IMAGES">
              <button type="button" class="add-tile source-tile" :disabled="capturing || submitting" @click="openCamera">
                <el-icon :class="{ 'is-loading': capturing }"><Loading v-if="capturing" /><Camera v-else /></el-icon>
                <span>{{ capturing ? t('plan.openingCamera') : t('plan.takePhoto') }}</span>
              </button>
              <button type="button" class="add-tile source-tile" :disabled="submitting" @click="openGallery">
                <el-icon><Picture /></el-icon>
                <span>{{ t('plan.chooseAlbum') }}</span>
              </button>
            </template>
            <el-upload
              v-else-if="draft.images.length < MAX_UPLOAD_IMAGES"
              class="upload-add"
              :auto-upload="false"
              :show-file-list="false"
              :multiple="true"
              :disabled="submitting"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              :on-change="onFileChange"
            >
              <div class="add-tile">
                <el-icon><Plus /></el-icon>
                <span>{{ t('plan.addMore') }}</span>
              </div>
            </el-upload>
          </div>
          <div v-else-if="isApp" class="native-upload-panel">
            <el-icon class="upload-ic"><UploadFilled /></el-icon>
            <div class="native-upload-title">{{ t('plan.uploadPhotoTitle') }}</div>
            <small>{{ t('plan.uploadPhotoHint') }}</small>
            <div class="native-upload-actions">
              <button type="button" class="native-source-button" :disabled="capturing || submitting" @click="openCamera">
                <el-icon :class="{ 'is-loading': capturing }"><Loading v-if="capturing" /><Camera v-else /></el-icon>
                <span>{{ capturing ? t('plan.openingCamera') : t('plan.takePhoto') }}</span>
              </button>
              <button type="button" class="native-source-button" :disabled="submitting" @click="openGallery">
                <el-icon><Picture /></el-icon>
                <span>{{ t('plan.chooseAlbum') }}</span>
              </button>
            </div>
          </div>
          <el-upload
            v-else
            drag
            :auto-upload="false"
            :show-file-list="false"
            :multiple="true"
            :disabled="submitting"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            :on-change="onFileChange"
          >
            <div class="upload-empty">
              <el-icon class="upload-ic"><UploadFilled /></el-icon>
              <div>{{ t('win.uploadHint') }}</div>
              <small>{{ t('win.uploadTip') }}</small>
            </div>
          </el-upload>
          <input
            ref="cameraInput"
            class="native-file-input"
            type="file"
            accept="image/*"
            capture="environment"
            @change="onNativeFiles"
          />
          <input
            ref="galleryInput"
            class="native-file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            multiple
            @change="onNativeFiles"
          />
          <el-alert
            v-if="draft.imageErrors.length"
            type="error"
            :closable="false"
            :title="draft.imageErrors[0]"
          />
        </div>

        <div v-show="step === 1" class="step-panel">
          <el-form label-position="top" size="small">
            <el-form-item :label="t('win.style')">
              <el-select v-model="draft.style" :placeholder="t('win.stylePlaceholder')" style="width:100%">
                <el-option v-for="item in studio.options.styles" :key="item" :label="term(item)" :value="item" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('win.budgetTier')">
              <el-radio-group v-model="draft.budget_tier">
                <el-radio-button v-for="item in studio.options.budget_tiers" :key="item" :value="item">{{ term(item) }}</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="t('win.requirement')">
              <el-input
                v-model="draft.requirement"
                type="textarea"
                :rows="3"
                :maxlength="studio.requirementMaxLength"
                show-word-limit
                :placeholder="t('win.requirementPlaceholder')"
              />
            </el-form-item>
          </el-form>
        </div>

        <div v-show="step === 2" class="step-panel">
          <div class="review-card">
            <div v-if="draft.images.length" class="review-thumbs">
              <img v-for="image in draft.images" :key="image.id" :src="image.url" alt="" />
            </div>
            <div class="review-image-rooms">
              <div v-for="(image, index) in draft.images" :key="image.id" class="review-line">
                <span>{{ t('plan.imageNumber', { number: index + 1 }) }}</span>
                <b>{{ term(image.room_type) }}</b>
              </div>
            </div>
            <div class="review-line"><span>{{ t('win.style') }}</span><b>{{ term(draft.style) }}</b></div>
            <div class="review-line"><span>{{ t('win.budgetTier') }}</span><b>{{ term(draft.budget_tier) }}</b></div>
            <div class="review-line"><span>{{ t('win.requirement') }}</span><b>{{ draft.requirement || t('common.dash') }}</b></div>
            <div class="review-line"><span>{{ t('plan.imageCount') }}</span><b>{{ draft.images.length }}</b></div>
          </div>
          <el-alert
            v-if="draft.images.length"
            type="info"
            :closable="false"
            :title="t('plan.rateLimitNotice', { count: draft.images.length, max: 12 })"
          />
          <div v-if="batchJobs.length" class="batch-status" aria-live="polite">
            <b>{{ t('plan.batchProgress') }}</b>
            <div class="batch-status-list">
              <div v-for="job in batchJobs" :key="job.id" class="batch-status-item">
                <div>
                  <span>{{ job.title }}</span>
                  <small v-if="job.task.elapsed">{{ t('win.elapsed', { sec: job.task.elapsed }) }}</small>
                </div>
                <el-tag size="small" :type="statusTagType(job.task.status)" effect="plain">
                  {{ t(`status.${job.task.status}`) }}
                </el-tag>
                <p v-if="job.task.error">{{ job.task.error }}</p>
              </div>
            </div>
          </div>
          <el-button type="primary" class="generate-btn" :loading="submitting" :disabled="submitting" @click="generate">
            <el-icon><MagicStick /></el-icon>
            {{ t('win.generate') }}
          </el-button>
        </div>

        <div class="step-actions">
          <el-button :disabled="step === 0 || submitting" @click="previousStep">{{ t('plan.previous') }}</el-button>
          <el-button v-if="step < steps.length - 1" type="primary" :disabled="submitting" @click="nextStep">
            {{ t('plan.next') }}
          </el-button>
        </div>
        </div>
      </div>

      <aside class="designer-sidebar">
        <DesignCoach
          :key="designerVersion"
          :draft="draft"
          :has-images="Boolean(draft.images.length)"
          :disabled="submitting"
          @apply-patch="applyDesignerPatch"
        />
      </aside>

      <section v-loading="recordsLoading" class="records-section">
        <div class="records-head">
          <div>
            <b>{{ t('plan.recordsTitle') }}</b>
            <span>{{ records.length }}</span>
          </div>
          <el-button
            type="primary"
            :disabled="!records.length || submitting"
            :loading="submitting"
            @click="packageRecords"
          >
            <el-icon><Box /></el-icon>
            {{ t('plan.packageRecords') }}
          </el-button>
        </div>

        <div v-if="!records.length" class="records-empty">
          <el-icon><Picture /></el-icon>
          <span>{{ t('plan.noRecords') }}</span>
        </div>

        <div v-else class="records-row">
          <button
            v-for="record in records"
            :key="record.id"
            type="button"
            class="record-item"
            :class="{ active: record.id === selectedRecord?.id }"
            @click="selectedRecordId = record.id"
          >
            <el-image
              v-if="resolveMediaUrl(record.result?.result_url)"
              :src="resolveMediaUrl(record.result?.result_url)"
              fit="cover"
              class="record-thumb"
              :alt="record.title"
              :preview-src-list="recordImageUrls"
              :initial-index="recordImageUrls.indexOf(resolveMediaUrl(record.result?.result_url))"
              preview-teleported
              @click.stop
            />
            <div v-else class="record-ph"><el-icon><Picture /></el-icon></div>
            <span class="record-name">{{ record.title }}</span>
          </button>
        </div>

        <div v-if="selectedRecord" class="record-detail">
          <el-image
            v-if="resolveMediaUrl(selectedRecord.result?.result_url)"
            :src="resolveMediaUrl(selectedRecord.result?.result_url)"
            fit="contain"
            class="record-hero"
            :preview-src-list="recordImageUrls"
            :initial-index="recordImageUrls.indexOf(resolveMediaUrl(selectedRecord.result?.result_url))"
            preview-teleported
          />
          <div class="record-meta">
            <div class="record-meta-title">
              <b>{{ selectedRecord.title }}</b>
              <el-button size="small" text type="danger" :disabled="submitting" @click="records.splice(records.indexOf(selectedRecord), 1)">
                {{ t('common.remove') }}
              </el-button>
            </div>
            <span>{{ term(selectedRecord.room_type) }} · {{ term(selectedRecord.style) }} · {{ term(selectedRecord.budget_tier) }}</span>
            <p v-if="selectedRecord.result?.design_note">{{ selectedRecord.result.design_note }}</p>
          </div>

          <div v-if="selectedRecord.result?.render_mode" class="record-mode">
            <el-tag
              size="small"
              :type="selectedRecord.result.render_mode === 'img2img' ? 'success' : 'info'"
              effect="dark"
            >
              {{ modeLabel(selectedRecord.result.render_mode) }}
            </el-tag>
          </div>
          <el-alert
            v-if="renderModeDowngraded(selectedRecord)"
            type="warning"
            :closable="false"
            :title="t('win.modeDowngraded')"
          >
            <el-text size="small" type="info">
              {{ selectedRecord.result?.error || t('win.modeDowngradedTip') }}
            </el-text>
          </el-alert>

          <div class="record-people">
            <div class="person-card">
              <b>{{ t('render.designer') }}</b>
              <template v-if="selectedRecord.result?.designer">
                <span>{{ selectedRecord.result.designer.name }} · {{ selectedRecord.result.designer.title }}</span>
                <small>{{ selectedRecord.result.designer.city }} · {{ selectedRecord.result.designer.years }} 年</small>
                <el-link
                  :href="`https://example.com/designer/${selectedRecord.result.designer.id}`"
                  target="_blank"
                  type="primary"
                  :underline="false"
                >
                  {{ t('plan.viewDesigner') }}
                </el-link>
              </template>
              <span v-else>{{ t('common.none') }}</span>
            </div>
            <div class="person-card">
              <b>{{ t('render.contractor') }}</b>
              <template v-if="selectedRecord.result?.contractor">
                <span>{{ selectedRecord.result.contractor.name }}</span>
                <small>{{ selectedRecord.result.contractor.city }} · {{ selectedRecord.result.contractor.quote_range }}</small>
                <el-link
                  :href="`https://example.com/contractor/${selectedRecord.result.contractor.id}`"
                  target="_blank"
                  type="primary"
                  :underline="false"
                >
                  {{ t('plan.viewContractor') }}
                </el-link>
              </template>
              <span v-else>{{ t('common.none') }}</span>
            </div>
          </div>

          <div v-if="selectedRecord.result?.furnitures?.length" class="record-furniture">
            <b class="furniture-title">{{ t('render.furnitureList') }}</b>
            <div class="furniture-row">
              <div v-for="item in selectedRecord.result.furnitures" :key="item.id" class="furniture-card">
                <el-image
                  v-if="resolveMediaUrl(item.image_url)"
                  :src="resolveMediaUrl(item.image_url)"
                  fit="cover"
                  class="furniture-image"
                  :preview-src-list="furnitureImageUrls"
                  :initial-index="furnitureImageUrls.indexOf(resolveMediaUrl(item.image_url))"
                  preview-teleported
                />
                <div class="furniture-copy">
                  <b>{{ item.name }}</b>
                  <span>{{ item.brand }} · {{ term(item.category_display) }}</span>
                  <em>{{ money(item.price) }}</em>
                  <el-link
                    :href="item.buy_url || `https://example.com/furniture/${item.id}`"
                    target="_blank"
                    type="primary"
                    :underline="false"
                  >
                    {{ t('render.buyLink') }}
                  </el-link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  </div>
</template>

<style scoped>
.plan-workspace {
  width: 100%;
  max-width: 1480px;
  margin: 0 auto;
}

.plan-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: var(--app-surface);
  padding: 16px;
}

.plan-flow,
.designer-sidebar { min-width: 0; }

.records-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--brand-muted);
  font-size: 12px;
  padding: 20px 4px;
  text-align: center;
}

.records-list { display: flex; flex-direction: column; gap: 8px; }

.records-section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.records-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.records-head > div { display: flex; align-items: center; gap: 7px; font-size: 14px; }
.records-head > div span { color: var(--brand-muted); font-size: 12px; }

.records-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}

.record-item {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  width: 92px;
  padding: 7px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--brand-ink);
  font: inherit;
  cursor: pointer;
  text-align: center;
}

.record-item.active { border-color: #d1d5db; background: var(--brand-green-soft); }
.record-thumb,
.record-ph {
  width: 72px;
  height: 54px;
  border-radius: 9px;
  object-fit: cover;
}

.record-thumb { display: block; overflow: hidden; }
.record-thumb :deep(.el-image__inner) { width: 100%; height: 100%; }

.record-ph { display: grid; place-items: center; color: var(--brand-muted); background: var(--brand-green-soft); }
.record-name { font-size: 12px; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.step-indicator { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin-bottom: 16px; }

.step-dot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 4px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: var(--brand-muted);
  font: inherit;
  cursor: pointer;
}

.step-dot span {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-green-soft);
  color: var(--brand-green-deep);
  font-size: 12px;
  font-weight: 800;
}

.step-dot small { font-size: 11px; font-weight: 700; }
.step-dot.active { color: var(--brand-green-deep); }
.step-dot.active span { background: var(--brand-green); color: #fff; }
.step-dot.completed span { background: rgba(35, 169, 124, 0.2); }
.step-dot:disabled { cursor: not-allowed; opacity: 0.5; }

.step-content { min-height: 0; }
.step-panel { display: flex; flex-direction: column; gap: 12px; }

.plan-name-field { display: flex; flex-direction: column; gap: 6px; }
.plan-name-field label { font-size: 12px; color: var(--brand-muted); font-weight: 700; }
.plan-name-field.has-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f56c6c inset;
}
.name-error-text {
  color: #f56c6c;
  font-size: 12px;
  font-weight: 600;
}

.upload-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.upload-tile {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  overflow: hidden;
  background: var(--brand-green-soft);
}

.upload-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.upload-tile .upload-meta {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 14px 6px 4px;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.55));
  color: #fff;
  font-size: 10px;
  text-align: center;
}

.upload-function {
  position: absolute;
  top: 6px;
  left: 6px;
  max-width: calc(100% - 42px);
  padding: 4px 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(23, 134, 95, 0.92);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-function.pending { background: rgba(17, 24, 39, 0.7); }

.upload-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 2;
}

.upload-add { display: block; }
.add-tile {
  width: 100%;
  aspect-ratio: 1 / 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1.5px dashed #d1d5db;
  border-radius: 12px;
  color: var(--brand-ink);
  font-size: 12px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.66);
  font-family: inherit;
}

.add-tile .el-icon { font-size: 24px; }
.source-tile { appearance: none; }
.source-tile:disabled { cursor: wait; opacity: 0.62; }

.upload-ic { font-size: 34px; color: var(--brand-green); }
.upload-empty { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.native-upload-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  padding: 20px 14px 16px;
  border: 1.5px dashed rgba(35, 169, 124, 0.38);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(240, 252, 247, 0.92), rgba(255, 255, 255, 0.98));
  text-align: center;
}
.native-upload-title { color: var(--brand-ink); font-size: 14px; font-weight: 800; }
.native-upload-panel small { color: var(--brand-muted); font-size: 11px; }
.native-upload-actions {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 5px;
}
.native-source-button {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid rgba(35, 169, 124, 0.32);
  border-radius: 12px;
  background: #fff;
  color: var(--brand-green-deep);
  font-family: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.native-source-button .el-icon { font-size: 18px; }
.native-source-button:disabled { cursor: wait; opacity: 0.62; }
.native-file-input {
  position: fixed;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}
.preview-wrap { display: flex; justify-content: center; }
.preview-img { max-width: 100%; max-height: 220px; border-radius: 12px; }
.image-meta { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--brand-muted); }

.modules-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.module-group { margin-bottom: 12px; }
.module-group-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.module-group-head b { font-size: 13px; }
.module-group-head small { color: var(--brand-muted); font-size: 11px; }
.module-tags { display: flex; flex-wrap: wrap; gap: 6px; }

.review-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  background: var(--brand-green-soft);
}

.review-image-rooms {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding-bottom: 9px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.review-thumbs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}

.review-thumbs img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 9px;
}

.review-line { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.review-line span { color: var(--brand-muted); }
.review-line b { text-align: right; }

.step-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
}
.generate-btn { width: 100%; margin-top: 8px; }

.batch-status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(35, 169, 124, 0.2);
  border-radius: 14px;
  background: rgba(240, 252, 247, 0.64);
}
.batch-status > b { font-size: 13px; color: var(--brand-green-deep); }
.batch-status-list { display: grid; gap: 7px; }
.batch-status-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 4px 10px;
  padding: 8px 9px;
  border-radius: 10px;
  background: #fff;
}
.batch-status-item > div { display: flex; flex-direction: column; min-width: 0; }
.batch-status-item span { overflow: hidden; font-size: 12px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.batch-status-item small { color: var(--brand-muted); font-size: 10px; }
.batch-status-item p { grid-column: 1 / -1; margin: 0; color: #d14343; font-size: 11px; line-height: 1.45; }

.record-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.record-hero {
  display: block;
  width: 100%;
  max-height: 420px;
  overflow: hidden;
  object-fit: contain;
  border-radius: 14px;
  background: var(--brand-green-soft);
}
.record-hero :deep(.el-image__inner) { max-height: 420px; }

.record-meta-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.record-meta-title b { font-size: 16px; }
.record-meta > span { color: var(--brand-muted); font-size: 13px; }
.record-meta p { margin: 8px 0 0; font-size: 13px; line-height: 1.6; }
.record-mode { display: flex; align-items: center; gap: 8px; }

.record-people {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.person-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border-radius: 14px;
  background: var(--brand-green-soft);
  font-size: 12px;
}

.person-card b { font-size: 13px; color: var(--brand-green-deep); }
.person-card span { color: var(--brand-ink); }
.person-card small { color: var(--brand-muted); }

.record-furniture { margin-top: 4px; }
.furniture-title { display: block; font-size: 13px; color: var(--brand-green-deep); margin-bottom: 8px; }

.furniture-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.furniture-card {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-radius: 12px;
  background: #f7fbf9;
}

.furniture-image {
  width: 52px;
  height: 52px;
  overflow: hidden;
  border-radius: 9px;
  object-fit: cover;
  flex: none;
}
.furniture-image :deep(.el-image__inner) { width: 100%; height: 100%; }

.furniture-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.furniture-copy b { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.furniture-copy span { color: var(--brand-muted); font-size: 11px; }
.furniture-copy em { font-style: normal; color: var(--brand-green-deep); font-weight: 800; font-size: 12px; }

@media (min-width: 1024px) {
  .plan-main {
    grid-template-columns: minmax(0, 1.65fr) minmax(320px, 0.85fr);
    gap: 22px;
    padding: 22px;
  }

  .designer-sidebar {
    position: sticky;
    top: 84px;
    align-self: start;
  }

  .designer-sidebar :deep(.designer-card) { margin-top: 0; }
  .records-section { grid-column: 1 / -1; }
  .upload-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .record-detail { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.8fr); }
  .record-hero { grid-row: 1 / span 5; }
  .record-furniture,
  .record-people { grid-column: 2; }
}

@media (max-width: 720px) {
  .upload-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .record-people { grid-template-columns: 1fr; }
  .furniture-row { grid-template-columns: 1fr; }
}
</style>
