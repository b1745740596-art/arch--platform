<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useTerm } from '@/i18n'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const term = useTerm()
const loading = ref(false)
const project = ref(null)
const generating = ref(false)

const tierColor = { economy: 'info', quality: 'primary', premium: 'warning' }

async function load() {
  loading.value = true
  try {
    project.value = await api.getProject(route.params.id)
  } catch (e) {
    ElMessage.error(t('common.loadFailed', { msg: e.message || e }))
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function regenerate() {
  generating.value = true
  try {
    await api.generateSchemes(project.value.id)
    ElMessage.success(t('detail.regenerated'))
    await load()
  } catch (e) {
    ElMessage.error(t('common.generateFailed', { msg: e.message || e }))
  } finally {
    generating.value = false
  }
}

async function toggleFav(scheme) {
  try {
    const updated = await api.toggleFavorite(scheme.id)
    scheme.is_favorited = updated.is_favorited
  } catch (e) {
    ElMessage.error(t('common.actionFailed', { msg: e.message || e }))
  }
}

function money(v) {
  return v == null ? t('common.dash') : '¥' + Number(v).toLocaleString()
}

// ---- 留资 ----
const leadVisible = ref(false)
const leadRef = ref()
const leadSubmitting = ref(false)
const lead = reactive({ scheme: null, contact_name: '', contact_phone: '', remark: '' })
const leadRules = computed(() => ({
  contact_name: [{ required: true, message: t('detail.rules.contactName'), trigger: 'blur' }],
  contact_phone: [{ required: true, message: t('detail.rules.contactPhone'), trigger: 'blur' }],
}))

function openLead(scheme) {
  lead.scheme = scheme ? scheme.id : null
  lead.contact_name = ''
  lead.contact_phone = ''
  lead.remark = ''
  leadVisible.value = true
}

async function submitLead() {
  await leadRef.value.validate()
  leadSubmitting.value = true
  try {
    await api.createLead({
      project: project.value.id,
      scheme: lead.scheme,
      contact_name: lead.contact_name,
      contact_phone: lead.contact_phone,
      consent: true,
      city: project.value.city,
      community: project.value.community,
      remark: lead.remark,
    })
    ElMessage.success(t('detail.leadSubmitted'))
    leadVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(t('common.submitFailed', { msg: e.message || e }))
  } finally {
    leadSubmitting.value = false
  }
}
</script>

<template>
  <div v-loading="loading">
    <el-page-header @back="router.push('/projects')" class="ph">
      <template #content>
        <span v-if="project">{{ project.title || t('detail.fallbackTitle', { id: project.id }) }}</span>
      </template>
    </el-page-header>

    <template v-if="project">
      <el-descriptions :column="4" border class="meta">
        <el-descriptions-item :label="t('detail.city')">{{ project.city || t('common.dash') }}</el-descriptions-item>
        <el-descriptions-item :label="t('detail.community')">{{ project.community || t('common.dash') }}</el-descriptions-item>
        <el-descriptions-item :label="t('detail.area')">{{ project.area || t('common.dash') }} {{ t('common.sqm') }}</el-descriptions-item>
        <el-descriptions-item :label="t('detail.status')">
          <el-tag type="success">{{ term(project.status_display) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="bar">
        <h3>{{ t('detail.schemesTitle', { count: project.schemes.length }) }}</h3>
        <div>
          <el-button @click="openLead(null)"><el-icon><Phone /></el-icon> {{ t('detail.bookConsultant') }}</el-button>
          <el-button type="primary" :loading="generating" @click="regenerate">
            <el-icon><MagicStick /></el-icon> {{ t('detail.regenerateSchemes') }}
          </el-button>
        </div>
      </div>

      <el-empty v-if="project.schemes.length === 0" :description="t('detail.emptySchemes')" />

      <el-row v-else :gutter="16">
        <el-col v-for="s in project.schemes" :key="s.id" :xs="24" :md="8">
          <el-card shadow="hover" class="scheme">
            <template #header>
              <div class="scheme-hd">
                <span class="scheme-name">{{ s.name }}</span>
                <el-icon class="fav" :class="{ on: s.is_favorited }" @click="toggleFav(s)">
                  <StarFilled v-if="s.is_favorited" /><Star v-else />
                </el-icon>
              </div>
              <div>
                <el-tag size="small" :type="tierColor[s.budget_tier]">{{ term(s.budget_tier_display) }}</el-tag>
                <el-tag size="small" type="info" style="margin-left:6px">{{ term(s.style) }}</el-tag>
              </div>
            </template>

            <div class="budget">{{ money(s.budget_min) }} — {{ money(s.budget_max) }}</div>
            <p class="layout">{{ s.layout }}</p>

            <div class="sec">{{ t('detail.highlights') }}</div>
            <ul><li v-for="(h, i) in s.highlights" :key="i">{{ h }}</li></ul>

            <div class="sec">{{ t('detail.risks') }}</div>
            <ul class="risk"><li v-for="(r, i) in s.risks" :key="i">{{ r }}</li></ul>

            <el-text size="small" type="info" class="assume">{{ s.assumptions }}</el-text>

            <div class="buildable">
              <el-tag size="small" :type="s.buildable_checked ? 'success' : 'warning'">
                {{ s.buildable_checked ? t('detail.buildableChecked') : t('detail.buildablePending') }}
              </el-tag>
            </div>

            <el-button type="primary" plain class="pick" @click="openLead(s)">
              {{ t('detail.pick') }}
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-dialog v-model="leadVisible" :title="t('detail.leadTitle')" width="440px">
      <el-form ref="leadRef" :model="lead" :rules="leadRules" label-width="100px">
        <el-form-item :label="t('detail.contactName')" prop="contact_name">
          <el-input v-model="lead.contact_name" />
        </el-form-item>
        <el-form-item :label="t('detail.contactPhone')" prop="contact_phone">
          <el-input v-model="lead.contact_phone" />
        </el-form-item>
        <el-form-item :label="t('detail.remark')">
          <el-input v-model="lead.remark" type="textarea" :rows="2" :placeholder="t('intake.optional')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leadVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="leadSubmitting" @click="submitLead">{{ t('detail.submitLead') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.ph { margin-bottom: 16px; }
.meta { margin-bottom: 16px; }
.bar { display: flex; align-items: center; justify-content: space-between; margin: 8px 0 16px; }
.bar h3 { margin: 0; }
.scheme { margin-bottom: 16px; }
.scheme-hd { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.scheme-name { font-weight: 600; font-size: 16px; }
.fav { cursor: pointer; color: var(--el-text-color-secondary); font-size: 18px; }
.fav.on { color: var(--el-color-warning); }
.budget { font-size: 18px; font-weight: 600; color: var(--el-color-danger); margin: 4px 0 8px; }
.layout { font-size: 13px; color: var(--el-text-color-regular); margin: 0 0 8px; }
.sec { font-weight: 600; font-size: 13px; margin-top: 8px; }
ul { margin: 4px 0; padding-left: 18px; font-size: 13px; }
ul.risk { color: var(--el-color-warning); }
.assume { display: block; margin: 8px 0; }
.buildable { margin: 8px 0; }
.pick { width: 100%; margin-top: 8px; }
</style>
