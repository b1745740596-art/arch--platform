<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'

const { t } = useI18n()
const router = useRouter()
const account = useAccountStore()
const profileRef = ref()
const passwordRef = ref()
const savingProfile = ref(false)
const savingPassword = ref(false)

const totalCredits = computed(
  () => (account.profile?.free_credits || 0) + (account.profile?.purchased_credits || 0),
)

const localeOptions = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
]
const timezoneOptions = [
  { value: 'Asia/Shanghai', label: 'Asia/Shanghai (UTC+8)' },
  { value: 'UTC', label: 'UTC' },
]

const profileForm = reactive({
  display_name: '',
  bio: '',
  locale: 'zh-CN',
  timezone: 'Asia/Shanghai',
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  new_password2: '',
})

const passwordRules = computed(() => ({
  old_password: [{ required: true, message: t('account.rules.oldPassword'), trigger: 'blur' }],
  new_password: [
    { required: true, message: t('account.rules.newPassword'), trigger: 'blur' },
    { min: 8, message: t('auth.rules.passwordMin'), trigger: 'blur' },
  ],
  new_password2: [
    { required: true, message: t('account.rules.confirm'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.new_password) return callback(new Error(t('auth.rules.confirmMatch')))
        callback()
      },
      trigger: 'blur',
    },
  ],
}))

const phoneBindRef = ref()
const phoneBinding = ref(false)
const phoneCodeSending = ref(false)
const phoneCountdown = ref(0)
let phoneCountdownTimer = null

const phoneBindForm = reactive({
  phone: '',
  code: '',
})

const phoneBindRules = computed(() => ({
  phone: [
    { required: true, message: t('auth.rules.phoneRequired'), trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: t('auth.rules.phoneInvalid'), trigger: 'blur' },
  ],
  code: [{ required: true, message: t('auth.rules.codeRequired'), trigger: 'blur' }],
}))

function startPhoneCountdown(seconds) {
  phoneCountdown.value = seconds
  if (phoneCountdownTimer) clearInterval(phoneCountdownTimer)
  phoneCountdownTimer = setInterval(() => {
    phoneCountdown.value -= 1
    if (phoneCountdown.value <= 0) {
      clearInterval(phoneCountdownTimer)
      phoneCountdownTimer = null
    }
  }, 1000)
}

async function sendPhoneBindCode() {
  if (!/^1[3-9]\d{9}$/.test(phoneBindForm.phone.trim())) {
    ElMessage.error(t('auth.rules.phoneInvalid'))
    return
  }
  phoneCodeSending.value = true
  try {
    await account.sendPhoneBindCode(phoneBindForm.phone.trim())
    ElMessage.success(t('auth.codeSent'))
    startPhoneCountdown(60)
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    phoneCodeSending.value = false
  }
}

async function submitPhoneBind() {
  await phoneBindRef.value.validate()
  phoneBinding.value = true
  try {
    await account.bindPhone({
      phone: phoneBindForm.phone.trim(),
      code: phoneBindForm.code.trim(),
    })
    ElMessage.success(t('account.phoneBound'))
    phoneBindForm.code = ''
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    phoneBinding.value = false
  }
}

onUnmounted(() => {
  if (phoneCountdownTimer) clearInterval(phoneCountdownTimer)
})

onMounted(async () => {
  const data = await account.fetchProfile(true)
  if (data) {
    profileForm.display_name = data.display_name || ''
    profileForm.bio = data.bio || ''
    profileForm.locale = data.locale || 'zh-CN'
    profileForm.timezone = data.timezone || 'Asia/Shanghai'
  }
})

async function submitProfile() {
  await profileRef.value.validate()
  savingProfile.value = true
  try {
    await account.updateProfile({ ...profileForm })
    ElMessage.success(t('account.profileSaved'))
  } catch (e) {
    const data = e?.response?.data
    const msg = data ? Object.values(data).flat().join('；') : e.message
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    savingProfile.value = false
  }
}

