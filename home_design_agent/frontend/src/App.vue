<script setup>
import { useRoute, useRouter } from 'vue-router'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'
import { SUPPORTED_LOCALES, currentLocale, elementLocale, setLocale } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useAppUpdateStore } from '@/stores/appUpdate'
import { appDefaultRoute, isNativeApp } from '@/utils/app'
import AppSettingsDialog from '@/components/AppSettingsDialog.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const auth = useAuthStore()
const appUpdate = useAppUpdateStore()
const settingsVisible = ref(false)
let autoUpdatePromptShown = false

const isApp = computed(() => isNativeApp())
const defaultPath = computed(() => appDefaultRoute())
const logoutPath = computed(() => (isApp.value ? '/login' : '/'))

const navItems = computed(() => {
  const items = []
  if (!isApp.value) {
    items.push({ path: '/', key: 'nav.home', icon: 'HomeFilled' })
  }
  items.push({ path: '/my-home', key: 'nav.myHome', icon: 'House' })
  items.push({ path: '/requirement', key: 'nav.requirement', icon: 'ChatDotRound' })
  items.push({ path: '/intake', key: 'nav.intake', icon: 'UploadFilled' })
  if (auth.user) {
    items.push({ path: '/billing', key: 'nav.billing', icon: 'Wallet' })
  }
  if (auth.user?.is_staff || auth.user?.is_superuser) {
    items.push({ path: '/admin/users', key: 'nav.adminUsers', icon: 'UserFilled' })
    items.push({ path: '/admin/payments', key: 'nav.adminPayments', icon: 'TrendCharts' })
  }
  return items
})

const localeShort = computed(
  () => SUPPORTED_LOCALES.find((l) => l.value === currentLocale.value)?.short || '中',
)
const avatarLetter = computed(() => (auth.user?.username || 'U').slice(0, 1).toUpperCase())

function isActive(path) {
  return path === '/' ? route.path === '/' : route.path.startsWith(path)
}

function switchLocale(locale) {
  setLocale(locale)
  document.title = t('brand')
}

async function doLogout() {
  await auth.logout()
  router.push(logoutPath.value)
}

async function configureAppChrome() {
  if (!isApp.value) return
  try {
    const { StatusBar, Style } = await import('@capacitor/status-bar')
    await StatusBar.setBackgroundColor({ color: '#f6f1e8' })
    await StatusBar.setStyle({ style: Style.Dark })
  } catch {
    // 状态栏插件不可用时降级，不影响页面渲染。
  }
}

onMounted(() => {
  auth.restoreSession()
  if (isApp.value) appUpdate.check()
  configureAppChrome()
})

watch(
  () => appUpdate.updateAvailable,
  async (available) => {
    if (!isApp.value || !available || autoUpdatePromptShown) return
    autoUpdatePromptShown = true
    try {
      await ElMessageBox.confirm(
        t('appUpdate.autoAvailable', { version: appUpdate.latest?.version || '' }),
        t('appUpdate.updateTitle'),
        {
          confirmButtonText: t('appUpdate.updateNow'),
          cancelButtonText: t('appUpdate.later'),
          type: 'info',
        },
      )
      appUpdate.downloadLatest()
    } catch {
      // 用户选择稍后，可随时从头像下的“设置”进入再检查。
    }
  },
)
</script>

