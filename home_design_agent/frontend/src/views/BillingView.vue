<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import { useBillingStore } from '@/stores/billing'
import { useAuthStore } from '@/stores/auth'
import wechatQr from '@/assets/pay_qr_wechat.webp'
import alipayQr from '@/assets/pay_qr_alipay.webp'

const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const billing = useBillingStore()

const providers = [
  { value: 'wechat', label: '微信支付', class: 'wechat' },
  { value: 'alipay', label: '支付宝', class: 'alipay' },
  { value: 'stripe', label: 'Stripe', class: 'stripe' },
]

const dialogVisible = ref(false)
const selectedPlan = ref(null)
const selectedProvider = ref('wechat')
const paying = ref(false)
const currentOrder = ref(null)
const currentPayment = ref(null)
const qrDataUrl = ref('')
const proofNote = ref('')
const submittingProof = ref(false)

const isMockMode = computed(() => billing.balance?.payment_mode !== 'live')
const qrMode = computed(() => billing.balance?.payment_qr_mode === true)
const visibleProviders = computed(() => (qrMode.value ? providers.filter((p) => p.value !== 'stripe') : providers))
const proofDone = computed(() => !!currentOrder.value?.payment_note)
const totalCredits = computed(() => billing.balance?.total_credits ?? 0)
const freeCredits = computed(() => billing.balance?.free_credits ?? 0)
const purchasedCredits = computed(() => billing.balance?.purchased_credits ?? 0)

const staticQrImage = (provider) => (provider === 'alipay' ? alipayQr : wechatQr)

const currencySymbol = (currency) => (currency === 'USD' ? '$' : '¥')
const formatAmount = (order) => `${currencySymbol(order?.currency)}${(order?.amount ?? 0).toFixed(2)}`

onMounted(async () => {
  await auth.fetchMe()
  await billing.refreshAll()
  if (route.query.paid === 'success') {
    ElMessage.success(t('billing.paidSuccess'))
  } else if (route.query.paid === 'cancel') {
    ElMessage.info(t('billing.payCancelled'))
  }
})

function openPay(plan) {
  selectedPlan.value = plan
  selectedProvider.value = 'wechat'
  currentOrder.value = null
  currentPayment.value = null
  qrDataUrl.value = ''
  proofNote.value = ''
  dialogVisible.value = true
}

async function submitOrder() {
  if (!selectedPlan.value) return
  paying.value = true
  try {
    const result = await billing.createOrder({
      plan: selectedPlan.value.id,
      provider: selectedProvider.value,
    })
    currentOrder.value = result.order
    currentPayment.value = result.payment
    if (result.payment?.checkout_url) {
      window.location.href = result.payment.checkout_url
      return
    }
    if (result.payment?.qr_code) {
      qrDataUrl.value = await QRCode.toDataURL(result.payment.qr_code, { width: 224, margin: 1 })
    }
  } catch (e) {
    ElMessage.error(t('common.submitFailed', { msg: extractError(e) }))
  } finally {
    paying.value = false
  }
}

async function mockPay() {
  if (!currentOrder.value) return
  try {
    const result = await billing.mockPay(currentOrder.value.id)
    currentOrder.value = result.order
    ElMessage.success(t('billing.mockPaid'))
    dialogVisible.value = false
  } catch (e) {
    ElMessage.error(t('common.actionFailed', { msg: extractError(e) }))
  }
}

async function submitProof() {
  if (!currentOrder.value || !proofNote.value.trim()) return
  submittingProof.value = true
  try {
    const result = await billing.submitProof(currentOrder.value.id, { payment_note: proofNote.value.trim() })
    currentOrder.value = result
    ElMessage.success(t('billing.proofSubmitted'))
  } catch (e) {
    ElMessage.error(t('common.actionFailed', { msg: extractError(e) }))
  } finally {
    submittingProof.value = false
  }
}

function extractError(e) {
  const data = e?.response?.data
  if (!data) return e?.message || String(e)
  if (typeof data === 'string') return data
  return data?.detail || Object.values(data).flat().join('；')
}

const statusType = (status) => ({ paid: 'success', pending: 'warning', failed: 'danger', cancelled: 'info', refunded: 'info' }[status] || 'info')
</script>

