<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'

const router = useRouter()
const { t } = useI18n()
const account = useAccountStore()
const formRef = ref()
const submitting = ref(false)

const form = reactive({ email: '' })

const rules = {
  email: [
    { required: true, message: t('auth.rules.email'), trigger: 'blur' },
    { type: 'email', message: t('auth.rules.email'), trigger: 'blur' },
  ],
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    await account.requestPasswordReset({ email: form.email.trim() })
    ElMessage.success(t('passwordReset.sentHint'))
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never" class="auth-card">
    <template #header><b>{{ t('passwordReset.forgotTitle') }}</b></template>
    <el-alert type="info" :closable="false" :title="t('passwordReset.sentHint')" style="margin-bottom:16px" />
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" :placeholder="t('passwordReset.emailPlaceholder')" @keyup.enter="submit" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">{{ t('passwordReset.sendSubmit') }}</el-button>
        <el-button @click="router.push('/login')">{{ t('passwordReset.backToLogin') }}</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card { max-width: 460px; margin: 0 auto; }
</style>