<template>
  <el-config-provider :locale="elementLocale">
    <div class="app" :class="{ 'is-app': isApp }">
      <header v-if="!isApp" class="topbar">
        <div class="topbar-inner">
          <router-link class="brand" :to="defaultPath">
            <span class="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <rect x="3" y="3" width="34" height="34" rx="11" fill="#2f6b4f" />
                <path d="M9 24 L14 16 L19 22 L24 12 L31 24 Z" fill="#c89662" />
                <path d="M9 24 H31 V29 H9 Z" fill="#f6f1e8" />
              </svg>
            </span>
            <span class="brand-copy">
              <b>{{ t('brand') }}</b>
              <small>{{ currentLocale === 'en-US' ? 'Home Design AI' : 'AI 家装设计' }}</small>
            </span>
          </router-link>

          <nav v-if="!isApp" class="nav" aria-label="Main navigation">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              class="nav-item"
              :class="{ active: isActive(item.path) }"
            >
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ t(item.key) }}</span>
            </router-link>
          </nav>

          <div class="actions">
            <el-dropdown trigger="click" @command="switchLocale">
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

            <template v-if="auth.user">
              <el-dropdown trigger="click">
                <div class="user-chip" :title="auth.user.username" style="cursor:pointer">
                  <span class="avatar">{{ avatarLetter }}</span>
                  <span class="username">{{ auth.user.username }}</span>
                  <el-icon class="lang-arrow"><ArrowDown /></el-icon>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="router.push('/account')">{{ t('nav.account') }}</el-dropdown-item>
                    <el-dropdown-item @click="router.push('/billing')">{{ t('nav.billing') }}</el-dropdown-item>
                    <el-dropdown-item
                      v-if="auth.user.is_staff || auth.user.is_superuser"
                      @click="router.push('/admin/users')"
                    >
                      {{ t('nav.adminUsers') }}
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="auth.user.is_staff || auth.user.is_superuser"
                      @click="router.push('/admin/payments')"
                    >
                      {{ t('nav.adminPayments') }}
                    </el-dropdown-item>
                    <el-dropdown-item divided @click="doLogout">{{ t('auth.logout') }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
            <template v-else>
              <router-link class="auth-link" to="/login">{{ t('nav.login') }}</router-link>
              <router-link class="auth-link primary" to="/register">{{ t('nav.register') }}</router-link>
            </template>
          </div>
        </div>
      </header>

      <main class="app-main">
        <RouterView v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </main>

      <nav v-if="isApp" class="app-tabbar" aria-label="App navigation">
        <router-link
          class="tabbar-item"
          :class="{ active: route.path === '/my-home' }"
          to="/my-home"
        >
          <el-icon><House /></el-icon>
          <span>{{ t('nav.myHome') }}</span>
        </router-link>
        <button
          type="button"
          class="tabbar-item"
          :class="{ active: settingsVisible }"
          @click="settingsVisible = true"
        >
          <span class="tabbar-icon-wrap">
            <el-icon><User /></el-icon>
            <span v-if="appUpdate.updateAvailable" class="update-dot"></span>
          </span>
          <span>{{ t('appUpdate.my') }}</span>
        </button>
      </nav>

      <footer v-if="!isApp" class="app-footer">
        <div class="footer-inner">
          <span class="footer-dot"></span>
          <span>{{ t('footer') }}</span>
        </div>
      </footer>

      <AppSettingsDialog v-model="settingsVisible" />
    </div>
  </el-config-provider>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(246, 241, 232, 0.76);
  backdrop-filter: saturate(160%) blur(20px);
  -webkit-backdrop-filter: saturate(160%) blur(20px);
  border-bottom: 1px solid rgba(47, 107, 79, 0.10);
}

.topbar::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, #2f6b4f 0%, #c89662 55%, transparent 100%);
  opacity: 0.75;
}

.topbar-inner {
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 22px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
  color: var(--brand-ink);
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  box-shadow: 0 7px 16px rgba(47, 107, 79, 0.18);
}

.brand-mark svg { width: 40px; height: 40px; }

.brand-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.12;
}

.brand-copy b { font-size: 16px; letter-spacing: -0.01em; }
.brand-copy small { font-size: 11px; color: var(--brand-muted); font-weight: 600; }

.nav {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav::-webkit-scrollbar { display: none; }

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 12px;
  color: var(--brand-muted);
  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;
  transition: color 0.18s ease, background 0.18s ease;
}

.nav-item:hover { color: var(--brand-green); background: rgba(47, 107, 79, 0.07); }
.nav-item.active { color: var(--brand-green-deep); background: rgba(47, 107, 79, 0.11); }

.actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.lang-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  padding: 0 10px;
  border-radius: 999px;
  color: var(--brand-green-deep);
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(47, 107, 79, 0.14);
  font-size: 13px;
  cursor: pointer;
  outline: none;
  transition: transform 0.16s ease, background 0.16s ease;
}

