<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const account = useAccountStore()
const formRef = ref()
const submitting = ref(false)

const uid = route.query.uid
const token = route.query.token

const form = reactive({
  new_password: '',
  new_password2: '',
})

const rules = computed(() => ({
  new_password: [
    { required: true, message: t('account.rules.newPassword'), trigger: 'blur' },
    { min: 8, message: t('auth.rules.passwordMin'), trigger: 'blur' },
  ],
  new_password2: [
    { required: true, message: t('account.rules.confirm'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.new_password) return callback(new Error(t('auth.rules.confirmMatch')))
        callback()
      },
      trigger: 'blur',
    },
  ],
}))

async function submit() {
  await formRef.value.validate()
  if (!uid || !token) {
    ElMessage.error(t('passwordReset.invalidLink'))
    return
  }
  submitting.value = true
  try {
    await account.confirmPasswordReset({
      uid: Number(uid),
      token,
      new_password: form.new_password,
    })
    ElMessage.success(t('passwordReset.resetSuccess'))
    router.push('/login')
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
    <template #header><b>{{ t('passwordReset.resetTitle') }}</b></template>
    <el-alert v-if="!uid || !token" type="warning" :closable="false" :title="t('passwordReset.invalidLink')" style="margin-bottom:16px" />
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item :label="t('account.newPassword')" prop="new_password">
        <el-input v-model="form.new_password" type="password" show-password />
      </el-form-item>
      <el-form-item :label="t('account.confirmNewPassword')" prop="new_password2">
        <el-input v-model="form.new_password2" type="password" show-password @keyup.enter="submit" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">{{ t('passwordReset.resetSubmit') }}</el-button>
        <el-button @click="router.push('/login')">{{ t('passwordReset.backToLogin') }}</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card { max-width: 460px; margin: 0 auto; }
</style>
