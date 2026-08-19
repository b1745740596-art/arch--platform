<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAppUpdateStore } from '@/stores/appUpdate'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const router = useRouter()
const { t } = useI18n()
const appUpdate = useAppUpdateStore()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
const changelog = computed(() => appUpdate.latest?.changelog || [])
const latestVersion = computed(() => appUpdate.latest?.version || t('common.dash'))

async function checkUpdate() {
  await appUpdate.check()
  if (!appUpdate.error && !appUpdate.updateAvailable) {
    ElMessage.success(t('appUpdate.upToDate'))
  }
}

function downloadLatest() {
  appUpdate.downloadLatest()
}

function openAccount() {
  visible.value = false
  router.push('/account')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="t('appUpdate.settings')"
    width="min(420px, 92vw)"
    align-center
    class="app-settings-dialog"
  >
    <div class="settings">
      <button type="button" class="settings-row" @click="openAccount">
        <span class="settings-icon"><el-icon><User /></el-icon></span>
        <span class="settings-copy">
          <b>{{ t('nav.account') }}</b>
          <small>{{ t('appUpdate.accountHint') }}</small>
        </span>
        <el-icon class="settings-arrow"><ArrowRight /></el-icon>
      </button>

      <div class="update-card">
        <div class="update-head">
          <span class="update-title">
            <el-icon><Upload /></el-icon>
            {{ t('appUpdate.updateTitle') }}
          </span>
          <el-tag
            v-if="appUpdate.updateAvailable"
            type="danger"
            size="small"
            effect="dark"
          >
            {{ t('appUpdate.updateAvailable', { version: latestVersion }) }}
          </el-tag>
          <el-tag v-else-if="appUpdate.checked" type="success" size="small" effect="plain">
            {{ t('appUpdate.upToDate') }}
          </el-tag>
        </div>

        <div class="version-line">
          <span>{{ t('appUpdate.currentVersion') }}</span>
          <b>{{ appUpdate.currentVersion || t('common.dash') }}</b>
        </div>
        <div class="version-line">
          <span>{{ t('appUpdate.latestVersion') }}</span>
          <b>{{ latestVersion }}</b>
        </div>

        <div v-if="changelog.length" class="changelog">
          <div class="changelog-title">{{ t('appUpdate.changelog') }}</div>
          <div v-for="item in changelog" :key="item" class="changelog-item">· {{ item }}</div>
        </div>

        <el-alert
          v-if="appUpdate.error"
          type="error"
          :closable="false"
          class="update-error"
          :title="t('appUpdate.failed', { msg: appUpdate.error })"
        />

        <div class="update-actions">
          <el-button
            type="primary"
            :loading="appUpdate.loading"
            @click="checkUpdate"
          >
            {{ appUpdate.loading ? t('appUpdate.checking') : t('appUpdate.checkUpdate') }}
          </el-button>
          <el-button
            v-if="appUpdate.updateAvailable"
            type="success"
            @click="downloadLatest"
          >
            {{ t('appUpdate.download') }}
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.settings { display: flex; flex-direction: column; gap: 14px; }

.settings-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border: 1px solid rgba(47, 107, 79, 0.10);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--brand-ink);
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.settings-row:hover { background: rgba(47, 107, 79, 0.07); }

.settings-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(47, 107, 79, 0.10);
  color: var(--brand-green);
  font-size: 18px;
}

.settings-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.settings-copy b { font-size: 14px; }
.settings-copy small { color: var(--brand-muted); font-size: 12px; }
.settings-arrow { color: var(--brand-muted); }

.update-card {
  padding: 14px;
  border-radius: 14px;
  background: rgba(47, 107, 79, 0.05);
  border: 1px solid rgba(47, 107, 79, 0.09);
}

.update-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.update-title { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 800; color: var(--brand-green-deep); }

.version-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  color: var(--brand-muted);
  font-size: 13px;
}

.version-line b { color: var(--brand-ink); }

.changelog { margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(47, 107, 79, 0.16); }
.changelog-title { font-size: 12px; font-weight: 800; color: var(--brand-green); margin-bottom: 4px; }
.changelog-item { color: var(--brand-muted); font-size: 12px; line-height: 1.7; }

.update-error { margin-top: 10px; }
.update-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
</style>