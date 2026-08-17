<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { currentLocale } from '@/i18n'
import { useHealthStore } from '@/stores/health'
import IphoneMock from '@/components/IphoneMock.vue'

const router = useRouter()
const health = useHealthStore()
const { t } = useI18n()
onMounted(() => health.check())

const steps = [
  { icon: 'UploadFilled', key: 'upload', tone: 'green' },
  { icon: 'ChatDotRound', key: 'requirement', tone: 'wood' },
  { icon: 'MagicStick', key: 'generate', tone: 'green' },
  { icon: 'ShoppingCart', key: 'furniture', tone: 'wood' },
  { icon: 'Phone', key: 'provider', tone: 'green' },
]

const showcase = [
  { variant: 'living', label: '现代客厅', en: 'Living room' },
  { variant: 'bedroom', label: '静谧卧室', en: 'Bedroom' },
  { variant: 'kitchen', label: '餐厨空间', en: 'Kitchen & dining' },
]
</script>

<template>
  <div class="home">
    <!-- Hero / 头图 -->
    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">
          <span class="eyebrow-dot"></span>
          {{ t('home.heroTagline') }}
        </span>
        <h1>{{ t('home.heroTitle') }}</h1>
        <p class="hero-sub">{{ t('home.heroSubtitle') }}</p>
        <div class="hero-cta">
          <el-button type="primary" size="large" @click="router.push('/my-home')">
            <el-icon><MagicStick /></el-icon>
            {{ t('home.ctaPrimary') }}
          </el-button>
          <el-button class="ghost-cta" size="large" @click="router.push('/my-home')">
            {{ t('home.ctaSecondary') }}
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
        <div class="hero-chips">
          <span class="chip"><el-icon><Picture /></el-icon> {{ t('home.chipRender') }}</span>
          <span class="chip"><el-icon><ShoppingCart /></el-icon> {{ t('home.chipFurniture') }}</span>
          <span class="chip"><el-icon><Phone /></el-icon> {{ t('home.chipAdvisor') }}</span>
        </div>
      </div>

      <div class="hero-visual" aria-label="AI interior render preview">
        <div class="hero-blob blob-green"></div>
        <div class="hero-blob blob-wood"></div>
        <div class="hero-phone">
          <IphoneMock variant="living" tone="green" />
        </div>
        <div class="float-note note-top">
          <el-icon><MagicStick /></el-icon>
          <span>{{ t('home.noteRender') }}</span>
        </div>
        <div class="float-note note-bottom">
          <el-icon><StarFilled /></el-icon>
          <span>{{ t('home.noteMatch') }}</span>
        </div>
      </div>
    </section>

    <!-- 效果图展示 -->
    <section class="showcase">
      <div class="section-head">
        <div>
          <span class="eyebrow">{{ t('home.showcaseEyebrow') }}</span>
          <h2>{{ t('home.showcaseTitle') }}</h2>
          <p>{{ t('home.showcaseSubtitle') }}</p>
        </div>
        <el-button class="section-action" @click="router.push('/my-home')">
          {{ t('home.showcaseAction') }}
          <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <div class="showcase-grid">
        <div v-for="(item, index) in showcase" :key="item.variant" class="showcase-card">
          <div class="showcase-stage">
            <IphoneMock :variant="item.variant" :tone="index === 1 ? 'wood' : 'green'" />
          </div>
          <div class="showcase-meta">
            <div class="showcase-title">{{ currentLocale === 'en-US' ? item.en : item.label }}</div>
            <div class="showcase-sub">{{ t(`home.showcase.${item.variant}`) }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 使用流程 -->
    <section class="steps">
      <div class="section-head">
        <div>
          <span class="eyebrow">{{ t('home.stepsEyebrow') }}</span>
          <h2>{{ t('home.stepsTitle') }}</h2>
        </div>
      </div>
      <div class="steps-grid">
        <div v-for="(s, index) in steps" :key="s.key" class="step" :class="`tone-${s.tone}`">
          <div class="step-index">0{{ index + 1 }}</div>
          <div class="step-icon"><el-icon><component :is="s.icon" /></el-icon></div>
          <div class="step-title">{{ t(`home.steps.${s.key}.title`) }}</div>
          <div class="step-desc">{{ t(`home.steps.${s.key}.desc`) }}</div>
        </div>
      </div>
    </section>

    <!-- 后端连通性 -->
    <el-card shadow="never" class="health">
      <template #header>
        <div class="health-head">
          <span class="health-title">
            <span class="status-dot"></span>
            {{ t('home.health.title') }}
          </span>
          <el-button text type="primary" @click="health.check()">
            <el-icon><Refresh /></el-icon>
            {{ t('home.health.recheck') }}
          </el-button>
        </div>
      </template>
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
    </el-card>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 34px;
}

.hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.02fr) minmax(300px, 0.98fr);
  align-items: center;
  gap: 30px;
  min-height: 520px;
  padding: 48px 44px;
  overflow: hidden;
  border-radius: 30px;
  background:
    radial-gradient(circle at 12% 14%, rgba(200, 150, 98, 0.28), transparent 34%),
    radial-gradient(circle at 82% 82%, rgba(47, 107, 79, 0.30), transparent 38%),
    linear-gradient(135deg, #fbf8f1 0%, #eef4ec 52%, #e6efe8 100%);
  border: 1px solid rgba(47, 107, 79, 0.10);
  box-shadow: var(--app-shadow);
}

