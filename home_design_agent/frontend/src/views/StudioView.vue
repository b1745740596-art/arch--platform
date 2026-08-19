<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useStudioStore } from '@/stores/studio'
import { clampModuleCodes } from '@/utils/validation'
import { isNativeApp } from '@/utils/app'
import StudioWindowCard from '@/components/StudioWindowCard.vue'
import PlanWorkspace from '@/components/PlanWorkspace.vue'

const studio = useStudioStore()
const { t } = useI18n()
const isApp = computed(() => isNativeApp())

// 宽屏两列：按索引奇偶拆分，保证卡片高度不一致时也不会互相拉扯
const leftColumn = computed(() => studio.windows.filter((_, i) => i % 2 === 0))
const rightColumn = computed(() => studio.windows.filter((_, i) => i % 2 === 1))

const readyCount = computed(
  () => studio.windows.filter((w) => studio.windowIssues(w).length === 0 && !['queued', 'running'].includes(w.status)).length,
)

onMounted(async () => {
  // store 为应用级单例：重新进入时补回预览 URL
  studio.rehydratePreviews()
  await studio.loadOptions()
  if (!isApp.value && !studio.windows.length) studio.addWindow()
})

// 离开页面时释放预览 URL 并取消进行中的请求，避免内存泄漏
onBeforeUnmount(() => {
  studio.dispose()
})

function addWindow() {
  if (!studio.canAddWindow) {
    ElMessage.warning(t('studio.limitWarn', { max: studio.MAX_WINDOWS }))
    return
  }
  studio.addWindow()
}

function submitAll() {
  const count = studio.enqueueAll()
  if (!count) {
    ElMessage.warning(t('studio.noSubmittable'))
    return
  }
  ElMessage.success(t('studio.submittedAll', { count, max: studio.MAX_CONCURRENT }))
}

// 把 N 个 variant 分别 fork 成 N 个新窗口（受窗口上限约束）
function forkVariants({ win, variants }) {
  let created = 0
  let skipped = 0
  for (const variant of variants) {
    if (!studio.canAddWindow) {
      skipped += 1
      continue
    }
    const { codes } = clampModuleCodes(variant.module_codes || [], {
      modules: studio.modules,
      groups: studio.groups,
      maxModules: studio.maxModules,
    })
    const created_win = studio.addWindow({
      room_type: win.form.room_type,
      style: win.form.style,
      budget_tier: win.form.budget_tier,
      requirement: win.form.requirement,
      moduleCodes: codes,
    })
    if (created_win) {
      created_win.title = variant.title || t('studio.schemeWindow')
      created += 1
    }
  }
  if (created) {
    ElMessage.success(
      t('studio.forked', {
        count: created,
        skipped: skipped ? t('studio.forkedSkipped', { count: skipped }) : '',
      }),
    )
  } else {
    ElMessage.warning(t('studio.forkLimit', { max: studio.MAX_WINDOWS }))
  }
}

function closeAll() {
  studio.resetAll()
  studio.addWindow()
  ElMessage.success(t('studio.boardReset'))
}
</script>

<template>
  <div class="studio" :class="{ 'is-app': isApp }">
    <PlanWorkspace v-if="isApp" />

    <template v-else>
      <!-- 顶部工具栏 -->
      <el-card v-if="!isApp" shadow="never" class="toolbar">
      <div class="tb">
        <div class="tb-l">
          <h3 class="tb-title">{{ t('studio.title') }}</h3>
          <el-text size="small" type="info">
            {{ t('studio.subtitle', { max: studio.MAX_CONCURRENT }) }}
          </el-text>
        </div>
        <div class="tb-r">
          <el-tag size="small" type="info" effect="plain">
            {{ t('studio.windows', { current: studio.windows.length, max: studio.MAX_WINDOWS }) }}
          </el-tag>
          <el-tag size="small" type="primary" effect="plain">
            {{ t('studio.running', { count: studio.busyCount }) }}
          </el-tag>
          <el-tag v-if="studio.queuedCount" size="small" type="warning" effect="plain">
            {{ t('studio.queued', { count: studio.queuedCount }) }}
          </el-tag>
        </div>
      </div>
      <div class="tb-actions">
        <el-button type="primary" :disabled="!studio.canAddWindow" @click="addWindow">
          <el-icon><Plus /></el-icon> {{ t('studio.addWindow') }}
        </el-button>
        <el-button type="success" :disabled="!readyCount" @click="submitAll">
          <el-icon><Promotion /></el-icon> {{ t('studio.submitAll') }}<template v-if="readyCount">（{{ readyCount }}）</template>
        </el-button>
        <el-button :loading="studio.optionsLoading" @click="studio.loadOptions()">
          <el-icon><Refresh /></el-icon> {{ t('studio.refreshOptions') }}
        </el-button>
        <el-button text @click="closeAll">{{ t('studio.resetBoard') }}</el-button>
      </div>
      <el-alert
        v-if="!studio.canAddWindow"
        type="info"
        :closable="false"
        class="tb-alert"
        :title="t('studio.limitAlert', { max: studio.MAX_WINDOWS })"
      />
      <el-alert
        v-if="studio.optionsDegraded"
        type="warning"
        :closable="false"
        class="tb-alert"
        :title="t('studio.degraded')"
      >
        <el-text size="small" type="info">{{ studio.optionsError }}</el-text>
      </el-alert>
    </el-card>

    <!-- 窗口网格：窄屏单列、宽屏两列 -->
    <el-row :gutter="16" class="grid">
      <el-col :xs="24" :sm="24" :md="12">
        <StudioWindowCard
          v-for="win in leftColumn"
          :key="win.id"
          :win="win"
          :index="studio.windows.indexOf(win)"
          @fork-variants="forkVariants"
        />
      </el-col>
      <el-col :xs="24" :sm="24" :md="12">
        <StudioWindowCard
          v-for="win in rightColumn"
          :key="win.id"
          :win="win"
          :index="studio.windows.indexOf(win)"
          @fork-variants="forkVariants"
        />
      </el-col>
    </el-row>

    <el-empty v-if="!studio.windows.length" :description="t('studio.emptyBoard')" />
    </template>
  </div>
</template>

<style scoped>
.studio { width: 100%; }
.toolbar { margin-bottom: 16px; }
.tb { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.tb-l { min-width: 0; }
.tb-title { margin: 0 0 4px; font-size: 18px; }
.tb-r { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tb-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.tb-alert { margin-top: 12px; }
.grid { margin-top: 0; }
</style>
