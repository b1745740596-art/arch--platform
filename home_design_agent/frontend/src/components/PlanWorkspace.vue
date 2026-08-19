<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useStudioStore } from '@/stores/studio'
import { useTerm } from '@/i18n'
import { resolveMediaUrl } from '@/utils/media'
import { canSelectModule, validateImageFile } from '@/utils/validation'

const studio = useStudioStore()
const { t } = useI18n()
const term = useTerm()

const steps = [
  { key: 'upload', labelKey: 'plan.stepUpload' },
  { key: 'config', labelKey: 'plan.stepConfig' },
  { key: 'modules', labelKey: 'plan.stepModules' },
  { key: 'review', labelKey: 'plan.stepReview' },
]

const step = ref(0)
const submitting = ref(false)
const records = ref([])
const projectId = ref(studio.sessionProjectId || null)
const selectedRecordId = ref(null)
const uploadRef = ref(null)

const draft = reactive({
  file: null,
  previewUrl: '',
  imageMeta: null,
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

function recordName(record) {
  return record.room_type ? term(record.room_type) : t('plan.unnamed')
}

function ensureDraftDefaults() {
  const preset = studio.defaultPreset()
  draft.room_type = draft.room_type || preset.room_type
  draft.style = draft.style || preset.style
  draft.budget_tier = draft.budget_tier || preset.budget_tier
  draft.moduleCodes = draft.moduleCodes.length ? [...draft.moduleCodes] : [...(preset.moduleCodes || [])]
  draft.workflowId = draft.workflowId ?? preset.workflowId
}

onMounted(async () => {
  await studio.loadOptions()
  ensureDraftDefaults()
  if (!projectId.value) projectId.value = studio.sessionProjectId || null
})

function releaseDraftPreview() {
  if (draft.previewUrl) {
    URL.revokeObjectURL(draft.previewUrl)
    draft.previewUrl = ''
  }
}

function resetDraft() {
  releaseDraftPreview()
  draft.file = null
  draft.previewUrl = ''
  draft.imageMeta = null
  draft.imageErrors = []
  draft.room_type = ''
  draft.style = ''
  draft.budget_tier = ''
  draft.requirement = ''
  draft.moduleCodes = []
  draft.workflowId = null
  ensureDraftDefaults()
  uploadRef.value?.clearFiles()
}

function uploadValid() {
  return Boolean(draft.file && !draft.imageErrors.length)
}

function configValid() {
  return Boolean(draft.room_type && draft.style && draft.budget_tier)
}

function modulesValid() {
  return draft.moduleCodes.length <= studio.maxModules
}

function stepValid() {
  if (step.value === 0) return uploadValid()
  if (step.value === 1) return configValid()
  if (step.value === 2) return modulesValid()
  return true
}

function nextStep() {
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

function onFileChange(file) {
  const raw = file?.raw
  if (!raw) return
  draft.imageErrors = []
  validateImageFile(raw, studio.imageRules).then(({ ok, errors, meta }) => {
    if (!ok) {
      releaseDraftPreview()
      draft.file = null
      draft.imageMeta = null
      draft.imageErrors = errors
      uploadRef.value?.clearFiles()
      ElMessage.error(errors[0])
      return
    }
    releaseDraftPreview()
    draft.file = raw
    draft.previewUrl = URL.createObjectURL(raw)
    draft.imageMeta = meta
  })
}

function removeImage() {
  releaseDraftPreview()
  draft.file = null
  draft.imageMeta = null
  draft.imageErrors = []
  uploadRef.value?.clearFiles()
}

function toggleModule(module) {
  const selected = draft.moduleCodes
  const index = selected.indexOf(module.code)
  if (index >= 0) {
    selected.splice(index, 1)
    return
  }
  const check = canSelectModule({
    module,
    selectedCodes: selected,
    modules: studio.modules,
    groups: studio.groups,
    maxModules: studio.maxModules,
  })
  if (!check.allowed) {
    ElMessage.warning(check.reason)
    return
  }
  if (check.replace?.length) {
    for (const code of check.replace) {
      const idx = selected.indexOf(code)
      if (idx >= 0) selected.splice(idx, 1)
    }
  }
  selected.push(module.code)
}

function isModuleSelected(code) {
  return draft.moduleCodes.includes(code)
}

function groupHint(group) {
  if (group.multiple === false) return t('win.single')
  return group.max_select ? t('win.maxSelect', { max: group.max_select }) : t('win.multiple')
}

async function ensureProject() {
  if (projectId.value) return projectId.value
  const project = await api.createProject({
    title: t('render.projectTitle', { room: draft.room_type, style: draft.style }),
  })
  projectId.value = project.id
  studio.sessionProjectId = project.id
  return project.id
}

async function generate() {
  if (!uploadValid() || !configValid() || !modulesValid()) {
    ElMessage.warning(t('plan.stepIncomplete'))
    return
  }
  submitting.value = true
  try {
    const pid = await ensureProject()
    const fd = new FormData()
    fd.append('project', pid)
    fd.append('room_type', draft.room_type)
    fd.append('style', draft.style)
    fd.append('budget_tier', draft.budget_tier)
    fd.append('requirement', draft.requirement || '')
    fd.append('raw_photo', draft.file)
    if (draft.moduleCodes.length) fd.append('module_codes', draft.moduleCodes.join(','))
    if (draft.workflowId != null) fd.append('workflow', draft.workflowId)

    const result = await api.createRender(fd)
    if (result?.status === 'failed') {
      ElMessage.error(result.error || t('common.unknownError'))
      return
    }

    records.value.unshift({
      id: `${result.id || Date.now()}-${records.value.length}`,
      title: recordName({ room_type: draft.room_type }),
      room_type: draft.room_type,
      style: draft.style,
      budget_tier: draft.budget_tier,
      result,
      created_at: new Date().toISOString(),
    })
    selectedRecordId.value = records.value[0].id
    ElMessage.success(t('plan.recordAdded', { room: recordName({ room_type: draft.room_type }) }))
    resetDraft()
    step.value = 0
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
    const furnitures = records.value.reduce((list, record) => {
      for (const item of record.result?.furnitures || []) {
        if (!list.some((existing) => existing.id === item.id)) list.push(item)
      }
      return list
    }, [])
    const total = furnitures.reduce((sum, item) => sum + (Number(item.price) || 0), 0)
    const payload = {
      title: t('plan.packageTitle', { count: records.value.length }),
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
    <aside class="plan-sidebar">
      <div class="sidebar-head">
        <b>{{ t('plan.recordsTitle') }}</b>
        <span>{{ records.length }}</span>
      </div>
      <div v-if="!records.length" class="records-empty">
        <el-icon><Picture /></el-icon>
        <span>{{ t('plan.noRecords') }}</span>
      </div>
      <div v-else class="records-list">
        <button
          v-for="record in records"
          :key="record.id"
          type="button"
          class="record-item"
          :class="{ active: record.id === selectedRecord?.id }"
          @click="selectedRecordId = record.id"
        >
          <img v-if="resolveMediaUrl(record.result?.result_url)" :src="resolveMediaUrl(record.result?.result_url)" :alt="record.title" />
          <div v-else class="record-ph"><el-icon><Picture /></el-icon></div>
          <span class="record-name">{{ record.title }}</span>
        </button>
      </div>
    </aside>

    <section class="plan-main">
      <div class="step-indicator">
        <button
          v-for="(item, index) in steps"
          :key="item.key"
          type="button"
          class="step-dot"
          :class="{ active: index <= step }"
          @click="goToStep(index)"
        >
          <span>{{ index + 1 }}</span>
          <small>{{ t(item.labelKey) }}</small>
        </button>
      </div>

      <div class="step-content">
        <div v-show="step === 0" class="step-panel">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :show-file-list="false"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            :on-change="onFileChange"
          >
            <div v-if="draft.previewUrl" class="preview-wrap">
              <img :src="draft.previewUrl" class="preview-img" alt="preview" />
            </div>
            <div v-else class="upload-empty">
              <el-icon class="upload-ic"><UploadFilled /></el-icon>
              <div>{{ t('win.uploadHint') }}</div>
              <small>{{ t('win.uploadTip') }}</small>
            </div>
          </el-upload>
          <div v-if="draft.imageMeta" class="image-meta">
            <span>{{ draft.imageMeta.width }}×{{ draft.imageMeta.height }}px · {{ (draft.imageMeta.size / 1024 / 1024).toFixed(2) }}MB</span>
            <el-button size="small" text type="danger" @click="removeImage">{{ t('common.remove') }}</el-button>
          </div>
        </div>

        <div v-show="step === 1" class="step-panel">
          <el-form label-position="top" size="small">
            <el-form-item :label="t('win.roomType')">
              <el-select v-model="draft.room_type" :placeholder="t('win.roomTypePlaceholder')" style="width:100%">
                <el-option v-for="item in studio.options.room_types" :key="item" :label="term(item)" :value="item" />
              </el-select>
            </el-form-item>
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
            <el-form-item v-if="studio.workflows.length" :label="t('win.workflow')">
              <el-select v-model="draft.workflowId" :placeholder="t('win.workflowPlaceholder')" style="width:100%">
                <el-option v-for="wf in studio.workflows" :key="wf.id" :label="wf.name" :value="wf.id" />
              </el-select>
            </el-form-item>
          </el-form>
        </div>

        <div v-show="step === 2" class="step-panel">
          <div class="modules-head">
            <span>{{ t('win.diverge') }}</span>
            <el-tag size="small" type="info" effect="plain">{{ draft.moduleCodes.length }} / {{ studio.maxModules }}</el-tag>
          </div>
          <div v-for="group in studio.modulesByGroup" :key="group.key" class="module-group">
            <div class="module-group-head">
              <b>{{ term(group.label) || group.key }}</b>
              <small>{{ groupHint(group) }}</small>
            </div>
            <div class="module-tags">
              <el-check-tag
                v-for="module in group.modules"
                :key="module.code"
                :checked="isModuleSelected(module.code)"
                @change="toggleModule(module)"
              >
                {{ module.name }}
              </el-check-tag>
            </div>
          </div>
        </div>

        <div v-show="step === 3" class="step-panel">
          <div class="review-card">
            <img v-if="draft.previewUrl" :src="draft.previewUrl" alt="preview" />
            <div class="review-line"><span>{{ t('win.roomType') }}</span><b>{{ term(draft.room_type) }}</b></div>
            <div class="review-line"><span>{{ t('win.style') }}</span><b>{{ term(draft.style) }}</b></div>
            <div class="review-line"><span>{{ t('win.budgetTier') }}</span><b>{{ term(draft.budget_tier) }}</b></div>
            <div class="review-line"><span>{{ t('win.requirement') }}</span><b>{{ draft.requirement || t('common.dash') }}</b></div>
            <div class="review-line"><span>{{ t('win.diverge') }}</span><b>{{ draft.moduleCodes.length }} / {{ studio.maxModules }}</b></div>
          </div>
          <el-button type="primary" class="generate-btn" :loading="submitting" @click="generate">
            <el-icon><MagicStick /></el-icon>
            {{ t('win.generate') }}
          </el-button>
        </div>
      </div>

      <div class="step-actions">
        <el-button :disabled="step === 0" @click="previousStep">{{ t('plan.previous') }}</el-button>
        <el-button v-if="step < steps.length - 1" type="primary" :disabled="!stepValid()" @click="nextStep">
          {{ t('plan.next') }}
        </el-button>
      </div>

      <div v-if="selectedRecord" class="selected-record">
        <img v-if="resolveMediaUrl(selectedRecord.result?.result_url)" :src="resolveMediaUrl(selectedRecord.result?.result_url)" alt="" />
        <div class="selected-copy">
          <b>{{ selectedRecord.title }}</b>
          <span>{{ term(selectedRecord.room_type) }} · {{ term(selectedRecord.style) }}</span>
          <el-button size="small" @click="records.splice(records.indexOf(selectedRecord), 1)">{{ t('common.remove') }}</el-button>
        </div>
      </div>

      <el-button class="package-btn" :disabled="!records.length" :loading="submitting" @click="packageRecords">
        <el-icon><Box /></el-icon>
        {{ t('plan.packageRecords') }}
      </el-button>
    </section>
  </div>
</template>

<style scoped>
.plan-workspace {
  display: grid;
  grid-template-columns: 118px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.plan-sidebar {
  position: sticky;
  top: 80px;
  border: 1px solid var(--app-border);
  border-radius: 16px;
  background: var(--app-surface);
  padding: 12px;
}

.sidebar-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; font-size: 13px; }
.sidebar-head span { color: var(--brand-muted); }

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

.record-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  width: 100%;
  padding: 7px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--brand-ink);
  font: inherit;
  cursor: pointer;
  text-align: center;
}

.record-item.active { border-color: var(--brand-green); background: var(--brand-green-soft); }
.record-item img,
.record-ph {
  width: 72px;
  height: 54px;
  border-radius: 9px;
  object-fit: cover;
}

.record-ph { display: grid; place-items: center; color: var(--brand-muted); background: var(--brand-green-soft); }
.record-name { font-size: 12px; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.plan-main {
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: var(--app-surface);
  padding: 16px;
}

.step-indicator { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin-bottom: 16px; }

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

.step-content { min-height: 320px; }
.step-panel { display: flex; flex-direction: column; gap: 12px; }

.upload-ic { font-size: 34px; color: var(--brand-green); }
.upload-empty { display: flex; flex-direction: column; align-items: center; gap: 3px; }
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

.review-card img { width: 100%; max-height: 180px; object-fit: cover; border-radius: 10px; }
.review-line { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.review-line span { color: var(--brand-muted); }
.review-line b { text-align: right; }

.step-actions { display: flex; justify-content: space-between; margin-top: 16px; }
.generate-btn { width: 100%; margin-top: 8px; }

.selected-record {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 16px;
  padding: 10px;
  border-radius: 14px;
  background: var(--brand-green-soft);
}

.selected-record img { width: 72px; height: 54px; object-fit: cover; border-radius: 9px; }
.selected-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.selected-copy b { font-size: 13px; }
.selected-copy span { color: var(--brand-muted); font-size: 12px; }

.package-btn { width: 100%; margin-top: 16px; }

@media (max-width: 720px) {
  .plan-workspace { grid-template-columns: 1fr; }
  .plan-sidebar { position: static; display: flex; gap: 10px; overflow-x: auto; }
  .records-list { flex-direction: row; }
  .record-item { min-width: 88px; }
  .records-empty { min-width: 120px; }
}
</style>