<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'

const { t } = useI18n()
const formRef = ref()
const submitting = ref(false)
const loadingOptions = ref(true)
const verifiedPhone = ref('')
const verificationConfig = reactive({
  phone_verification_enabled: false,
})

const form = reactive({
  name: '',
  phone: '',
  city: '',
  community: '',
  room_type: '',
  style: '',
  budget_min: null,
  budget_max: null,
  requirement: '',
})

const options = reactive({
  room_types: ['客厅', '主卧', '次卧', '衣帽间', '厨房', '卫生间', '书房', '餐厅'],
  styles: ['现代简约', '现代轻奢', '意式极简', '北欧', '中式', '日式'],
})

const phoneRule = {
  validator: (rule, value, callback) => {
    if (!value) return callback(new Error(t('requirement.rules.phoneRequired')))
    if (!/^1[3-9]\d{9}$/.test(value)) return callback(new Error(t('requirement.rules.phoneInvalid')))
    if (verificationConfig.phone_verification_enabled) {
      if (!verifiedPhone.value) return callback(new Error(t('requirement.rules.phoneBindRequired')))
      if (value !== verifiedPhone.value) return callback(new Error(t('requirement.rules.phoneMismatch')))
    }
    callback()
  },
  trigger: 'blur',
}

const rules = computed(() => ({
  name: [{ required: true, message: t('requirement.rules.name'), trigger: 'blur' }],
  phone: [phoneRule],
}))

async function loadOptions() {
  try {
    const data = await api.getPromptOptions()
    if (data?.room_types?.length) options.room_types = data.room_types
    if (data?.styles?.length) options.styles = data.styles
  } catch {
    // 选项服务不可用时使用内置兜底
  } finally {
    loadingOptions.value = false
  }
}

async function loadProfile() {
  try {
    const profile = await api.getProfile()
    verifiedPhone.value = profile?.phone || ''
    if (verifiedPhone.value) form.phone = verifiedPhone.value
    if (!form.name && profile?.display_name) form.name = profile.display_name
  } catch {
    verifiedPhone.value = ''
  }
}

async function loadVerificationConfig() {
  try {
    Object.assign(verificationConfig, await api.getVerificationConfig())
  } catch {
    // 默认关闭验证要求，保持联系方式表单可用。
  }
}

onMounted(() => {
  loadOptions()
  loadProfile()
  loadVerificationConfig()
})

async function submit() {
  await formRef.value.validate()
  if (form.budget_min != null && form.budget_max != null && form.budget_min > form.budget_max) {
    ElMessage.warning(t('requirement.rules.budgetRange'))
    return
  }
  submitting.value = true
  try {
    await api.createRequirement({
      name: form.name,
      phone: form.phone,
      city: form.city || '',
      community: form.community || '',
      room_type: form.room_type || '',
      style: form.style || '',
      budget_min: form.budget_min,
      budget_max: form.budget_max,
      requirement: form.requirement || '',
    })
    ElMessage.success(t('requirement.submitted'))
    formRef.value.resetFields()
    form.phone = verifiedPhone.value
    form.budget_min = null
    form.budget_max = null
  } catch (e) {
    const data = e?.response?.data
    const msg = data ? Object.values(data).flat().join('；') : e.message
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="hd">
        <el-icon><UserFilled /></el-icon>
        <span>{{ t('requirement.header') }}</span>
      </div>
    </template>

    <p class="sub">{{ t('requirement.subtitle') }}</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" style="max-width:680px">
      <el-form-item :label="t('requirement.name')" prop="name">
        <el-input v-model="form.name" :placeholder="t('requirement.namePlaceholder')" />
      </el-form-item>

      <el-form-item :label="t('requirement.phone')" prop="phone">
        <div class="phone-field">
          <el-input
            v-model="form.phone"
            maxlength="11"
            :disabled="verificationConfig.phone_verification_enabled && Boolean(verifiedPhone)"
            :placeholder="t('requirement.phonePlaceholder')"
          />
          <small v-if="verificationConfig.phone_verification_enabled && verifiedPhone">
            {{ t('requirement.phoneVerified') }}
          </small>
          <small v-else-if="verificationConfig.phone_verification_enabled">
            {{ t('requirement.phoneBindRequired') }}
            <router-link to="/account">{{ t('requirement.bindNow') }}</router-link>
          </small>
          <small v-else>{{ t('requirement.phoneVerificationOff') }}</small>
        </div>
      </el-form-item>

      <el-form-item :label="t('requirement.city')">
        <el-input v-model="form.city" :placeholder="t('requirement.optional')" />
      </el-form-item>

      <el-form-item :label="t('requirement.community')">
        <el-input v-model="form.community" :placeholder="t('requirement.optional')" />
      </el-form-item>

      <el-form-item :label="t('requirement.roomType')">
        <el-select v-model="form.room_type" clearable :loading="loadingOptions" :placeholder="t('requirement.optional')" style="width:100%">
          <el-option v-for="r in options.room_types" :key="r" :label="r" :value="r" />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('requirement.style')">
        <el-select v-model="form.style" clearable :loading="loadingOptions" :placeholder="t('requirement.optional')" style="width:100%">
          <el-option v-for="s in options.styles" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('requirement.budgetRange')">
        <el-input-number v-model="form.budget_min" :min="0" :step="10000" :placeholder="t('requirement.budgetMin')" />
        <span style="margin:0 8px">—</span>
        <el-input-number v-model="form.budget_max" :min="0" :step="10000" :placeholder="t('requirement.budgetMax')" />
      </el-form-item>

      <el-form-item :label="t('requirement.requirement')">
        <el-input
          v-model="form.requirement"
          type="textarea"
          :rows="4"
          maxlength="300"
          show-word-limit
          :placeholder="t('requirement.requirementPlaceholder')"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">
          {{ t('requirement.submit') }}
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.sub { color: var(--el-text-color-secondary); margin: 0 0 18px; }
.phone-field { width: 100%; }
.phone-field small { display: block; margin-top: 4px; color: var(--el-text-color-secondary); line-height: 1.4; }
.phone-field a { margin-left: 4px; color: var(--el-color-primary); }
</style>
