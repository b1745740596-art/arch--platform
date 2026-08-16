<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useStudioStore, STATUS_META } from '@/stores/studio'
import { useTerm } from '@/i18n'
import {
  canSelectModule,
  clampModuleCodes,
  describeImageRules,
  validateImageFile,
} from '@/utils/validation'

const props = defineProps({
  win: { type: Object, required: true },
  index: { type: Number, default: 0 },
})
const emit = defineEmits(['fork-variants'])

const studio = useStudioStore()
const { t } = useI18n()
const term = useTerm()
const uploadRef = ref(null)

const statusMeta = computed(() => STATUS_META[props.win.status] || STATUS_META.draft)
const statusLabel = computed(() => t(statusMeta.value.key))
const issues = computed(() => studio.windowIssues(props.win))
const submittable = computed(() => studio.isSubmittable(props.win))
const busy = computed(() => ['running', 'queued', 'validating'].includes(props.win.status))
const imageTip = computed(() => describeImageRules(studio.imageRules))
const result = computed(() => props.win.result)
const furnitures = computed(() => result.value?.furnitures || [])
const furnitureImages = computed(() => furnitures.value.map((f) => f.image_url).filter(Boolean))
const appliedModules = computed(() => result.value?.applied_modules || [])
// 当前选中的工作流与其生图模式（img2img 会把上传照片作为参考图）
const selectedWorkflow = computed(() => studio.workflowById(props.win.workflowId))
const workflowMode = computed(() => selectedWorkflow.value?.mode || '')
// 实际生效的模式：后端会在图生图失败时退回文生图
const renderMode = computed(() => result.value?.render_mode || '')
const renderModeDowngraded = computed(
  () => workflowMode.value === 'img2img' && renderMode.value === 'text2img',
)

// 模式文案本地化（后端 mode_display 为中文，这里按当前语言展示）
function modeLabel(mode) {
  return mode === 'img2img' ? t('win.modeImg2Img') : t('win.modeText2Img')
}

// 图片选择：先做真实像素校验，失败则清除文件并提示具体原因
async function onFileChange(file) {
  const raw = file?.raw
  if (!raw) return
  props.win.status = 'validating'
  props.win.imageErrors = []
  const { ok, errors, meta } = await validateImageFile(raw, studio.imageRules)
  if (!ok) {
    studio.clearImage(props.win.id)
    props.win.imageErrors = errors
    props.win.status = 'draft'
    uploadRef.value?.clearFiles()
    ElMessage.error(errors[0])
    return
  }
  studio.setImage(props.win.id, raw, meta)
  props.win.status = 'draft'
  props.win.imageErrors = []
}

function removeImage() {
  studio.clearImage(props.win.id)
  props.win.imageErrors = []
  uploadRef.value?.clearFiles()
}

// 发散选项勾选：遵守分组 multiple / max_select 与全局 max_modules
function toggleModule(module) {
  if (busy.value) return
  const selected = props.win.moduleCodes
  const idx = selected.indexOf(module.code)
  if (idx >= 0) {
    selected.splice(idx, 1)
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
    for (const old of check.replace) {
      const i = selected.indexOf(old)
      if (i >= 0) selected.splice(i, 1)
    }
  }
  selected.push(module.code)
}

function isSelected(code) {
  return props.win.moduleCodes.includes(code)
}

function applyVariant(variant) {
  const { codes, dropped } = clampModuleCodes(variant.module_codes || [], {
    modules: studio.modules,
    groups: studio.groups,
    maxModules: studio.maxModules,
  })
  props.win.moduleCodes = codes
  if (dropped.length) {
    ElMessage.warning(t('win.variantClamped', { title: variant.title, count: dropped.length }))
  } else {
    ElMessage.success(t('win.variantApplied', { title: variant.title }))
  }
}

function clearModules() {
  props.win.moduleCodes = []
}