<template>
  <div class="billing-page">
    <section class="balance-card">
      <div>
        <p class="eyebrow">{{ t('billing.balanceEyebrow') }}</p>
        <div class="balance-main">
          <strong>{{ totalCredits }}</strong>
          <span>{{ t('billing.creditsUnit') }}</span>
        </div>
        <p class="balance-sub">
          {{ t('billing.balanceHint', { free: freeCredits, purchased: purchasedCredits }) }}
        </p>
      </div>
      <div class="balance-meta">
        <div><span>{{ t('billing.freeCredits') }}</span><b>{{ freeCredits }}</b></div>
        <div><span>{{ t('billing.purchasedCredits') }}</span><b>{{ purchasedCredits }}</b></div>
      </div>
    </section>

    <section class="plans-section">
      <h2>{{ t('billing.plansTitle') }}</h2>
      <p class="subtitle">{{ t('billing.plansSubtitle') }}</p>
      <div class="plans-grid">
        <div
          v-for="plan in billing.plans"
          :key="plan.id"
          class="plan-card"
          :class="{ featured: plan.slug === 'popular' }"
        >
          <span v-if="plan.slug === 'popular'" class="badge">{{ t('billing.popular') }}</span>
          <h3>{{ plan.name }}</h3>
          <p class="plan-desc">{{ plan.description }}</p>
          <div class="plan-price">
            <b>{{ currencySymbol(plan.currency) }}{{ plan.price.toFixed(2) }}</b>
            <span> / {{ plan.credits }} {{ t('billing.creditsUnit') }}</span>
          </div>
          <el-button type="primary" plain @click="openPay(plan)">{{ t('billing.rechargeNow') }}</el-button>
        </div>
      </div>
    </section>

    <section class="orders-section">
      <h2>{{ t('billing.ordersTitle') }}</h2>
      <el-table :data="billing.orders" v-loading="billing.loading" empty-text="—">
        <el-table-column prop="order_no" :label="t('billing.orderNo')" min-width="180" />
        <el-table-column :label="t('billing.package')" min-width="120">
          <template #default="{ row }">{{ row.plan?.name || row.credits + ' ' + t('billing.creditsUnit') }}</template>
        </el-table-column>
        <el-table-column prop="provider_display" :label="t('billing.provider')" width="110" />
        <el-table-column :label="t('billing.amount')" width="110">
          <template #default="{ row }">{{ formatAmount(row) }}</template>
        </el-table-column>
        <el-table-column :label="t('billing.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('billing.createdAt')" min-width="150">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" :title="t('billing.payTitle')" width="420px" align-center>
      <div class="pay-body">
        <div class="pay-plan">
          <b>{{ selectedPlan?.name }}</b>
          <span>{{ selectedPlan?.credits }} {{ t('billing.creditsUnit') }} · {{ selectedPlan ? currencySymbol(selectedPlan.currency) + selectedPlan.price.toFixed(2) : '' }}</span>
        </div>

        <template v-if="!currentOrder">
          <p class="pay-label">{{ t('billing.chooseProvider') }}</p>
          <div class="provider-list">
            <button
              v-for="p in visibleProviders"
              :key="p.value"
              type="button"
              class="provider-btn"
              :class="[p.class, { active: selectedProvider === p.value }]"
              @click="selectedProvider = p.value"
            >
              {{ p.label }}
            </button>
          </div>
          <el-button type="primary" class="pay-submit" :loading="paying" @click="submitOrder">
            {{ t('billing.confirmPay') }}
          </el-button>
        </template>

        <template v-else>
          <div class="order-line">{{ t('billing.orderNo') }}：{{ currentOrder.order_no }}</div>
          <template v-if="currentPayment?.static_qr">
            <p class="pay-label">{{ t('billing.staticQrHint') }}</p>
            <img :src="staticQrImage(currentOrder.provider)" class="static-qr" alt="payment QR" />
            <div class="pay-amount">{{ formatAmount(currentOrder) }}</div>
            <template v-if="!proofDone">
              <el-input
                v-model="proofNote"
                type="textarea"
                :rows="2"
                maxlength="200"
                show-word-limit
                :placeholder="t('billing.proofPlaceholder')"
              />
              <el-button
                type="success"
                class="pay-submit"
                :loading="submittingProof"
                :disabled="!proofNote.trim()"
                @click="submitProof"
              >
                {{ t('billing.submitProof') }}
              </el-button>
              <p class="pay-note-tip">{{ t('billing.proofTip') }}</p>
            </template>
            <el-alert
              v-else
              type="success"
              :title="t('billing.proofSubmitted')"
              :description="t('billing.proofWaiting')"
              show-icon
            />
          </template>
          <template v-else-if="qrDataUrl">
            <p class="pay-label">{{ t('billing.scanToPay', { provider: providers.find((p) => p.value === currentOrder.provider)?.label }) }}</p>
            <img :src="qrDataUrl" class="qr" alt="QR code" />
          </template>
          <template v-else-if="currentPayment?.checkout_url || isMockMode">
            <p class="pay-label">{{ isMockMode ? t('billing.mockHint') : t('billing.redirecting') }}</p>
            <el-button v-if="isMockMode" type="success" :loading="paying" class="pay-submit" @click="mockPay">
              {{ t('billing.mockPay') }}
            </el-button>
          </template>
          <template v-else>
            <p class="pay-label">{{ t('billing.pendingHint') }}</p>
          </template>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.billing-page { max-width: 880px; margin: 0 auto; }
