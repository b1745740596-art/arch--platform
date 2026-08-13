<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useHealthStore } from '@/stores/health'

const router = useRouter()
const health = useHealthStore()
const { t } = useI18n()
onMounted(() => health.check())

const steps = [
  { icon: 'UploadFilled', key: 'upload' },
  { icon: 'ChatDotRound', key: 'requirement' },
  { icon: 'MagicStick', key: 'generate' },
  { icon: 'ShoppingCart', key: 'furniture' },
  { icon: 'Phone', key: 'provider' },
]
</script>

<template>
  <div class="home">
    <el-card class="hero" shadow="never">
      <h1>{{ t('home.heroTitle') }}</h1>
      <p>{{ t('home.heroSubtitle') }}</p>
      <div class="cta">
        <el-button type="primary" size="large" @click="router.push('/render')">
          {{ t('home.ctaPrimary') }}
        </el-button>
        <el-button size="large" @click="router.push('/projects')">{{ t('home.ctaSecondary') }}</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" class="steps">
      <el-col v-for="s in steps" :key="s.key" :xs="24" :sm="12" :md="8" :lg="4">
        <el-card shadow="hover" class="step">
          <el-icon class="step-icon"><component :is="s.icon" /></el-icon>
          <div class="step-title">{{ t(`home.steps.${s.key}.title`) }}</div>
          <div class="step-desc">{{ t(`home.steps.${s.key}.desc`) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="health">
      <template #header>{{ t('home.health.title') }}</template>
      <el-skeleton v-if="health.loading" :rows="1" animated />
      <el-alert v-else-if="health.error" type="error" :closable="false"
        :title="t('home.health.failed', { msg: health.error })" />
      <el-descriptions v-else-if="health.status" :column="3" border>
        <el-descriptions-item :label="t('home.health.status')">
          <el-tag type="success">{{ health.status.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('home.health.app')">{{ health.status.app }}</el-descriptions-item>
        <el-descriptions-item :label="t('home.health.django')">{{ health.status.django }}</el-descriptions-item>
      </el-descriptions>
      <el-button text type="primary" @click="health.check()">{{ t('home.health.recheck') }}</el-button>
    </el-card>
  </div>
</template>

<style scoped>
.hero {
  text-align: center;
  padding: 24px 12px;
  background: linear-gradient(135deg, var(--el-color-primary-light-8), #fff);
}
.hero h1 { margin: 0 0 8px; font-size: 26px; }
.hero p { color: var(--el-text-color-secondary); margin: 0 0 20px; }
.cta { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.steps { margin: 20px 0; }
.step { text-align: center; margin-bottom: 16px; }
.step-icon { font-size: 30px; color: var(--el-color-primary); }
.step-title { font-weight: 600; margin: 8px 0 4px; }
.step-desc { font-size: 13px; color: var(--el-text-color-secondary); }
.health :deep(.el-button) { margin-top: 12px; }
</style>
