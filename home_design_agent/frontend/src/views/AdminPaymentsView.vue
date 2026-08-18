<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'

const { t } = useI18n()
const stats = ref(null)
const orders = ref([])
const diagnostics = ref(null)
const loading = ref(false)
const trendEl = ref()
const providerEl = ref()
const trendChart = ref(null)
const providerChart = ref(null)

const totalRevenue = computed(() => sumAmount(stats.value?.total_revenue))
const todayRevenue = computed(() => sumAmount(stats.value?.today_revenue))
const monthRevenue = computed(() => sumAmount(stats.value?.month_revenue))

function sumAmount(rows) {
  if (!rows?.length) return 0
  return rows.reduce((sum, row) => sum + Number(row.amount_cents || 0), 0) / 100
}

function formatMoney(value) {
  return `¥${Number(value || 0).toFixed(2)}`
}

function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

async function loadData() {
  loading.value = true
  try {
    const [statsData, orderData, diagnosticsData] = await Promise.all([
      api.getAdminPaymentStats(),
      api.listAdminPaymentOrders(),
      api.getAdminPaymentDiagnostics(),
    ])
    stats.value = statsData
    orders.value = orderData
    diagnostics.value = diagnosticsData
    await renderCharts()
  } catch (e) {
    ElMessage.error(t('adminPayments.loadFailed', { msg: extractError(e) }))
  } finally {
    loading.value = false
  }
}

async function renderCharts() {
  const echarts = await import('echarts')
  if (trendEl.value) {
    if (!trendChart.value) trendChart.value = echarts.init(trendEl.value)
    trendChart.value.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 18, top: 26, bottom: 30 },
      xAxis: {
        type: 'category',
        data: stats.value?.daily_revenue?.map((item) => item.date) || [],
        axisLine: { lineStyle: { color: 'rgba(47,107,79,0.25)' } },
        axisLabel: { color: '#68766e' },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(47,107,79,0.08)' } },
        axisLabel: { color: '#68766e', formatter: '¥{value}' },
      },
      series: [{
        name: t('adminPayments.revenue'),
        type: 'bar',
        barWidth: '52%',
        data: stats.value?.daily_revenue?.map((item) => Number((item.amount_cents || 0) / 100)) || [],
        itemStyle: { color: '#2f6b4f', borderRadius: [6, 6, 0, 0] },
      }],
    })
  }

  if (providerEl.value) {
    if (!providerChart.value) providerChart.value = echarts.init(providerEl.value)
    const providerData = (stats.value?.by_provider || []).map((item) => ({
      name: item.provider_display,
      value: Number((item.amount_cents || 0) / 100),
    }))
    providerChart.value.setOption({
      tooltip: { trigger: 'item', formatter: '{b}：¥{c}（{d}%）' },
      legend: { bottom: 0, textStyle: { color: '#68766e' } },
      color: ['#2f6b4f', '#7fae96', '#c89662'],
      series: [{
        name: t('adminPayments.provider'),
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { color: '#3b4b41', formatter: '{b}\n¥{c}' },
        data: providerData,
      }],
    })
  }
}

async function markPaid(row) {
  try {
    const updated = await api.adminMarkPaid(row.id, { reference: 'manual' })
    ElMessage.success(t('adminPayments.markPaidSuccess'))
    const index = orders.value.findIndex((item) => item.id === row.id)
    if (index >= 0) orders.value.splice(index, 1, updated)
    await loadData()
  } catch (e) {
    ElMessage.error(t('common.actionFailed', { msg: extractError(e) }))
  }
}

function extractError(e) {
  const data = e?.response?.data
  if (!data) return e?.message || String(e)
  if (typeof data === 'string') return data
  return data?.detail || Object.values(data).flat().join('；')
}

const statusType = (status) => ({ paid: 'success', pending: 'warning', failed: 'danger', cancelled: 'info', refunded: 'info' }[status] || 'info')

function resizeCharts() {
  trendChart.value?.resize()
  providerChart.value?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart.value?.dispose()
  providerChart.value?.dispose()
})
</script>

