<script setup>
import { useRoute, useRouter } from 'vue-router'
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { SUPPORTED_LOCALES, currentLocale, elementLocale, setLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const activeIndex = computed(() => route.path)
const { t } = useI18n()
const auth = useAuthStore()

const localeShort = computed(
  () => SUPPORTED_LOCALES.find((l) => l.value === currentLocale.value)?.short || '中',
)

function switchLocale(locale) {
  setLocale(locale)
  document.title = t('brand')
}

async function doLogout() {
  await auth.logout()
  router.push('/')
}

onMounted(() => {
  auth.fetchMe()
})
</script>

<template>
  <el-config-provider :locale="elementLocale">
    <el-container class="app">
    <el-header class="app-header">
      <div class="brand" @click="$router.push('/')">
        <el-icon><HomeFilled /></el-icon>
        <span>{{ t('brand') }}</span>
      </div>
      <el-menu
        :default-active="activeIndex"
        mode="horizontal"
        router
        class="nav"
        :ellipsis="false"
      >
        <el-menu-item index="/">{{ t('nav.home') }}</el-menu-item>
        <el-menu-item index="/render">{{ t('nav.render') }}</el-menu-item>
        <el-menu-item index="/studio">{{ t('nav.studio') }}</el-menu-item>
        <el-menu-item index="/projects">{{ t('nav.projects') }}</el-menu-item>
        <el-menu-item index="/requirement">{{ t('nav.requirement') }}</el-menu-item>
        <el-menu-item index="/intake">{{ t('nav.intake') }}</el-menu-item>
      </el-menu>

      <el-dropdown class="lang" trigger="click" @command="switchLocale">
        <span class="lang-trigger" :title="t('nav.language')">
          <el-icon><Switch /></el-icon>
          <span class="lang-text">{{ localeShort }}</span>
          <el-icon class="lang-arrow"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="l in SUPPORTED_LOCALES"
              :key="l.value"
              :command="l.value"
              :disabled="l.value === currentLocale"
            >
              {{ l.label }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <div class="user-actions">
        <template v-if="auth.user">
          <span class="username">{{ auth.user.username }}</span>
          <el-button text @click="doLogout">{{ t('auth.logout') }}</el-button>
        </template>
        <template v-else>
          <router-link class="user-link" to="/login">{{ t('nav.login') }}</router-link>
          <router-link class="user-link" to="/register">{{ t('nav.register') }}</router-link>
        </template>
      </div>
    </el-header>

    <el-main class="app-main">
      <RouterView />
    </el-main>

    <el-footer class="app-footer">
      {{ t('footer') }}
    </el-footer>
    </el-container>
  </el-config-provider>
</template>

<style scoped>
.app { min-height: 100vh; }
.app-header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: var(--el-color-primary);
  color: #fff;
  padding: 0 24px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.nav {
  flex: 1;
  background: transparent;
  border-bottom: none;
}
.nav :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.85);
  border-bottom: none;
}
.nav :deep(.el-menu-item.is-active),
.nav :deep(.el-menu-item:hover) {
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
}
.user-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 14px;
  color: #fff;
  font-size: 14px;
  white-space: nowrap;
}
.username { opacity: 0.92; }
.user-link {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
}
.user-link:hover { color: #fff; text-decoration: underline; }
.lang { flex: none; }
.lang-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 14px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  outline: none;
  background: rgba(255, 255, 255, 0.14);
  transition: background 0.2s;
}
.lang-trigger:hover { background: rgba(255, 255, 255, 0.26); }
.lang-text { font-weight: 600; letter-spacing: 0.5px; }
.lang-arrow { font-size: 12px; }
.app-main {
  max-width: 1080px;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
}
.app-footer {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  height: auto;
  padding: 16px;
}
</style>
