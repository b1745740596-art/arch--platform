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
const fileList = ref([])

const form = reactive({
  title: '',
  city: '',
  community: '',
  area: null,
  budget_min: null,
  budget_max: null,
  floorplan: null,
})

const rules = computed(() => ({
  title: [{ required: true, message: t('intake.rules.title'), trigger: 'blur' }],
  city: [{ required: true, message: t('intake.rules.city'), trigger: 'blur' }],
  area: [{ required: true, message: t('intake.rules.area'), trigger: 'blur' }],
}))

function onFileChange(file) {
  form.floorplan = file.raw
  fileList.value = [file]
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('title', form.title)
    fd.append('city', form.city)
    fd.append('community', form.community || '')
    if (form.area != null) fd.append('area', form.area)
    if (form.budget_min != null) fd.append('budget_min', form.budget_min)
    if (form.budget_max != null) fd.append('budget_max', form.budget_max)
    if (form.floorplan) fd.append('floorplan', form.floorplan)
    const project = await api.createProjectForm(fd)
    ElMessage.success(t('intake.created'))
    await api.generateSchemes(project.id)
    router.push(`/projects/${project.id}`)
  } catch (e) {
    ElMessage.error(t('common.submitFailed', { msg: e.message || e }))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="hd"><el-icon><UploadFilled /></el-icon> {{ t('intake.header') }}</div>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="140px" style="max-width:680px">
      <el-form-item :label="t('intake.title')" prop="title">
        <el-input v-model="form.title" :placeholder="t('intake.titlePlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('intake.city')" prop="city">
        <el-input v-model="form.city" :placeholder="t('intake.cityPlaceholder')" />
      </el-form-item>
      <el-form-item :label="t('intake.community')">
        <el-input v-model="form.community" :placeholder="t('intake.optional')" />
      </el-form-item>
      <el-form-item :label="t('intake.area')" prop="area">
        <el-input-number v-model="form.area" :min="1" :max="9999" :precision="1" />
      </el-form-item>
      <el-form-item :label="t('intake.budgetRange')">
        <el-input-number v-model="form.budget_min" :min="0" :step="10000" :placeholder="t('intake.budgetMin')" />
        <span style="margin:0 8px">—</span>
        <el-input-number v-model="form.budget_max" :min="0" :step="10000" :placeholder="t('intake.budgetMax')" />
      </el-form-item>
      <el-form-item :label="t('intake.floorplan')">
        <el-upload
          :auto-upload="false"
          :limit="1"
          :file-list="fileList"
          accept="image/jpeg,image/png"
          list-type="picture"
          :on-change="onFileChange"
        >
          <el-button type="primary" plain>{{ t('intake.pickImage') }}</el-button>
          <template #tip>
            <div class="tip">{{ t('intake.floorplanTip') }}</div>
          </template>
        </el-upload>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">
          {{ t('intake.submit') }}
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.tip { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