function submit() {
  const list = issues.value
  if (list.length) {
    ElMessage.error(list[0])
    return
  }
  const waiting = studio.busyCount >= studio.MAX_CONCURRENT
  if (studio.enqueue(props.win.id)) {
    ElMessage.success(waiting ? t('win.queuedTip') : t('win.startedTip'))
  }
}

function money(v) {
  return v == null ? t('common.dash') : '¥' + Number(v).toLocaleString()
}

function groupHint(group) {
  if (group.multiple === false) return t('win.single')
  return group.max_select ? t('win.maxSelect', { max: group.max_select }) : t('win.multiple')
}
</script>

<template>
  <el-card shadow="never" class="win-card" :class="'is-' + win.status">
    <template #header>
      <div class="win-hd">
        <div class="win-hd-l">
          <b class="win-title">{{ win.title || t('win.title', { index: index + 1 }) }}</b>
          <el-tag :type="statusMeta.type" size="small" effect="light">{{ statusLabel }}</el-tag>
          <span v-if="win.status === 'running'" class="timer">
            <el-icon class="spin"><Loading /></el-icon> {{ win.elapsed }}s
          </span>
          <span v-else-if="win.status === 'success' && win.elapsed" class="timer">
            {{ t('win.elapsed', { sec: win.elapsed }) }}
          </span>
        </div>
        <div class="win-hd-r">
          <el-tooltip :content="t('win.duplicate')" placement="top">
            <el-button
              size="small"
              text
              :disabled="!studio.canAddWindow || busy"
              @click="studio.duplicateWindow(win.id)"
            >
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip :content="t('win.close')" placement="top">
            <el-button size="small" text @click="studio.closeWindow(win.id)">
              <el-icon><Close /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </template>

    <!-- 上传区 -->
    <el-upload
      ref="uploadRef"
      drag
      class="up"
      :auto-upload="false"
      :limit="1"
      :show-file-list="false"
      :disabled="busy"
      accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
      :on-change="onFileChange"
    >
      <div v-if="win.previewUrl" class="pv-wrap">
        <img :src="win.previewUrl" class="pv" :alt="t('win.previewAlt')" />
      </div>
      <div v-else class="up-empty">
        <el-icon class="up-ic"><UploadFilled /></el-icon>
        <div>{{ t('win.uploadHint') }}</div>
        <div class="tip">{{ imageTip }}</div>
      </div>
    </el-upload>
    <div v-if="win.imageMeta" class="img-meta">
      <el-text size="small" type="success">
        {{ win.imageMeta.width }}×{{ win.imageMeta.height }}px ·
        {{ (win.imageMeta.size / 1024 / 1024).toFixed(2) }}MB
      </el-text>
      <el-button size="small" text type="danger" :disabled="busy" @click.stop="removeImage">
        {{ t('common.remove') }}
      </el-button>
    </div>

    <!-- 表单 -->
    <el-form label-width="82px" class="form" size="small" :disabled="busy">
      <el-form-item v-if="studio.workflows.length" :label="t('win.workflow')">
        <el-select v-model="win.workflowId" :placeholder="t('win.workflowPlaceholder')">
          <el-option
            v-for="wf in studio.workflows"
            :key="wf.id"
            :label="wf.name"
            :value="wf.id"
          >
            <span>{{ wf.name }}</span>
            <el-text size="small" type="info" class="wf-opt">
              {{ modeLabel(wf.mode) }} · {{ t('win.workflowSteps', { count: wf.step_count }) }}
            </el-text>
          </el-option>
        </el-select>
        <el-text v-if="selectedWorkflow" size="small" type="info" class="wf-hint">
          {{ modeLabel(workflowMode) }}：{{
            workflowMode === 'img2img' ? t('win.modeImg2ImgHint') : t('win.modeText2ImgHint')
          }}
        </el-text>
      </el-form-item>
      <el-form-item :label="t('win.roomType')">
        <el-select v-model="win.form.room_type" :placeholder="t('win.roomTypePlaceholder')">
          <el-option v-for="r in studio.options.room_types" :key="r" :label="term(r)" :value="r" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('win.style')">
        <el-select v-model="win.form.style" :placeholder="t('win.stylePlaceholder')">
          <el-option v-for="s in studio.options.styles" :key="s" :label="term(s)" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('win.budgetTier')">
        <el-radio-group v-model="win.form.budget_tier">
          <el-radio-button v-for="tier in studio.options.budget_tiers" :key="tier" :value="tier">
            {{ term(tier) }}
          </el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item :label="t('win.requirement')">
        <el-input
          v-model="win.form.requirement"
          type="textarea"
          :rows="2"
          :maxlength="studio.requirementMaxLength"
          show-word-limit
          :placeholder="t('win.requirementPlaceholder')"
        />
      </el-form-item>
    </el-form>

    <!-- 发散选项 -->
    <el-collapse class="diverge">
      <el-collapse-item name="modules">
        <template #title>
          <span class="dv-title">
            {{ t('win.diverge') }}
            <el-tag size="small" type="info" effect="plain">
              {{ win.moduleCodes.length }} / {{ studio.maxModules }}
            </el-tag>
          </span>
        </template>

        <div class="dv-actions">
          <el-button
            size="small"
            :loading="win.variantLoading"
            :disabled="busy"
            @click="studio.fetchVariants(win.id)"
          >
            <el-icon><MagicStick /></el-icon> {{ t('win.moreInspiration') }}
          </el-button>
          <el-button
            v-if="win.variants.length"
            size="small"
            text
            type="primary"
            @click="emit('fork-variants', { win, variants: win.variants })"
          >
            {{ t('win.forkEach') }}
          </el-button>
          <el-button v-if="win.moduleCodes.length" size="small" text :disabled="busy" @click="clearModules">
            {{ t('win.clearSelected') }}
          </el-button>
        </div>

        <el-text v-if="win.variantHint" size="small" type="info" class="dv-hint">{{ win.variantHint }}</el-text>

        <div v-if="win.variants.length" class="vars">
          <el-card
            v-for="v in win.variants"
            :key="v.key"
            shadow="hover"
            class="var-card"
            body-style="padding:10px"
            @click="applyVariant(v)"
          >
            <div class="var-title">{{ v.title }}</div>
            <div class="var-sum">{{ v.summary }}</div>
            <div v-if="v.highlights && v.highlights.length" class="var-hl">
              <el-tag v-for="h in v.highlights" :key="h" size="small" type="info" effect="plain">{{ h }}</el-tag>
            </div>
          </el-card>
        </div>

        <el-empty v-if="!studio.modulesByGroup.length" :image-size="48" :description="t('win.emptyModules')" />
        <div v-for="g in studio.modulesByGroup" :key="g.key" class="mg">
          <div class="mg-hd">
            <span class="mg-label">{{ term(g.label) || g.key }}</span>
            <el-text size="small" type="info">{{ groupHint(g) }}</el-text>
          </div>
          <div class="mg-tags">
            <el-tooltip
              v-for="m in g.modules"
              :key="m.code"
              :content="m.description || m.name"
              placement="top"
              :disabled="!m.description"
            >
              <el-check-tag :checked="isSelected(m.code)" class="m-tag" @change="toggleModule(m)">
                {{ m.name }}
              </el-check-tag>
            </el-tooltip>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 待修正项 -->
    <el-alert v-if="issues.length && !busy" type="warning" :closable="false" class="issues" :title="t('win.issues')">
      <ul class="issue-list">
        <li v-for="(it, i) in issues" :key="i">{{ it }}</li>
      </ul>
    </el-alert>

    <el-button
      type="primary"
      class="submit"
      :loading="win.status === 'running'"
      :disabled="!submittable"
      @click="submit"
    >
      <template v-if="win.status === 'queued'">{{ t('win.queueing') }}</template>
      <template v-else-if="win.status === 'running'">{{ t('win.generating', { sec: win.elapsed }) }}</template>
      <template v-else><el-icon><MagicStick /></el-icon> {{ t('win.generate') }}</template>
    </el-button>

    <!-- 结果区 -->
    <el-alert v-if="win.status === 'failed'" type="error" :closable="false" class="err" :title="t('win.genFailed')">
      <div class="err-msg">{{ win.error || t('common.unknownError') }}</div>
      <el-button size="small" type="danger" plain @click="studio.retry(win.id)">{{ t('common.retry') }}</el-button>
    </el-alert>

    <template v-if="result && win.status === 'success'">
      <el-divider content-position="left">{{ t('win.resultTitle') }}</el-divider>
      <el-image
        v-if="result.result_url"
        :src="result.result_url"
        fit="contain"
        class="render-img"
        :preview-src-list="[result.result_url]"
        preview-teleported
      />
      <div v-if="appliedModules.length || renderMode" class="applied">
        <el-tag
          v-if="renderMode"
          size="small"
          :type="renderMode === 'img2img' ? 'success' : 'info'"
          effect="dark"
        >
          {{ modeLabel(renderMode) }}
        </el-tag>
        <el-text v-if="appliedModules.length" size="small" type="info">{{ t('win.appliedModules') }}</el-text>
        <el-tag v-for="m in appliedModules" :key="m.code || m.name" size="small" type="success" effect="plain">
          {{ m.name || m.code }}
        </el-tag>
      </div>
      <el-alert
        v-if="renderModeDowngraded"
        type="warning"
        :closable="false"
        class="issues"
        :title="t('win.modeDowngraded')"
      >
        <el-text size="small" type="info">{{ result.error || t('win.modeDowngradedTip') }}</el-text>
      </el-alert>

      <template v-if="result.design_note">
        <el-divider content-position="left">{{ t('win.designNote') }}</el-divider>
        <pre class="note-text">{{ result.design_note }}</pre>
      </template>

      <template v-if="furnitures.length">
        <el-divider content-position="left">{{ t('win.furnitureList') }}</el-divider>
        <el-row :gutter="8">
          <el-col v-for="f in furnitures" :key="f.id" :span="12">
            <el-card shadow="hover" class="fur" body-style="padding:8px">
              <el-image
                v-if="f.image_url"
                :src="f.image_url"
                fit="cover"
                class="fur-img"
                :preview-src-list="furnitureImages"
                :initial-index="furnitureImages.indexOf(f.image_url)"
                preview-teleported
              >
                <template #error>
                  <div class="fur-img fur-img-ph"><el-icon><Picture /></el-icon></div>
                </template>
              </el-image>
              <div v-else class="fur-img fur-img-ph"><el-icon><Picture /></el-icon></div>
              <div class="fur-name">{{ f.name }}</div>
              <div class="fur-meta">{{ f.brand }} · {{ term(f.category_display) }}</div>
              <div class="fur-price">{{ money(f.price) }}</div>
              <el-link v-if="f.buy_url" :href="f.buy_url" target="_blank" type="primary" :underline="false">
                {{ t('win.buyLink') }}
              </el-link>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <el-row :gutter="8" class="rec">
        <el-col :span="12">
          <el-card shadow="never" body-style="padding:10px">
            <div class="rec-hd">{{ t('win.contractor') }}</div>
            <template v-if="result.contractor">
              <div class="rec-name">{{ result.contractor.name }}</div>
              <div class="rec-meta">
                <span>{{ result.contractor.city }} · {{ result.contractor.quote_range }}</span>
                <span>{{ result.contractor.response_speed }}</span>
              </div>
            </template>
            <el-text v-else type="info" size="small">{{ t('common.none') }}</el-text>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" body-style="padding:10px">
            <div class="rec-hd">{{ t('win.designer') }}</div>
            <template v-if="result.designer">
              <div class="rec-name">{{ result.designer.name }} · {{ result.designer.title }}</div>
              <div class="rec-meta">
                <span>{{ result.designer.city }} · {{ t('win.yearsExp', { years: result.designer.years }) }}</span>
              </div>
            </template>
            <el-text v-else type="info" size="small">{{ t('common.none') }}</el-text>
          </el-card>
        </el-col>
      </el-row>

      <el-collapse v-if="result.prompt" class="prompt-box">
        <el-collapse-item :title="t('win.promptTitle')">
          <el-text size="small">{{ result.prompt }}</el-text>
        </el-collapse-item>
      </el-collapse>
      <div class="res-actions">
        <el-button size="small" @click="studio.retry(win.id)">{{ t('common.regenerate') }}</el-button>
      </div>
    </template>
  </el-card>