async function submitPassword() {
  await passwordRef.value.validate()
  savingPassword.value = true
  try {
    await account.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.new_password2 = ''
    ElMessage.success(t('account.passwordChanged'))
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    savingPassword.value = false
  }
}
</script>

<template>
  <div class="account-page">
    <el-card shadow="never" class="credit-card">
      <div class="credit-info">
        <div>
          <span>{{ t('account.creditTitle') }}</span>
          <b>{{ totalCredits }}</b>
        </div>
        <div class="credit-detail">
          {{ t('account.freeCredits', { n: account.profile?.free_credits || 0 }) }} ·
          {{ t('account.purchasedCredits', { n: account.profile?.purchased_credits || 0 }) }}
        </div>
      </div>
      <el-button type="primary" @click="router.push('/billing')">{{ t('account.recharge') }}</el-button>
    </el-card>

    <el-card shadow="never">
      <template #header><b>{{ t('account.profileTitle') }}</b></template>
      <el-form ref="profileRef" :model="profileForm" label-width="100px">
        <el-form-item :label="t('auth.username')">
          <el-input :model-value="account.profile?.username" disabled />
        </el-form-item>
        <el-form-item :label="t('auth.email')">
          <el-input :model-value="account.profile?.email" disabled />
        </el-form-item>
        <el-form-item :label="t('account.displayName')" prop="display_name">
          <el-input v-model="profileForm.display_name" maxlength="50" />
        </el-form-item>
        <el-form-item :label="t('account.bio')" prop="bio">
          <el-input v-model="profileForm.bio" type="textarea" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('account.locale')" prop="locale">
          <el-select v-model="profileForm.locale" style="width: 100%">
            <el-option v-for="o in localeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('account.timezone')" prop="timezone">
          <el-select v-model="profileForm.timezone" style="width: 100%">
            <el-option v-for="o in timezoneOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingProfile" @click="submitProfile">{{ t('account.saveProfile') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><b>{{ t('account.phoneTitle') }}</b></template>
      <el-form ref="phoneBindRef" :model="phoneBindForm" :rules="phoneBindRules" label-width="100px">
        <el-form-item :label="t('account.currentPhone')">
          <el-input :model-value="account.profile?.phone || t('common.none')" disabled />
        </el-form-item>
        <el-form-item :label="t('account.phone')" prop="phone">
          <el-input v-model="phoneBindForm.phone" :placeholder="t('auth.phonePlaceholder')">
            <template #append>
              <el-button :disabled="phoneCountdown > 0" :loading="phoneCodeSending" @click="sendPhoneBindCode">
                {{ phoneCountdown > 0 ? `${phoneCountdown}s` : t('auth.sendCode') }}
              </el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item :label="t('auth.code')" prop="code">
          <el-input v-model="phoneBindForm.code" maxlength="8" :placeholder="t('auth.codePlaceholder')" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="phoneBinding" @click="submitPhoneBind">{{ t('account.bindPhone') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><b>{{ t('account.passwordTitle') }}</b></template>
      <el-form ref="passwordRef" :model="passwordForm" :rules="passwordRules" label-width="100px">
        <el-form-item :label="t('account.oldPassword')" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item :label="t('account.newPassword')" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item :label="t('account.confirmNewPassword')" prop="new_password2">
          <el-input v-model="passwordForm.new_password2" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingPassword" @click="submitPassword">{{ t('account.changePasswordSubmit') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.account-page { max-width: 720px; margin: 0 auto; }
.credit-card { margin-bottom: 16px; }
.credit-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.credit-info div:first-child span {
  display: block;
  margin-bottom: 4px;
  color: var(--brand-muted);
  font-size: 12px;
}
.credit-info div:first-child b {
  font-size: 30px;
  line-height: 1;
  color: var(--brand-green-deep);
}
.credit-detail {
  margin-top: 8px;
  color: var(--brand-muted);
  font-size: 12px;
}
</style>
