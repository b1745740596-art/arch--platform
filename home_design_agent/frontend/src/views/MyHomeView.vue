<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import StudioView from './StudioView.vue'
import { useStudioStore } from '@/stores/studio'
import { api } from '@/api/client'
import { currentLocale, useTerm } from '@/i18n'

const { t } = useI18n()
const term = useTerm()
const studio = useStudioStore()

const tab = ref('studio')
const reports = ref([])
const orders = ref([])
const reportsLoading = ref(false)
const ordersLoading = ref(false)
const orderSubmitting = ref(false)
const selectedReportId = ref(null)

const savedResultIds = new Set()

const TABS = [
  { key: 'studio', icon: 'Grid', labelKey: 'myHome.tabStudio' },
  { key: 'report', icon: 'Document', labelKey: 'myHome.tabReport' },
  { key: 'orders', icon: 'ShoppingCart', labelKey: 'myHome.tabOrders' },
]

const tierBudget = {
  经济: [80000, 160000],
  品质: [160000, 320000],
  高端: [320000, 600000],
}

const selectedReport = computed(
  () => reports.value.find((r) => r.id === selectedReportId.value) || reports.value[0] || null,
)

const reportData = computed(() => selectedReport.value?.report || {})

const reportStatusType = computed(() => (selectedReport.value?.status === 'ordered' ? 'success' : 'info'))

const orderStatusType = {
  pending: 'warning',
  confirmed: 'primary',
  paid: 'success',
  cancelled: 'info',
}

function money(v) {
  return v == null ? t('common.dash') : '¥' + Number(v).toLocaleString()
}

function furnitureTotal(report) {
  return (report?.furnitures || []).reduce((sum, f) => sum + (Number(f.price) || 0), 0)
}

function buildBudgetAdvice(win, total) {
  const range = tierBudget[win.form.budget_tier] || [120000, 280000]
  const extra = Math.max(0, Math.round(range[1] - total))
  return t('myHome.budgetAdvice', {
    min: money(range[0]),
    max: money(range[1]),
    furniture: money(total),
    extra: money(extra),
  })
}

function buildRenovationAdvice(report) {
  const base = t('myHome.renovationBase')
  const note = report?.design_note ? ` ${report.design_note}` : ''
  return `${base}${note}`
}

async function loadReports() {
  reportsLoading.value = true
  try {
    const data = await api.listReports()
    reports.value = Array.isArray(data) ? data : data?.results || []
    if (!selectedReportId.value && reports.value.length) {
      selectedReportId.value = reports.value[0].id
    }
  } catch (e) {
    reports.value = []
  } finally {
    reportsLoading.value = false
  }
}

async function loadOrders() {
  ordersLoading.value = true
  try {
    const data = await api.listOrders()
    orders.value = Array.isArray(data) ? data : data?.results || []
  } catch (e) {
    orders.value = []
  } finally {
    ordersLoading.value = false
  }
}

async function saveWindowReport(win) {
  const result = win.result
  if (!result?.id) return
  const furnitures = (result.furnitures || []).map((f) => ({
    id: f.id,
    name: f.name,
    brand: f.brand,
    category_display: f.category_display,
    price: f.price,
    buy_url: f.buy_url,
    image_url: f.image_url,
  }))
  const total = furnitures.reduce((sum, f) => sum + (Number(f.price) || 0), 0)
  const title = win.title || `${win.form.room_type}·${win.form.style}`
  const range = tierBudget[win.form.budget_tier] || [120000, 280000]

  try {
    const saved = await api.saveReport({
      project: win.projectId,
      render_job: result.id,
      title,
      room_type: win.form.room_type,
      style: win.form.style,
      budget_tier: win.form.budget_tier,
      report: {
        title,
        room_type: win.form.room_type,
        style: win.form.style,
        budget_tier: win.form.budget_tier,
        result_url: result.result_url || result.result_image_url || null,
        design_note: result.design_note || '',
        furnitures,
        designer: result.designer || null,
        contractor: result.contractor || null,
        applied_modules: result.applied_modules || [],
        budget_min: range[0],
        budget_max: range[1],
        furniture_total: total,
        budget_advice: buildBudgetAdvice(win, total),
      }
    })
    selectedReportId.value = saved.id
    await loadReports()
    ElMessage.success(t('myHome.reportSaved'))
  } catch (e) {
    // 自动保存失败不阻塞生成流程，用户仍可在报告页手工重试
    ElMessage.warning(t('myHome.reportSaveFailed', { msg: extractError(e) }))
  }
}