<template>
  <div class="admin-payments">
    <div class="page-head">
      <div>
        <h1>{{ t('adminPayments.title') }}</h1>
        <p>{{ t('adminPayments.subtitle') }}</p>
      </div>
      <el-button :loading="loading" @click="loadData">{{ t('adminPayments.refresh') }}</el-button>
    </div>

    <div class="summary-grid">
      <div class="summary-card primary">
        <span>{{ t('adminPayments.totalRevenue') }}</span>
        <b>{{ formatMoney(totalRevenue) }}</b>
      </div>
      <div class="summary-card">
        <span>{{ t('adminPayments.todayRevenue') }}</span>
        <b>{{ formatMoney(todayRevenue) }}</b>
      </div>
      <div class="summary-card">
        <span>{{ t('adminPayments.monthRevenue') }}</span>
        <b>{{ formatMoney(monthRevenue) }}</b>
      </div>
      <div class="summary-card">
        <span>{{ t('adminPayments.paidOrders') }}</span>
        <b>{{ stats?.paid_orders || 0 }}</b>
      </div>
      <div class="summary-card">
        <span>{{ t('adminPayments.pendingOrders') }}</span>
        <b>{{ stats?.pending_orders || 0 }}</b>
      </div>
    </div>

    <el-card v-if="diagnostics" shadow="never" class="diag-card">
      <template #header><b>{{ t('adminPayments.diagnosticsTitle') }}</b></template>
      <div class="diag-head">
        <el-tag :type="diagnostics.payment_mode === 'live' ? 'success' : 'warning'" effect="light">
          {{ t('adminPayments.modeLabel') }}：{{ diagnostics.payment_mode }}
        </el-tag>
        <span>{{ t('adminPayments.plansCount', { n: diagnostics.plans_count }) }}</span>
      </div>
      <div class="diag-providers">
        <div v-for="(info, name) in diagnostics.providers" :key="name" class="diag-provider">
          <b>{{ name }}</b>
          <el-tag :type="info.configured ? 'success' : 'danger'" size="small">
            {{ info.configured ? t('adminPayments.configured') : t('adminPayments.notConfigured') }}
          </el-tag>
          <el-tag :type="info.package_installed ? 'success' : 'warning'" size="small">
            {{ info.package_installed ? t('adminPayments.packageInstalled') : t('adminPayments.packageMissing') }}
          </el-tag>
        </div>
      </div>
      <div class="diag-webhooks">
        <p>{{ t('adminPayments.webhookUrls') }}</p>
        <div v-for="(url, name) in diagnostics.webhook_urls" :key="name">
          <span class="diag-webhook-name">{{ name }}</span>
          <code>{{ url }}</code>
        </div>
      </div>
    </el-card>

    <div class="chart-grid">
      <el-card shadow="never" class="chart-card">
        <template #header><b>{{ t('adminPayments.trendTitle') }}</b></template>
        <div ref="trendEl" class="chart trend-chart"></div>
      </el-card>
      <el-card shadow="never" class="chart-card">
        <template #header><b>{{ t('adminPayments.providerTitle') }}</b></template>
        <div ref="providerEl" class="chart provider-chart"></div>
      </el-card>
    </div>

    <el-card shadow="never" class="orders-card">
      <template #header><b>{{ t('adminPayments.ordersTitle') }}</b></template>
      <el-table :data="orders" v-loading="loading" empty-text="—">
        <el-table-column prop="username" :label="t('adminPayments.user')" min-width="120" />
        <el-table-column prop="order_no" :label="t('adminPayments.orderNo')" min-width="190" />
        <el-table-column :label="t('adminPayments.package')" min-width="120">
          <template #default="{ row }">{{ row.plan?.name || row.credits + ' ' + t('adminPayments.credits') }}</template>
        </el-table-column>
        <el-table-column prop="provider_display" :label="t('adminPayments.provider')" width="110" />
        <el-table-column :label="t('adminPayments.amount')" width="110">
          <template #default="{ row }">¥{{ Number(row.amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column :label="t('adminPayments.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('adminPayments.paidAt')" min-width="150">
          <template #default="{ row }">{{ formatDate(row.paid_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('adminPayments.actions')" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="primary"
              plain
              @click="markPaid(row)"
            >
              {{ t('adminPayments.markPaid') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.admin-payments { max-width: 1100px; margin: 0 auto; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-head h1 { margin: 0; font-size: 24px; }
.page-head p { margin: 6px 0 0; color: var(--brand-muted); font-size: 13px; }
.summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin: 22px 0; }
.summary-card {
  padding: 18px 16px; border: 1px solid var(--app-border); border-radius: 16px;
  background: var(--app-surface); box-shadow: var(--app-shadow-soft);
}
.summary-card span { display: block; color: var(--brand-muted); font-size: 12px; margin-bottom: 8px; }
.summary-card b { font-size: 22px; color: var(--brand-green-deep); }
.summary-card.primary { background: linear-gradient(135deg, #2f6b4f 0%, #204b37 100%); border: 0; }
.summary-card.primary span { color: rgba(255,255,255,0.72); }
.summary-card.primary b { color: #fff; }
.diag-card { margin: 16px 0; }
.diag-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; color: var(--brand-muted); font-size: 13px; }
.diag-providers { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.diag-provider { display: flex; align-items: center; gap: 8px; }
.diag-provider b { text-transform: uppercase; letter-spacing: 0.4px; }
.diag-webhooks p { margin: 0 0 8px; color: var(--brand-muted); font-size: 13px; }
.diag-webhooks div { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 12px; }
.diag-webhook-name { width: 60px; color: var(--brand-muted); }
.diag-webhooks code { color: var(--brand-green-deep); word-break: break-all; }
.chart-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; margin-bottom: 16px; }
.chart-card { min-width: 0; }
.chart { width: 100%; }
.trend-chart { height: 320px; }
.provider-chart { height: 320px; }
.orders-card { margin-top: 16px; }
@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-grid { grid-template-columns: 1fr; }
}
</style>
