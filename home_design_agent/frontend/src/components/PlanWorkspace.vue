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
import DesignCoach from '@/components/DesignCoach.vue'

const router = useRouter()
const studio = useStudioStore()
const { t } = useI18n()
const term = useTerm()

const steps = [
  { key: 'upload', labelKey: 'plan.stepUpload' },
  { key: 'config', labelKey: 'plan.stepConfig' },
  { key: 'review', labelKey: 'plan.stepReview' },
]

const step = ref(0)
const submitting = ref(false)
const records = ref([])
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

function ensureDraftDefaults() {
  const preset = studio.defaultPreset()
  draft.plan_name = draft.plan_name || projectName.value
  draft.style = draft.style || preset.style
  draft.budget_tier = draft.budget_tier || preset.budget_tier
}

onMounted(async () => {
  if (!projectId.value) projectId.value = studio.sessionProjectId || null
  await studio.loadOptions()
  ensureDraftDefaults()
})

function releaseDraftImages() {
  for (const image of draft.images) {
    if (image.url) URL.revokeObjectURL(image.url)
  }
  draft.images = []
}

function resetDraft() {
  releaseDraftImages()
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

function onFileChange(file) {
  const raw = file?.raw
  if (!raw) return
  if (draft.images.length >= MAX_UPLOAD_IMAGES) {
    ElMessage.warning(t('plan.uploadLimit', { max: MAX_UPLOAD_IMAGES }))
    return
  }
  draft.imageErrors = []
  validateImageFile(raw, studio.imageRules).then(({ ok, errors, meta }) => {
    if (!ok) {
      draft.imageErrors = errors
      ElMessage.error(errors[0])
      return
    }
    draft.images.push({
      id: `image-${Date.now()}-${imageSequence += 1}`,
      file: raw,
      url: URL.createObjectURL(raw),
      meta,
      room_type: '',
    })
  })
}

function removeImage(index) {
  const [removed] = draft.images.splice(index, 1)
  if (removed?.url) URL.revokeObjectURL(removed.url)
  draft.room_type = draft.images.find((image) => image.room_type)?.room_type || ''
  draft.imageErrors = []
}

async function ensureProject() {
  if (projectId.value) return projectId.value
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
  try {
    const pid = await ensureProject()
    const created = []
    for (let index = 0; index < draft.images.length; index += 1) {
      const image = draft.images[index]
      const fd = new FormData()
      fd.append('project', pid)
      fd.append('room_type', image.room_type)
      fd.append('style', draft.style)
      fd.append('budget_tier', draft.budget_tier)
      fd.append('requirement', draft.requirement || '')
      fd.append('raw_photo', image.file)
      if (draft.moduleCodes.length) fd.append('module_codes', draft.moduleCodes.join(','))
      if (draft.workflowId != null) fd.append('workflow', draft.workflowId)

      const result = await api.createRender(fd)
      if (result?.status === 'failed') {
        ElMessage.error(result.error || t('common.unknownError'))
        continue
      }

      const record = {
        id: `${result.id || Date.now()}-${records.value.length}`,
        title: recordName({ room_type: image.room_type }),
        room_type: image.room_type,
        style: draft.style,
        budget_tier: draft.budget_tier,
        result,
        created_at: new Date().toISOString(),
      }
      records.value.unshift(record)
      created.push(record)
    }

    if (created.length) selectedRecordId.value = records.value[0].id
    ElMessage.success(t('plan.batchAdded', { count: created.length }))
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
      <div class="step-content">
        <div v-show="step === 0" class="step-panel">
          <div class="plan-name-field" :class="{ 'has-error': nameRequired }">
            <label>{{ t('plan.nameLabel') }}</label>
            <el-input
              v-model="draft.plan_name"
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
                @click="removeImage(index)"
              >
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
            <el-upload
              v-if="draft.images.length < MAX_UPLOAD_IMAGES"
              class="upload-add"
              :auto-upload="false"
              :show-file-list="false"
              :multiple="true"
              accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
              :on-change="onFileChange"
            >
              <div class="add-tile">
                <el-icon><Plus /></el-icon>
                <span>{{ t('plan.addMore') }}</span>
              </div>
            </el-upload>
          </div>
          <el-upload
            v-else
            drag
            :auto-upload="false"
            :show-file-list="false"
            :multiple="true"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            :on-change="onFileChange"
          >
            <div class="upload-empty">
              <el-icon class="upload-ic"><UploadFilled /></el-icon>
              <div>{{ t('win.uploadHint') }}</div>
              <small>{{ t('win.uploadTip') }}</small>
            </div>
          </el-upload>
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
          <el-button type="primary" class="generate-btn" :loading="submitting" @click="generate">
            <el-icon><MagicStick /></el-icon>
            {{ t('win.generate') }}
          </el-button>
        </div>

        <div class="step-actions">
          <el-button :disabled="step === 0" @click="previousStep">{{ t('plan.previous') }}</el-button>
          <el-button v-if="step < steps.length - 1" type="primary" @click="nextStep">
            {{ t('plan.next') }}
          </el-button>
        </div>
      </div>

      <DesignCoach
        :key="designerVersion"
        :draft="draft"
        :has-images="Boolean(draft.images.length)"
        :disabled="submitting"
        @apply-patch="applyDesignerPatch"
      />

      <section class="records-section">
        <div class="records-head">
          <div>
            <b>{{ t('plan.recordsTitle') }}</b>
            <span>{{ records.length }}</span>
          </div>
          <el-button
            type="primary"
            :disabled="!records.length"
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
            <img
              v-if="resolveMediaUrl(record.result?.result_url)"
              :src="resolveMediaUrl(record.result?.result_url)"
              :alt="record.title"
            />
            <div v-else class="record-ph"><el-icon><Picture /></el-icon></div>
            <span class="record-name">{{ record.title }}</span>
          </button>
        </div>

        <div v-if="selectedRecord" class="record-detail">
          <img
            v-if="resolveMediaUrl(selectedRecord.result?.result_url)"
            :src="resolveMediaUrl(selectedRecord.result?.result_url)"
            class="record-hero"
            alt=""
          />
          <div class="record-meta">
            <div class="record-meta-title">
              <b>{{ selectedRecord.title }}</b>
              <el-button size="small" text type="danger" @click="records.splice(records.indexOf(selectedRecord), 1)">
                {{ t('common.remove') }}
              </el-button>
            </div>
            <span>{{ term(selectedRecord.room_type) }} · {{ term(selectedRecord.style) }} · {{ term(selectedRecord.budget_tier) }}</span>
            <p v-if="selectedRecord.result?.design_note">{{ selectedRecord.result.design_note }}</p>
          </div>

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
                <img v-if="resolveMediaUrl(item.image_url)" :src="resolveMediaUrl(item.image_url)" alt="" />
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
  display: block;
}

.plan-main {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: var(--app-surface);
  padding: 16px;
}

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
.record-item img,
.record-ph {
  width: 72px;
  height: 54px;
  border-radius: 9px;
  object-fit: cover;
}

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
}

.add-tile .el-icon { font-size: 24px; }

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

.record-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.record-hero {
  width: 100%;
  max-height: 420px;
  object-fit: contain;
  border-radius: 14px;
  background: var(--brand-green-soft);
}

.record-meta-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.record-meta-title b { font-size: 16px; }
.record-meta > span { color: var(--brand-muted); font-size: 13px; }
.record-meta p { margin: 8px 0 0; font-size: 13px; line-height: 1.6; }

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

.furniture-card img {
  width: 52px;
  height: 52px;
  border-radius: 9px;
  object-fit: cover;
  flex: none;
}

.furniture-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.furniture-copy b { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.furniture-copy span { color: var(--brand-muted); font-size: 11px; }
.furniture-copy em { font-style: normal; color: var(--brand-green-deep); font-weight: 800; font-size: 12px; }

@media (max-width: 720px) {
  .upload-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .record-people { grid-template-columns: 1fr; }
  .furniture-row { grid-template-columns: 1fr; }
}
</style>