watch(
  () => studio.windows.map((w) => ({ id: w.id, status: w.status, resultId: w.result?.id })),
  (list) => {
    for (const item of list) {
      if (item.status !== 'success' || !item.resultId || savedResultIds.has(item.resultId)) continue
      const win = studio.windows.find((w) => w.id === item.id)
      if (!win) continue
      savedResultIds.add(item.resultId)
      saveWindowReport(win)
    }
  },
  { deep: true },
)

function extractError(e) {
  const data = e?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return String(data.detail)
  if (data) {
    const first = Object.entries(data)[0]
    if (first) return `${first[0]}: ${[].concat(first[1]).join('; ')}`
  }
  return e?.message || String(e || '')
}

async function placeOrder() {
  const report = selectedReport.value
  if (!report) {
    ElMessage.warning(t('myHome.selectReport'))
    return
  }
  orderSubmitting.value = true
  try {
    const data = report.report || {}
    await api.createOrder({
      project: report.project,
      report: report.id,
      title: report.title || data.title,
      amount_min: data.budget_min,
      amount_max: data.budget_max,
      payload: data,
    })
    ElMessage.success(t('myHome.orderCreated'))
    await Promise.all([loadOrders(), loadReports()])
    tab.value = 'orders'
  } catch (e) {
    ElMessage.error(t('myHome.orderFailed', { msg: extractError(e) }))
  } finally {
    orderSubmitting.value = false
  }
}

function selectReport(report) {
  selectedReportId.value = report.id
}

function openWorkbench() {
  if (studio.canAddWindow) studio.addWindow()
  tab.value = 'studio'
}

onMounted(() => {
  loadReports()
  loadOrders()
})
</script>

