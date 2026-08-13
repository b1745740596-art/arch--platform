<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'
import { useTerm } from '@/i18n'

const router = useRouter()
const { t } = useI18n()
const term = useTerm()
const loading = ref(false)
const projects = ref([])

const statusType = {
  draft: 'info', recognized: 'info', requirement: 'warning',
  scheme: 'primary', lead: 'success', signed: 'success',
}

async function load() {
  loading.value = true
  try {
    const data = await api.listProjects()
    projects.value = data.results || data
  } catch (e) {
    ElMessage.error(t('common.loadFailed', { msg: e.message || e }))
  } finally {
    loading.value = false
  }
}
onMounted(load)

function money(v) {
  return v == null ? t('common.dash') : '¥' + Number(v).toLocaleString()
}
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div class="hd">
        <span>{{ t('projects.header') }}</span>
        <el-button type="primary" @click="router.push('/intake')">
          <el-icon><Plus /></el-icon> {{ t('projects.create') }}
        </el-button>
      </div>
    </template>

    <el-empty v-if="!loading && projects.length === 0" :description="t('projects.empty')">
      <el-button type="primary" @click="router.push('/intake')">{{ t('projects.uploadFloorplan') }}</el-button>
    </el-empty>

    <el-table v-else v-loading="loading" :data="projects" @row-click="(r) => router.push(`/projects/${r.id}`)"
      style="width:100%; cursor:pointer">
      <el-table-column prop="title" :label="t('projects.colTitle')" min-width="160" />
      <el-table-column prop="city" :label="t('projects.colCity')" width="90" />
      <el-table-column prop="community" :label="t('projects.colCommunity')" min-width="120" />
      <el-table-column prop="area" :label="t('projects.colArea')" width="100" />
      <el-table-column :label="t('projects.colBudget')" min-width="180">
        <template #default="{ row }">{{ money(row.budget_min) }} — {{ money(row.budget_max) }}</template>
      </el-table-column>
      <el-table-column :label="t('projects.colSchemes')" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.scheme_count }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('projects.colStatus')" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType[row.status] || 'info'">{{ term(row.status_display) }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
</style>
