<script setup>
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useTerm } from '@/i18n'

const { t } = useI18n()
const term = useTerm()
const submitting = ref(false)
const result = ref(null)
const previewUrl = ref('')

const form = reactive({
  project: null,
  style: '现代轻奢',
  room_type: '客厅',
  budget_tier: '品质',
  requirement: '',
  raw_photo: null,
})

const styles = ['现代简约', '现代轻奢', '意式极简', '北欧', '中式', '日式']
const rooms = ['客厅', '主卧', '次卧', '厨房', '卫生间', '书房', '餐厅']
const tiers = ['经济', '品质', '高端']

function onFileChange(file) {
  form.raw_photo = file.raw
  previewUrl.value = URL.createObjectURL(file.raw)
}

async function ensureProject() {
  if (form.project) return form.project
  const p = await api.createProject({
    title: t('render.projectTitle', { room: form.room_type, style: form.style }),
  })
  form.project = p.id
  return p.id
}

async function generate() {
  if (!form.raw_photo) {
    ElMessage.warning(t('render.needPhoto'))
    return
  }
  submitting.value = true
  try {
    const pid = await ensureProject()
    const fd = new FormData()
    fd.append('project', pid)
    fd.append('style', form.style)
    fd.append('room_type', form.room_type)
    fd.append('budget_tier', form.budget_tier)
    fd.append('requirement', form.requirement || '')
    fd.append('raw_photo', form.raw_photo)
    result.value = await api.createRender(fd)
    if (result.value.status === 'failed') {
      ElMessage.error(t('common.generateFailed', { msg: result.value.error }))
    } else {
      ElMessage.success(t('render.generated'))
    }
  } catch (e) {
    ElMessage.error(t('common.submitFailed', { msg: e.message || e }))
  } finally {
    submitting.value = false
  }
}

async function regenerate() {
  if (!result.value) return
  submitting.value = true
  try {
    result.value = await api.regenerateRender(result.value.id)
    ElMessage.success(t('render.regenerated'))
  } catch (e) {
    ElMessage.error(t('common.failed', { msg: e.message || e }))
  } finally {
    submitting.value = false
  }
}

function money(v) {
  return v == null ? t('common.dash') : '¥' + Number(v).toLocaleString()
}
const furnitures = computed(() => result.value?.furnitures || [])
const furnitureImages = computed(() => furnitures.value.map((f) => f.image_url).filter(Boolean))
</script>