<template>
  <div class="my-home">
    <section class="home-head">
      <div class="head-copy">
        <span class="eyebrow">
          <span class="eyebrow-dot"></span>
          {{ t('myHome.subtitle') }}
        </span>
        <h1>{{ t('myHome.title') }}</h1>
        <p>{{ t('myHome.description') }}</p>
      </div>
      <el-button type="primary" size="large" @click="openWorkbench">
        <el-icon><Plus /></el-icon>
        {{ t('myHome.newTask') }}
      </el-button>
    </section>

    <div class="segmented">
      <button
        v-for="item in TABS"
        :key="item.key"
        type="button"
        class="seg-item"
        :class="{ active: tab === item.key }"
        @click="tab = item.key"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ t(item.labelKey) }}</span>
      </button>
    </div>

    <div v-show="tab === 'studio'" class="tab-panel">
      <StudioView />
    </div>

    <div v-show="tab === 'report'" class="tab-panel">
      <div class="report-layout">
        <aside class="report-list">
          <div class="list-head">
            <b>{{ t('myHome.reportList') }}</b>
            <el-tag size="small" type="info" effect="plain">{{ reports.length }}</el-tag>
          </div>
          <div v-if="reportsLoading" class="list-loading"><el-skeleton :rows="4" animated /></div>
          <div v-else-if="!reports.length" class="empty-state">
            <el-icon><Document /></el-icon>
            <span>{{ t('myHome.noReports') }}</span>
          </div>
          <button
            v-for="report in reports"
            :key="report.id"
            type="button"
            class="report-item"
            :class="{ active: report.id === selectedReport?.id }"
            @click="selectReport(report)"
          >
            <div class="report-item-title">{{ report.title || t('common.none') }}</div>
            <div class="report-item-meta">
              <span>{{ term(report.room_type) }} · {{ term(report.style) }}</span>
              <el-tag size="small" :type="report.status === 'ordered' ? 'success' : 'info'">
                {{ report.status_display }}
              </el-tag>
            </div>
          </button>
        </aside>

        <article v-if="selectedReport" class="report-detail">
          <div class="report-topbar">
            <div>
              <span class="report-kicker">{{ t('myHome.reportKicker') }}</span>
              <h2>{{ selectedReport.title || reportData.title || t('common.none') }}</h2>
              <p class="report-sub">
                {{ term(selectedReport.room_type) }} · {{ term(selectedReport.style) }} ·
                {{ term(selectedReport.budget_tier) }}
              </p>
            </div>
            <el-tag :type="reportStatusType">{{ selectedReport.status_display }}</el-tag>
          </div>

          <div v-if="reportData.result_url" class="report-hero">
            <img :src="reportData.result_url" :alt="selectedReport.title" />
          </div>
          <div v-else class="report-hero report-hero-empty">
            <el-icon><Picture /></el-icon>
            <span>{{ t('myHome.noImage') }}</span>
          </div>

          <section class="report-section">
            <h3><el-icon><EditPen /></el-icon> {{ t('myHome.designNote') }}</h3>
            <p class="report-text">{{ reportData.design_note || t('common.none') }}</p>
          </section>

          <section class="report-section">
            <h3><el-icon><Coin /></el-icon> {{ t('myHome.budgetAdviceTitle') }}</h3>
            <div class="budget-band">
              <div>
                <span>{{ t('myHome.budgetRange') }}</span>
                <b>{{ money(reportData.budget_min) }} — {{ money(reportData.budget_max) }}</b>
              </div>
              <div>
                <span>{{ t('myHome.furnitureTotal') }}</span>
                <b>{{ money(reportData.furniture_total) }}</b>
              </div>
            </div>
            <p class="report-text">{{ reportData.budget_advice }}</p>
          </section>

          <section class="report-section">
            <h3><el-icon><ShoppingCart /></el-icon> {{ t('myHome.furnitureList') }}</h3>
            <div v-if="reportData.furnitures?.length" class="furniture-grid">
              <div v-for="f in reportData.furnitures" :key="f.id" class="furniture-item">
                <img v-if="f.image_url" :src="f.image_url" :alt="f.name" />
                <div v-else class="furniture-ph"><el-icon><Picture /></el-icon></div>
                <div class="furniture-info">
                  <b>{{ f.name }}</b>
                  <span>{{ f.brand }} · {{ term(f.category_display) }}</span>
                  <em>{{ money(f.price) }}</em>
                </div>
              </div>
            </div>
            <p v-else class="report-text muted">{{ t('common.none') }}</p>
          </section>

          <div class="people-grid">
            <section class="report-section">
              <h3><el-icon><Avatar /></el-icon> {{ t('myHome.designer') }}</h3>
              <template v-if="reportData.designer">
                <b>{{ reportData.designer.name }} · {{ reportData.designer.title }}</b>
                <p class="report-text">{{ reportData.designer.intro }}</p>
                <div class="meta-line">
                  <span>{{ reportData.designer.city }}</span>
                  <span>{{ reportData.designer.years }} 年</span>
                </div>
              </template>
              <p v-else class="report-text muted">{{ t('common.none') }}</p>
            </section>
            <section class="report-section">
              <h3><el-icon><Tools /></el-icon> {{ t('myHome.contractor') }}</h3>
              <template v-if="reportData.contractor">
                <b>{{ reportData.contractor.name }}</b>
                <p class="report-text">{{ reportData.contractor.quote_range }}</p>
                <div class="meta-line">
                  <span>{{ reportData.contractor.city }}</span>
                  <span>{{ reportData.contractor.response_speed }}</span>
                </div>
              </template>
              <p v-else class="report-text muted">{{ t('common.none') }}</p>
            </section>
          </div>

          <section class="report-section">
            <h3><el-icon><Opportunity /></el-icon> {{ t('myHome.renovationAdvice') }}</h3>
            <p class="report-text">{{ buildRenovationAdvice(reportData) }}</p>
          </section>

          <div class="order-bar">
            <div>
              <b>{{ t('myHome.orderSummary') }}</b>
              <span>{{ money(reportData.budget_min) }} — {{ money(reportData.budget_max) }}</span>
            </div>
            <el-button
              type="primary"
              size="large"
              :loading="orderSubmitting"
              @click="placeOrder"
            >
              <el-icon><ShoppingBag /></el-icon>
              {{ t('myHome.placeOrder') }}
            </el-button>
          </div>
        </article>

        <div v-else class="report-detail report-detail-empty">
          <el-empty :description="t('myHome.noReports')" />
        </div>
      </div>
    </div>

    <div v-show="tab === 'orders'" class="tab-panel">
      <el-card shadow="never" class="orders-card">
        <template #header>
          <div class="orders-head">
            <b>{{ t('myHome.orders') }}</b>
            <el-button size="small" :loading="ordersLoading" @click="loadOrders">
              <el-icon><Refresh /></el-icon> {{ t('myHome.refresh') }}
            </el-button>
          </div>
        </template>

        <div v-if="ordersLoading" class="list-loading"><el-skeleton :rows="5" animated /></div>
        <el-empty v-else-if="!orders.length" :description="t('myHome.noOrders')" />
        <div v-else class="orders-list">
          <div v-for="order in orders" :key="order.id" class="order-item">
            <div class="order-icon"><el-icon><ShoppingBag /></el-icon></div>
            <div class="order-main">
              <b>{{ order.title || t('common.none') }}</b>
              <span>{{ order.created_at }}</span>
            </div>
            <div class="order-amount">{{ money(order.amount_min) }} — {{ money(order.amount_max) }}</div>
            <el-tag :type="orderStatusType[order.status] || 'info'">{{ order.status_display }}</el-tag>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.my-home {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.home-head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  overflow: hidden;
  border-radius: 26px;
  border: 1px solid rgba(47, 107, 79, 0.10);
  background:
    radial-gradient(circle at 85% 0%, rgba(200, 150, 98, 0.26), transparent 32%),
    linear-gradient(135deg, #fbf8f1, #eef4ec);
  box-shadow: var(--app-shadow);
}

.eyebrow-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-green);
  box-shadow: 0 0 0 4px rgba(47, 107, 79, 0.12);
}

