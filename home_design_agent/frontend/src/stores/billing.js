import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api/client'

export const useBillingStore = defineStore('billing', () => {
  const balance = ref(undefined)
  const plans = ref([])
  const orders = ref([])
  const transactions = ref([])
  const loading = ref(false)

  async function fetchBalance(force = false) {
    if (balance.value !== undefined && !force) return balance.value
    balance.value = await api.getBalance()
    return balance.value
  }

  async function fetchPlans() {
    plans.value = await api.listPlans()
    return plans.value
  }

  async function fetchOrders() {
    orders.value = await api.listPaymentOrders()
    return orders.value
  }

  async function fetchTransactions() {
    transactions.value = await api.listTransactions()
    return transactions.value
  }

  async function createOrder(data) {
    loading.value = true
    try {
      const result = await api.createPaymentOrder(data)
      balance.value = result.balance
      await fetchOrders()
      return result
    } finally {
      loading.value = false
    }
  }

  async function mockPay(id) {
    const result = await api.mockPayOrder(id)
    balance.value = result.balance
    await fetchOrders()
    return result
  }

  async function submitProof(id, data) {
    const result = await api.submitPaymentProof(id, data)
    await fetchOrders()
    return result
  }

  async function refreshAll() {
    await Promise.all([fetchBalance(true), fetchPlans(), fetchOrders(), fetchTransactions()])
  }

  return {
    balance,
    plans,
    orders,
    transactions,
    loading,
    fetchBalance,
    fetchPlans,
    fetchOrders,
    fetchTransactions,
    createOrder,
    mockPay,
    submitProof,
    refreshAll,
  }
})
