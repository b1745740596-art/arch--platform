<script setup>
import InteriorScene from './InteriorScene.vue'

defineProps({
  variant: { type: String, default: 'living' },
  label: { type: String, default: '' },
  tone: { type: String, default: 'green' },
})
</script>

<template>
  <div class="phone-wrap" :class="`tone-${tone}`">
    <div class="phone">
      <div class="speaker"></div>
      <div class="island"></div>
      <div class="screen">
        <InteriorScene :variant="variant" />
        <div class="screen-ui">
          <span class="ui-pill">AI Render</span>
          <span class="ui-caption">Green · Oak</span>
        </div>
      </div>
      <div class="home-bar"></div>
    </div>
    <div v-if="label" class="phone-label">{{ label }}</div>
  </div>
</template>

<style scoped>
.phone-wrap {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
  max-width: 260px;
}

.phone {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 5;
  max-width: 260px;
  border-radius: 46px;
  padding: 10px;
  background: linear-gradient(145deg, #2c2f2d 0%, #111412 100%);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.14),
    0 24px 50px rgba(32, 43, 36, 0.24);
}

.speaker {
  position: absolute;
  top: 18px;
  left: 50%;
  width: 42px;
  height: 5px;
  border-radius: 999px;
  background: #1b1e1c;
  transform: translateX(-50%);
  z-index: 2;
}

.island {
  position: absolute;
  top: 13px;
  left: 50%;
  width: 92px;
  height: 24px;
  border-radius: 999px;
  background: #080908;
  transform: translateX(-50%);
  z-index: 3;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.screen {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 36px;
  background: #f1efe8;
}

.screen-ui {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}

.ui-pill,
.ui-caption {
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #204b37;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(8px);
  box-shadow: 0 3px 12px rgba(45, 62, 52, 0.12);
}

.ui-caption {
  color: #8c5f33;
  background: rgba(242, 227, 206, 0.82);
}

.home-bar {
  position: absolute;
  bottom: 9px;
  left: 50%;
  width: 88px;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  transform: translateX(-50%);
  z-index: 4;
}

.phone-label {
  font-size: 13px;
  font-weight: 650;
  color: var(--brand-muted);
}

.tone-wood .phone {
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.14),
    0 24px 50px rgba(90, 60, 32, 0.22);
}

.tone-wood .ui-pill {
  color: #8c5f33;
}
</style>