.hero::after {
  content: '';
  position: absolute;
  inset: 14px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 22px;
  pointer-events: none;
}

.hero-copy { position: relative; z-index: 2; }

.hero h1 {
  margin: 18px 0 14px;
  max-width: 620px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1.02;
  letter-spacing: -0.045em;
  color: var(--brand-ink);
}

.hero-sub {
  margin: 0 0 26px;
  max-width: 570px;
  color: var(--brand-muted);
  font-size: 17px;
  line-height: 1.7;
}

.eyebrow-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-green);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.12);
}

.hero-cta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ghost-cta {
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(47, 107, 79, 0.16);
  color: var(--brand-green-deep);
}

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(47, 107, 79, 0.10);
  color: var(--brand-muted);
  font-size: 12px;
  font-weight: 650;
}

.chip :deep(.el-icon) { color: var(--brand-green); }

.hero-visual {
  position: relative;
  z-index: 1;
  min-height: 440px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(2px);
}

.blob-green {
  width: 300px;
  height: 300px;
  left: 6%;
  top: 8%;
  background: linear-gradient(135deg, rgba(47, 107, 79, 0.32), rgba(47, 107, 79, 0.04));
}

.blob-wood {
  width: 240px;
  height: 240px;
  right: -4%;
  bottom: 4%;
  background: linear-gradient(135deg, rgba(200, 150, 98, 0.42), rgba(200, 150, 98, 0.05));
}

.hero-phone {
  position: relative;
  z-index: 2;
  width: min(68%, 300px);
  animation: float 5.5s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(-1deg); }
  50% { transform: translateY(-12px) rotate(1deg); }
}

.float-note {
  position: absolute;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 12px;
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(47, 107, 79, 0.10);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(10px);
  color: var(--brand-ink);
  font-size: 12px;
  font-weight: 700;
}

.note-top { top: 10%; right: 1%; color: var(--brand-green-deep); }
.note-bottom { bottom: 12%; left: 0; color: var(--brand-wood-deep); }
.float-note :deep(.el-icon) { font-size: 15px; }

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
}

.section-head h2 {
  margin: 10px 0 6px;
  font-size: 30px;
  letter-spacing: -0.03em;
  color: var(--brand-ink);
}

.section-head p {
  margin: 0;
  color: var(--brand-muted);
  font-size: 14px;
}

.section-action {
  background: var(--brand-wood-soft);
  border: 1px solid rgba(140, 95, 51, 0.18);
  color: var(--brand-wood-deep);
}

.showcase {
  padding-top: 6px;
}

.showcase-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

.showcase-card {
  padding: 20px 16px 18px;
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(247, 243, 234, 0.88));
  border: 1px solid rgba(47, 107, 79, 0.10);
  box-shadow: var(--app-shadow-soft);
}

.showcase-stage {
  display: flex;
  justify-content: center;
  border-radius: 18px;
  background: rgba(47, 107, 79, 0.05);
  padding: 14px;
}

.showcase-meta { padding: 14px 4px 0; }
.showcase-title { font-size: 17px; font-weight: 750; color: var(--brand-ink); }
.showcase-sub { margin-top: 4px; font-size: 12px; color: var(--brand-muted); }

.steps { padding-top: 6px; }
.steps-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.step {
  position: relative;
  min-height: 184px;
  padding: 22px 16px 18px;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(47, 107, 79, 0.10);
  background: rgba(255, 255, 255, 0.74);
  box-shadow: var(--app-shadow-soft);
}

.step.tone-wood { background: linear-gradient(160deg, #fffdf8, #f3e5cf); }

.step-index {
  position: absolute;
  right: 12px;
  top: 8px;
  font-size: 26px;
  font-weight: 800;
  color: rgba(47, 107, 79, 0.10);
  letter-spacing: -0.04em;
}

.step-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: rgba(47, 107, 79, 0.12);
  color: var(--brand-green);
  font-size: 21px;
}

.step.tone-wood .step-icon {
  background: rgba(200, 150, 98, 0.16);
  color: var(--brand-wood-deep);
}

.step-title { margin-top: 14px; font-size: 15px; font-weight: 750; }
.step-desc { margin-top: 6px; font-size: 12px; line-height: 1.55; color: var(--brand-muted); }

.health { margin-top: 2px; }

.health-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.health-title {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  font-weight: 700;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--brand-green);
  box-shadow: 0 0 0 5px rgba(47, 107, 79, 0.12);
}

@media (max-width: 960px) {
  .hero {
    grid-template-columns: 1fr;
    padding: 34px 26px;
  }

  .hero-visual { min-height: 400px; }
  .showcase-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .steps-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .showcase-grid,
  .steps-grid { grid-template-columns: 1fr; }

  .section-head { flex-direction: column; align-items: flex-start; }
  .hero h1 { font-size: 36px; }
  .hero-sub { font-size: 15px; }
}
</style>