.balance-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 28px;
  border: 1px solid var(--app-border);
  border-radius: 20px;
  background: linear-gradient(135deg, #2f6b4f 0%, #204b37 100%);
  color: #fff;
  box-shadow: var(--app-shadow);
}
.eyebrow { margin: 0 0 6px; font-size: 12px; letter-spacing: 2px; opacity: 0.72; }
.balance-main { display: flex; align-items: baseline; gap: 8px; }
.balance-main strong { font-size: 46px; line-height: 1; font-weight: 800; }
.balance-main span { font-size: 14px; opacity: 0.82; }
.balance-sub { margin: 12px 0 0; font-size: 13px; opacity: 0.8; }
.balance-meta { display: flex; gap: 30px; }
.balance-meta div { text-align: right; }
.balance-meta span { display: block; font-size: 12px; opacity: 0.72; }
.balance-meta b { font-size: 22px; }
.plans-section, .orders-section { margin-top: 30px; }
h2 { margin: 0; font-size: 20px; }
.subtitle { margin: 6px 0 16px; color: var(--brand-muted); font-size: 13px; }
.plans-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.plan-card {
  position: relative;
  padding: 22px;
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: var(--app-surface);
}
.plan-card.featured { border-color: rgba(47, 107, 79, 0.4); box-shadow: var(--app-shadow-soft); }
.badge {
  position: absolute; top: 16px; right: 16px;
  padding: 3px 8px; border-radius: 999px; background: #c89662; color: #fff; font-size: 11px;
}
.plan-card h3 { margin: 0 0 6px; }
.plan-desc { min-height: 38px; margin: 0 0 16px; color: var(--brand-muted); font-size: 13px; }
.plan-price { margin-bottom: 18px; }
.plan-price b { font-size: 26px; }
.plan-price span { color: var(--brand-muted); font-size: 12px; }
.pay-body { padding: 4px 2px; }
.pay-plan { display: flex; justify-content: space-between; padding-bottom: 14px; border-bottom: 1px solid var(--app-border); }
.pay-plan span { color: var(--brand-muted); font-size: 13px; }
.pay-label { margin: 16px 0 8px; font-size: 13px; color: var(--brand-muted); }
.provider-list { display: flex; gap: 10px; }
.provider-btn {
  flex: 1; padding: 11px 0; border-radius: 12px; border: 1px solid var(--app-border);
  background: #fff; color: var(--brand-ink); font-weight: 650; cursor: pointer;
}
.provider-btn.active { border-color: var(--el-color-primary); color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.pay-submit { width: 100%; margin-top: 18px; }
.order-line { padding: 12px 0 4px; font-size: 13px; color: var(--brand-muted); }
.qr { display: block; margin: 6px auto 0; width: 224px; height: 224px; border-radius: 8px; }
.static-qr { display: block; margin: 6px auto 0; width: 100%; max-width: 280px; height: auto; max-height: 320px; object-fit: contain; border-radius: 8px; }
.pay-amount { margin: 12px 0 4px; text-align: center; font-size: 20px; font-weight: 800; color: var(--brand-green-deep); }
.pay-note-tip { margin: 8px 0 0; font-size: 12px; color: var(--brand-muted); }
@media (max-width: 720px) {
  .balance-card { flex-direction: column; align-items: flex-start; gap: 18px; }
  .balance-meta { width: 100%; justify-content: flex-start; }
  .plans-grid { grid-template-columns: 1fr; }
}
</style>