.head-copy h1 {
  margin: 12px 0 6px;
  font-size: 34px;
  letter-spacing: -0.04em;
  color: var(--brand-ink);
}

.head-copy p {
  margin: 0;
  color: var(--brand-muted);
  font-size: 14px;
}

.segmented {
  display: inline-flex;
  align-self: center;
  padding: 5px;
  gap: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(47, 107, 79, 0.10);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(14px);
}

.seg-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 16px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--brand-muted);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.seg-item.active {
  background: linear-gradient(135deg, #3b7a5b, #2f6b4f);
  color: #fff;
  box-shadow: 0 7px 16px rgba(47, 107, 79, 0.20);
}

.tab-panel { min-width: 0; }

.report-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.report-list,
.report-detail,
.orders-card {
  border-radius: 22px;
  border: 1px solid rgba(47, 107, 79, 0.10);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: var(--app-shadow-soft);
  backdrop-filter: blur(14px);
}

.report-list {
  position: sticky;
  top: 88px;
  padding: 16px;
  max-height: calc(100vh - 108px);
  overflow: auto;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px 12px;
  border-bottom: 1px solid rgba(47, 107, 79, 0.08);
}

.list-loading { padding: 12px 4px; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 34px 0;
  color: var(--brand-muted);
  font-size: 13px;
}

.empty-state :deep(.el-icon) { font-size: 30px; }

.report-item {
  width: 100%;
  display: block;
  text-align: left;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 14px;
  background: rgba(47, 107, 79, 0.04);
  cursor: pointer;
  font: inherit;
  color: var(--brand-ink);
  transition: border-color 0.18s ease, background 0.18s ease;
}

.report-item:hover { border-color: rgba(47, 107, 79, 0.14); }
.report-item.active { border-color: rgba(47, 107, 79, 0.28); background: rgba(47, 107, 79, 0.09); }

.report-item-title {
  font-size: 14px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--brand-muted);
}

