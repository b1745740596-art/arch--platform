<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'

const router = useRouter()
const { t } = useI18n()
const formRef = ref()
const submitting = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  password2: '',
})

const rules = computed(() => ({
  username: [{ required: true, message: t('auth.rules.username'), trigger: 'blur' }],
  email: [{ type: 'email', message: t('auth.rules.email'), trigger: 'blur' }],
  password: [
    { required: true, message: t('auth.rules.passwordRequired'), trigger: 'blur' },
    { min: 8, message: t('auth.rules.passwordMin'), trigger: 'blur' },
  ],
  password2: [
    { required: true, message: t('auth.rules.confirmRequired'), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) return callback(new Error(t('auth.rules.confirmMatch')))
        callback()
      },
      trigger: 'blur',
    },
  ],
}))

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    await api.register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      password2: form.password2,
    })
    ElMessage.success(t('auth.registerSuccess'))
    router.push('/login')
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
  <el-card shadow="never" class="auth-card">
    <template #header><b>{{ t('auth.registerHeader') }}</b></template>
    <el-alert type="info" :closable="false" :title="t('auth.noBackend')" style="margin-bottom:16px" />
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item :label="t('auth.username')" prop="username">
        <el-input v-model="form.username" :placeholder="t('auth.usernamePlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" :placeholder="t('auth.emailPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('auth.password')" prop="password">
        <el-input v-model="form.password" type="password" show-password :placeholder="t('auth.passwordPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('auth.confirmPassword')" prop="password2">
        <el-input v-model="form.password2" type="password" show-password :placeholder="t('auth.confirmPassword')" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">{{ t('auth.registerSubmit') }}</el-button>
        <el-button @click="router.push('/login')">{{ t('auth.loginSubmit') }}</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card { max-width: 460px; margin: 0 auto; }
</style>