</template>

<style scoped>
.win-card { margin-bottom: 16px; }
.win-card.is-running { border-color: var(--el-color-primary-light-5); }
.win-card.is-failed { border-color: var(--el-color-danger-light-5); }
.win-hd { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.win-hd-l { display: flex; align-items: center; gap: 8px; min-width: 0; }
.win-hd-r { display: flex; align-items: center; flex: none; }
.win-title { font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.timer { font-size: 12px; color: var(--el-text-color-secondary); display: inline-flex; align-items: center; gap: 4px; }
.spin { animation: rot 1s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }
.up { width: 100%; }
.up :deep(.el-upload) { width: 100%; }
.up :deep(.el-upload-dragger) { padding: 12px; }
.up-empty { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.up-ic { font-size: 32px; color: var(--el-color-primary); }
.tip { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.pv-wrap { display: flex; justify-content: center; }
.pv { max-height: 140px; max-width: 100%; border-radius: 6px; }
.img-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; }
.form { margin-top: 12px; }
.diverge { margin-bottom: 8px; }
.dv-title { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
.dv-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.dv-hint { display: block; margin-bottom: 8px; }
.vars { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.var-card { cursor: pointer; }
.var-title { font-weight: 600; font-size: 13px; }
.var-sum { font-size: 12px; color: var(--el-text-color-secondary); margin: 2px 0 4px; }
.var-hl { display: flex; flex-wrap: wrap; gap: 4px; }
.mg { margin-bottom: 10px; }
.mg-hd { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.mg-label { font-size: 13px; font-weight: 600; }
.mg-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.m-tag { font-size: 12px; }
.issues { margin-bottom: 10px; }
.issue-list { margin: 4px 0 0; padding-left: 18px; font-size: 12px; line-height: 1.7; }
.submit { width: 100%; }
.err { margin-top: 10px; }
.err-msg { font-size: 12px; margin: 4px 0 8px; word-break: break-word; }
.render-img { width: 100%; max-height: 280px; border-radius: 8px; background: #f2f4f7; }
.applied { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 8px; }
.wf-opt { margin-left: 8px; }
.wf-hint { display: block; line-height: 1.5; margin-top: 2px; }
.note-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  background: var(--el-fill-color-light);
  padding: 8px;
  border-radius: 6px;
  max-height: 180px;
  overflow: auto;
}
.fur { margin-bottom: 8px; }
.fur-img { width: 100%; height: 84px; border-radius: 4px; background: #f2f4f7; margin-bottom: 6px; cursor: zoom-in; }
.fur-img-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 20px;
  cursor: default;
}
.fur-name { font-weight: 600; font-size: 12px; }
.fur-meta { font-size: 11px; color: var(--el-text-color-secondary); }
.fur-price { color: var(--el-color-danger); font-weight: 600; font-size: 12px; }
.rec { margin-top: 8px; }
.rec-hd { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.rec-name { font-weight: 600; font-size: 13px; }
.rec-meta { display: flex; flex-direction: column; gap: 2px; font-size: 11px; color: var(--el-text-color-secondary); }
.prompt-box { margin-top: 10px; }
.res-actions { margin-top: 10px; display: flex; justify-content: flex-end; }
</style>