.lang-trigger:hover { transform: translateY(-1px); background: #fff; }
.lang-text { font-weight: 700; letter-spacing: 0.4px; }
.lang-arrow { font-size: 12px; }

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 11px 0 5px;
  border-radius: 999px;
  background: var(--brand-wood-soft);
  border: 1px solid rgba(140, 95, 51, 0.16);
}

.avatar {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b7a5b, #204b37);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}

.username { max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 650; color: var(--brand-wood-deep); }

.ghost-link {
  border: 0;
  background: transparent;
  color: var(--brand-muted);
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}

.ghost-link:hover { color: var(--brand-green); }

.auth-link {
  padding: 8px 13px;
  border-radius: 999px;
  color: var(--brand-green-deep);
  font-size: 13px;
  font-weight: 700;
  border: 1px solid rgba(47, 107, 79, 0.16);
}

.auth-link.primary {
  color: #fff;
  border-color: transparent;
  background: linear-gradient(135deg, #3b7a5b, #2f6b4f);
  box-shadow: 0 8px 18px rgba(47, 107, 79, 0.18);
}

.app-main {
  flex: 1;
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 24px 48px;
}

.app-footer {
  border-top: 1px solid rgba(47, 107, 79, 0.09);
  background: rgba(255, 255, 255, 0.35);
}

.footer-inner {
  max-width: 1180px;
  margin: 0 auto;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--brand-muted);
  font-size: 12px;
  text-align: center;
}

.footer-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-green);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.10);
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* App 端（Capacitor / 原生壳）：更像移动端首页，去掉营销型布局的余量，
   让核心功能尽量顶到首屏。 */
.app.is-app {
  background: var(--brand-ivory);
}

.app.is-app .topbar.is-app {
  background: var(--brand-ivory);
  border-bottom: none;
  box-shadow: none;
}

.app.is-app .topbar.is-app::after {
  display: none;
}

.app.is-app .topbar.is-app .topbar-inner {
  max-width: none;
  padding: 10px 14px;
  gap: 12px;
}

.app.is-app .topbar.is-app .brand-mark {
  width: 36px;
  height: 36px;
}

.app.is-app .topbar.is-app .brand-copy b { font-size: 15px; }

.app.is-app .topbar.is-app .nav {
  justify-content: flex-start;
  gap: 2px;
}

.app.is-app .topbar.is-app .nav-item {
  padding: 7px 10px;
}

.app.is-app .app-main {
  max-width: none;
  padding: 12px 12px 84px;
}

.app-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 60;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px;
  padding: 8px 8px calc(8px + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.94);
  border-top: 1px solid rgba(47, 107, 79, 0.10);
  box-shadow: 0 -8px 24px rgba(45, 62, 52, 0.10);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.tabbar-item {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
  padding: 5px 4px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: var(--brand-muted);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.18s ease, background 0.18s ease, transform 0.18s ease;
}

.tabbar-item :deep(.el-icon),
.tabbar-item .el-icon {
  font-size: 20px;
}

.tabbar-item:active { transform: scale(0.96); }
.tabbar-item.active {
  color: var(--brand-green-deep);
  background: rgba(47, 107, 79, 0.08);
}

.tabbar-icon-wrap {
  position: relative;
  display: inline-flex;
}

.tabbar-icon-wrap .update-dot {
  position: absolute;
  top: -1px;
  right: -5px;
}

.settings-menu-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.update-dot {
  width: 7px;
  height: 7px;
  margin-left: 2px;
  border-radius: 50%;
  background: var(--el-color-danger);
  box-shadow: 0 0 0 3px rgba(245, 108, 108, 0.16);
}

@media (max-width: 860px) {
  .topbar-inner {
    flex-wrap: wrap;
    gap: 10px;
  }

  .nav {
    order: 3;
    flex-basis: 100%;
    justify-content: flex-start;
  }

  .actions { margin-left: auto; }
  .user-chip .username { display: none; }
}
</style>