<template>
  <el-row :gutter="16">
    <!-- 左：输入 -->
    <el-col :xs="24" :md="9">
      <el-card shadow="never">
        <template #header><b>{{ t('render.inputHeader') }}</b></template>
        <el-upload
          drag :auto-upload="false" :limit="1" :show-file-list="false"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif" :on-change="onFileChange"
        >
          <template v-if="previewUrl">
            <img :src="previewUrl" class="preview" />
          </template>
          <template v-else>
            <el-icon class="up-ic"><UploadFilled /></el-icon>
            <div>{{ t('render.uploadHint') }}</div>
            <div class="tip">{{ t('render.uploadTip') }}</div>
          </template>
        </el-upload>

        <el-form label-width="92px" class="form">
          <el-form-item :label="t('render.roomType')">
            <el-select v-model="form.room_type"><el-option v-for="r in rooms" :key="r" :label="term(r)" :value="r" /></el-select>
          </el-form-item>
          <el-form-item :label="t('render.style')">
            <el-select v-model="form.style"><el-option v-for="s in styles" :key="s" :label="term(s)" :value="s" /></el-select>
          </el-form-item>
          <el-form-item :label="t('render.budgetTier')">
            <el-radio-group v-model="form.budget_tier">
              <el-radio-button v-for="tier in tiers" :key="tier" :value="tier">{{ term(tier) }}</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="t('render.requirement')">
            <el-input v-model="form.requirement" type="textarea" :rows="3"
              :placeholder="t('render.requirementPlaceholder')" />
          </el-form-item>
          <el-button type="primary" :loading="submitting" @click="generate" style="width:100%">
            <el-icon><MagicStick /></el-icon> {{ t('render.generate') }}
          </el-button>
        </el-form>
      </el-card>
    </el-col>

    <!-- 右：结果 -->
    <el-col :xs="24" :md="15">
      <el-card shadow="never" class="result-card">
        <template #header>
          <div class="rhd">
            <b>{{ t('render.resultHeader') }}</b>
            <el-button v-if="result" size="small" :loading="submitting" @click="regenerate">
              {{ t('render.regenerate') }}
            </el-button>
          </div>
        </template>

        <el-empty v-if="!result" :description="t('render.emptyResult')" />

        <template v-else>
          <el-image v-if="result.result_url" :src="result.result_url" fit="contain" class="render-img"
            :preview-src-list="[result.result_url]" />
          <el-tag :type="result.status === 'success' ? 'success' : 'danger'" class="st">
            {{ term(result.status_display) }}
          </el-tag>

          <template v-if="result.design_note">
            <el-divider content-position="left">{{ t('render.designNote') }}</el-divider>
            <el-card shadow="never" class="note">
              <pre class="note-text">{{ result.design_note }}</pre>
            </el-card>
          </template>

          <el-divider content-position="left">{{ t('render.furnitureList') }}</el-divider>
          <el-row :gutter="12">
            <el-col v-for="f in furnitures" :key="f.id" :xs="12" :sm="8">
              <el-card shadow="hover" class="fur" body-style="padding:10px">
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
                  {{ t('render.buyLink') }}
                </el-link>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="12" class="rec">
            <el-col :xs="24" :sm="12">
              <el-card shadow="never">
                <template #header>{{ t('render.contractor') }}</template>
                <template v-if="result.contractor">
                  <div class="rec-name">{{ result.contractor.name }}</div>
                  <div class="rec-meta">
                    <el-rate :model-value="Number(result.contractor.rating)" disabled />
                    <span>{{ result.contractor.city }} · {{ result.contractor.quote_range }}</span>
                    <span>{{ result.contractor.response_speed }}</span>
                  </div>
                </template>
                <el-text v-else type="info">{{ t('common.none') }}</el-text>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-card shadow="never">
                <template #header>{{ t('render.designer') }}</template>
                <template v-if="result.designer">
                  <div class="rec-name">{{ result.designer.name }} · {{ result.designer.title }}</div>
                  <div class="rec-meta">
                    <el-rate :model-value="Number(result.designer.rating)" disabled />
                    <span>{{ result.designer.city }} · {{ t('render.yearsExp', { years: result.designer.years }) }}</span>
                  </div>
                  <div class="rec-intro">{{ result.designer.intro }}</div>
                </template>
                <el-text v-else type="info">{{ t('common.none') }}</el-text>
              </el-card>
            </el-col>
          </el-row>

          <el-collapse class="prompt-box">
            <el-collapse-item :title="t('render.promptTitle')">
              <el-text size="small">{{ result.prompt }}</el-text>
            </el-collapse-item>
          </el-collapse>
        </template>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.preview { max-height: 180px; border-radius: 6px; }
.up-ic { font-size: 42px; color: var(--el-color-primary); }
.tip { font-size: 12px; color: var(--el-text-color-secondary); }
.form { margin-top: 16px; }
.rhd { display: flex; align-items: center; justify-content: space-between; }
.render-img { width: 100%; max-height: 420px; border-radius: 8px; background: #f2f4f7; }
.st { margin-top: 8px; }
.fur { margin-bottom: 12px; }
.fur-img {
  width: 100%;
  height: 120px;
  border-radius: 6px;
  background: #f2f4f7;
  margin-bottom: 8px;
  cursor: zoom-in;
}
.fur-img-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-size: 26px;
  cursor: default;
}
.fur-name { font-weight: 600; font-size: 13px; }
.fur-meta { font-size: 12px; color: var(--el-text-color-secondary); margin: 2px 0; }
.fur-price { color: var(--el-color-danger); font-weight: 600; }
.rec { margin-top: 8px; }
.rec-name { font-weight: 600; }
.rec-meta { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--el-text-color-secondary); }
.rec-intro { font-size: 12px; margin-top: 6px; }
.prompt-box { margin-top: 12px; }
.note { margin-top: 4px; background: var(--el-fill-color-light); }
.note-text { margin: 0; white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 13px; line-height: 1.6; color: var(--el-text-color-primary); }
</style>