.report-detail {
  padding: 26px;
}

.report-detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
}

.report-topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.report-kicker {
  display: inline-block;
  margin-bottom: 6px;
  color: var(--brand-green);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.report-topbar h2 { margin: 0; font-size: 24px; letter-spacing: -0.03em; }
.report-sub { margin: 6px 0 0; color: var(--brand-muted); font-size: 13px; }

.report-hero {
  height: 300px;
  margin-bottom: 20px;
  border-radius: 18px;
  overflow: hidden;
  background: #eef2ec;
  display: grid;
  place-items: center;
}

.report-hero img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.report-hero-empty {
  flex-direction: column;
  gap: 8px;
  color: var(--brand-muted);
  font-size: 13px;
}

.report-hero-empty :deep(.el-icon) { font-size: 42px; }

.report-section {
  padding: 16px 0;
  border-top: 1px solid rgba(47, 107, 79, 0.08);
}

.report-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  font-size: 15px;
  color: var(--brand-green-deep);
}

.report-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--brand-ink);
  font-size: 13px;
  line-height: 1.75;
}

.budget-band {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.budget-band > div {
  padding: 14px;
  border-radius: 14px;
  background: rgba(47, 107, 79, 0.07);
}

.budget-band span {
  display: block;
  color: var(--brand-muted);
  font-size: 12px;
}

.budget-band b { font-size: 18px; color: var(--brand-green-deep); }

.furniture-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.furniture-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(200, 150, 98, 0.07);
}

.furniture-item img,
.furniture-ph {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  object-fit: cover;
  flex: none;
}

.furniture-ph {
  display: grid;
  place-items: center;
  color: var(--brand-muted);
  background: rgba(47, 107, 79, 0.08);
}

.furniture-info { min-width: 0; display: flex; flex-direction: column; }
.furniture-info b { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.furniture-info span { font-size: 11px; color: var(--brand-muted); margin-top: 2px; }
.furniture-info em { font-style: normal; font-size: 13px; font-weight: 800; color: var(--brand-wood-deep); margin-top: auto; }

.people-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.meta-line { display: flex; flex-wrap: wrap; gap: 10px; color: var(--brand-muted); font-size: 12px; margin-top: 8px; }

.order-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #eef4ec, #f7ead8);
}

.order-bar > div { display: flex; flex-direction: column; gap: 4px; }
.order-bar span { color: var(--brand-muted); font-size: 13px; }

.orders-head { display: flex; align-items: center; justify-content: space-between; }

.orders-list { display: flex; flex-direction: column; gap: 10px; }

.order-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(47, 107, 79, 0.05);
}

.order-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(47, 107, 79, 0.12);
  color: var(--brand-green);
  font-size: 19px;
}

.order-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.order-main b { font-size: 14px; }
.order-main span { color: var(--brand-muted); font-size: 12px; }
.order-amount { color: var(--brand-wood-deep); font-weight: 800; font-size: 13px; }

@media (max-width: 860px) {
  .home-head { flex-direction: column; align-items: flex-start; }
  .report-layout { grid-template-columns: 1fr; }
  .report-list { position: static; max-height: none; }
  .people-grid { grid-template-columns: 1fr; }
  .furniture-grid { grid-template-columns: 1fr; }
}
</style>
