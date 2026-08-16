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
  password: '',
})

const rules = computed(() => ({
  username: [{ required: true, message: t('auth.rules.username'), trigger: 'blur' }],
  password: [{ required: true, message: t('auth.rules.passwordRequired'), trigger: 'blur' }],
}))

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    await api.login({ username: form.username.trim(), password: form.password })
    ElMessage.success(t('auth.loginSuccess'))
    router.push('/')
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
    <template #header><b>{{ t('auth.loginHeader') }}</b></template>
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
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card { max-width: 460px; margin: 0 auto; }
</style>
