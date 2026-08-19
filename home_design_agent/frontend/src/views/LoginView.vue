<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'
import { appDefaultRoute } from '@/utils/app'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

const activeTab = ref('password')
const formRef = ref()
const phoneFormRef = ref()
const submitting = ref(false)
const phoneSubmitting = ref(false)
const codeSending = ref(false)
const countdown = ref(0)
let countdownTimer = null

const form = reactive({
  username: '',
  password: '',
})

const phoneForm = reactive({
  phone: '',
  code: '',
})

const rules = computed(() => ({
  username: [{ required: true, message: t('auth.rules.username'), trigger: 'blur' }],
  password: [{ required: true, message: t('auth.rules.passwordRequired'), trigger: 'blur' }],
}))

const phoneRules = computed(() => ({
  phone: [
    { required: true, message: t('auth.rules.phoneRequired'), trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: t('auth.rules.phoneInvalid'), trigger: 'blur' },
  ],
  code: [{ required: true, message: t('auth.rules.codeRequired'), trigger: 'blur' }],
}))

const emailFormRef = ref()
const emailSubmitting = ref(false)
const emailCodeSending = ref(false)
const emailCountdown = ref(0)
let emailCountdownTimer = null

const emailForm = reactive({
  email: '',
  code: '',
})

const emailRules = computed(() => ({
  email: [
    { required: true, message: t('auth.rules.email'), trigger: 'blur' },
    { type: 'email', message: t('auth.rules.email'), trigger: 'blur' },
  ],
  code: [{ required: true, message: t('auth.rules.codeRequired'), trigger: 'blur' }],
}))

function startCountdown(seconds) {
  countdown.value = seconds
  if (countdownTimer) clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

function startEmailCountdown(seconds) {
  emailCountdown.value = seconds
  if (emailCountdownTimer) clearInterval(emailCountdownTimer)
  emailCountdownTimer = setInterval(() => {
    emailCountdown.value -= 1
    if (emailCountdown.value <= 0) {
      clearInterval(emailCountdownTimer)
      emailCountdownTimer = null
    }
  }, 1000)
}

async function sendCode() {
  if (!/^1[3-9]\d{9}$/.test(phoneForm.phone.trim())) {
    ElMessage.error(t('auth.rules.phoneInvalid'))
    return
  }
  codeSending.value = true
  try {
    await api.sendPhoneLoginCode(phoneForm.phone.trim())
    ElMessage.success(t('auth.codeSent'))
    startCountdown(60)
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    codeSending.value = false
  }
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    await auth.login({ username: form.username.trim(), password: form.password })
    ElMessage.success(t('auth.loginSuccess'))
    router.push(route.query.redirect || appDefaultRoute())
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    submitting.value = false
  }
}

async function submitPhone() {
  await phoneFormRef.value.validate()
  phoneSubmitting.value = true
  try {
    await auth.phoneLogin({ phone: phoneForm.phone.trim(), code: phoneForm.code.trim() })
    ElMessage.success(t('auth.loginSuccess'))
    router.push(route.query.redirect || appDefaultRoute())
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    phoneSubmitting.value = false
  }
}

async function sendEmailCode() {
  if (!emailForm.email.trim()) {
    ElMessage.error(t('auth.rules.email'))
    return
  }
  emailCodeSending.value = true
  try {
    await api.sendEmailLoginCode(emailForm.email.trim())
    ElMessage.success(t('auth.codeSent'))
    startEmailCountdown(60)
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    emailCodeSending.value = false
  }
}

async function submitEmail() {
  await emailFormRef.value.validate()
  emailSubmitting.value = true
  try {
    await auth.emailLogin({ email: emailForm.email.trim(), code: emailForm.code.trim() })
    ElMessage.success(t('auth.loginSuccess'))
    router.push(route.query.redirect || appDefaultRoute())
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    emailSubmitting.value = false
  }
}

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (emailCountdownTimer) clearInterval(emailCountdownTimer)
})
</script>

<template>
  <el-card shadow="never" class="auth-card">
    <template #header><b>{{ t('auth.loginHeader') }}</b></template>

    <el-tabs v-model="activeTab">
      <el-tab-pane :label="t('auth.passwordLogin')" name="password">
        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
          <el-form-item :label="t('auth.username')" prop="username">
            <el-input v-model="form.username" :placeholder="t('auth.usernamePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('auth.password')" prop="password">
            <el-input v-model="form.password" type="password" show-password :placeholder="t('auth.passwordPlaceholder')" @keyup.enter="submit" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="submit">{{ t('auth.loginSubmit') }}</el-button>
            <el-button @click="router.push('/register')">{{ t('auth.registerSubmit') }}</el-button>
            <router-link class="forgot-link" to="/forgot-password">{{ t('passwordReset.forgotTitle') }}</router-link>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- 暂时隐藏手机验证码登录入口，代码保留 -->
      <el-tab-pane v-if="false" :label="t('auth.phoneLogin')" name="phone">
        <el-form ref="phoneFormRef" :model="phoneForm" :rules="phoneRules" label-width="100px">
          <el-form-item :label="t('account.phone')" prop="phone">
            <el-input v-model="phoneForm.phone" :placeholder="t('auth.phonePlaceholder')">
              <template #append>
                <el-button :disabled="countdown > 0" :loading="codeSending" @click="sendCode">
                  {{ countdown > 0 ? `${countdown}s` : t('auth.sendCode') }}
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="t('auth.code')" prop="code">
            <el-input v-model="phoneForm.code" maxlength="8" :placeholder="t('auth.codePlaceholder')" @keyup.enter="submitPhone" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="phoneSubmitting" @click="submitPhone">{{ t('auth.loginSubmit') }}</el-button>
            <el-button @click="router.push('/register')">{{ t('auth.registerSubmit') }}</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane :label="t('auth.emailLogin')" name="email">
        <el-form ref="emailFormRef" :model="emailForm" :rules="emailRules" label-width="100px">
          <el-form-item :label="t('auth.email')" prop="email">
            <el-input v-model="emailForm.email" :placeholder="t('auth.emailPlaceholder')">
              <template #append>
                <el-button :disabled="emailCountdown > 0" :loading="emailCodeSending" @click="sendEmailCode">
                  {{ emailCountdown > 0 ? `${emailCountdown}s` : t('auth.sendCode') }}
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item :label="t('auth.code')" prop="code">
            <el-input v-model="emailForm.code" maxlength="8" :placeholder="t('auth.codePlaceholder')" @keyup.enter="submitEmail" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="emailSubmitting" @click="submitEmail">{{ t('auth.loginSubmit') }}</el-button>
            <el-button @click="router.push('/register')">{{ t('auth.registerSubmit') }}</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<style scoped>
.auth-card { max-width: 460px; margin: 0 auto; }
.forgot-link { margin-left: auto; font-size: 13px; color: var(--brand-green); }
</style>
