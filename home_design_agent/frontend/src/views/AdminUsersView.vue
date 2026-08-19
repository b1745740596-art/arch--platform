<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api/client'

const { t } = useI18n()

const loading = ref(false)
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const saving = ref(false)
const formRef = ref()

const creditVisible = ref(false)
const creditUserId = ref(null)
const creditUsername = ref('')
const creditLoading = ref(false)
const creditSaving = ref(false)
const creditMode = ref('adjust')
const creditBalance = ref({ free_credits: 0, purchased_credits: 0, total_credits: 0 })
const creditForm = reactive({
  free_delta: 0,
  purchased_delta: 0,
  free_credits: 0,
  purchased_credits: 0,
  note: '',
})

function emptyCreditForm() {
  return { free_delta: 0, purchased_delta: 0, free_credits: 0, purchased_credits: 0, note: '' }
}

const roleOptions = computed(() => [
  { value: 'customer', label: t('adminUsers.roleOptions.customer') },
  { value: 'designer', label: t('adminUsers.roleOptions.designer') },
  { value: 'operations', label: t('adminUsers.roleOptions.operations') },
  { value: 'admin', label: t('adminUsers.roleOptions.admin') },
])

function emptyForm() {
  return {
    username: '',
    email: '',
    password: '',
    display_name: '',
    phone: '',
    roles: [],
    is_active: true,
    is_staff: false,
    is_superuser: false,
  }
}

const form = reactive(emptyForm())

const rules = computed(() => ({
  username: [{ required: true, message: t('auth.rules.username'), trigger: 'blur' }],
  email: [{ type: 'email', message: t('auth.rules.email'), trigger: 'blur' }],
  password: [
    {
      validator: (rule, value, callback) => {
        if (dialogMode.value === 'create' && !value) {
          return callback(new Error(t('auth.rules.passwordRequired')))
        }
        if (value && value.length < 8) {
          return callback(new Error(t('auth.rules.passwordMin')))
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}))

async function loadUsers() {
  loading.value = true
  try {
    const data = await api.listAdminUsers({ page: page.value })
    users.value = data.results
    total.value = data.count
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message
    ElMessage.error(t('common.loadFailed', { msg }))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    email: row.email || '',
    password: '',
    display_name: row.display_name || '',
    phone: row.phone || '',
    roles: [...(row.roles || [])],
    is_active: row.is_active,
    is_staff: row.is_staff,
    is_superuser: row.is_superuser,
  })
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  const payload = {
    username: form.username.trim(),
    email: form.email.trim() || '',
    display_name: form.display_name,
    phone: form.phone,
    roles: form.roles,
    is_active: form.is_active,
    is_staff: form.is_staff,
    is_superuser: form.is_superuser,
  }
  if (dialogMode.value === 'create' || form.password) {
    payload.password = form.password
  }

  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await api.createAdminUser(payload)
    } else {
      await api.updateAdminUser(editingId.value, payload)
    }
    ElMessage.success(t('adminUsers.saveSuccess'))
    dialogVisible.value = false
    await loadUsers()
  } catch (e) {
    const data = e?.response?.data
    const msg = data ? Object.values(data).flat().join('；') : e.message
    ElMessage.error(t('common.submitFailed', { msg }))
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  try {
    await api.updateAdminUser(row.id, { is_active: row.is_active })
    ElMessage.success(t('adminUsers.saveSuccess'))
  } catch (e) {
    row.is_active = !row.is_active
    const data = e?.response?.data
    const msg = data ? Object.values(data).flat().join('；') : e.message
    ElMessage.error(t('common.actionFailed', { msg }))
  }
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(t('adminUsers.deleteConfirm'), t('adminUsers.title'), {
      confirmButtonText: t('adminUsers.delete'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
  } catch {
    return
  }

  try {
    await api.deleteAdminUser(row.id)
    ElMessage.success(t('adminUsers.deleteSuccess'))
    await loadUsers()
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('common.actionFailed', { msg }))
  }
}

function roleLabel(role) {
  return t(`adminUsers.roleOptions.${role}`) || role
}

function formatDate(value) {
  if (!value) return t('common.none')
  return new Date(value).toLocaleString()
}

async function openCredit(row) {
  creditUserId.value = row.id
  creditUsername.value = row.username
  creditMode.value = 'adjust'
  Object.assign(creditForm, emptyCreditForm())
  creditVisible.value = true
  creditLoading.value = true
  try {
    creditBalance.value = await api.getAdminUserCredits(row.id)
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message
    ElMessage.error(t('adminUsers.credit.loadFailed', { msg }))
    creditBalance.value = { free_credits: 0, purchased_credits: 0, total_credits: 0 }
  } finally {
    creditLoading.value = false
  }
}

async function submitCredit() {
  if (!creditUserId.value) return
  creditSaving.value = true
  try {
    if (creditMode.value === 'adjust') {
      creditBalance.value = await api.adjustAdminUserCredits(creditUserId.value, {
        free_delta: Number(creditForm.free_delta) || 0,
        purchased_delta: Number(creditForm.purchased_delta) || 0,
        note: creditForm.note.trim(),
      })
    } else {
      creditBalance.value = await api.setAdminUserCredits(creditUserId.value, {
        free_credits: Number(creditForm.free_credits) || 0,
        purchased_credits: Number(creditForm.purchased_credits) || 0,
        note: creditForm.note.trim(),
      })
    }
    ElMessage.success(t('adminUsers.credit.adjustSuccess'))
    Object.assign(creditForm, emptyCreditForm())
  } catch (e) {
    const data = e?.response?.data
    const msg = data?.detail || (data ? Object.values(data).flat().join('；') : e.message)
    ElMessage.error(t('adminUsers.credit.submitFailed', { msg }))
  } finally {
    creditSaving.value = false
  }
}

onMounted(loadUsers)
</script>

<template>
  <div class="admin-users">
    <div class="page-head">
      <h2>{{ t('adminUsers.title') }}</h2>
      <el-button type="primary" @click="openCreate">{{ t('adminUsers.newUser') }}</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="users" stripe>
        <el-table-column prop="username" :label="t('auth.username')" min-width="130" />
        <el-table-column prop="email" :label="t('auth.email')" min-width="180">
          <template #default="{ row }">{{ row.email || t('common.none') }}</template>
        </el-table-column>
        <el-table-column prop="display_name" :label="t('account.displayName')" min-width="110" />
        <el-table-column prop="phone" :label="t('account.phone')" min-width="130">
          <template #default="{ row }">{{ row.phone || t('common.none') }}</template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.roleLabel')" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role" size="small" style="margin-right:4px">
              {{ roleLabel(role) }}
            </el-tag>
            <span v-if="!row.roles?.length">{{ t('common.none') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.active')" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggleActive(row)" />
          </template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.staff')" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_staff" type="success" size="small">{{ t('common.yes') }}</el-tag>
            <span v-else>{{ t('common.no') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.superuser')" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.is_superuser" type="danger" size="small">{{ t('common.yes') }}</el-tag>
            <span v-else>{{ t('common.no') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.lastLogin')" min-width="160">
          <template #default="{ row }">{{ formatDate(row.last_login) }}</template>
        </el-table-column>
        <el-table-column :label="t('adminUsers.actions')" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">{{ t('adminUsers.edit') }}</el-button>
            <el-button link type="warning" @click="openCredit(row)">{{ t('adminUsers.credit.action') }}</el-button>
            <el-button link type="danger" @click="deleteUser(row)">{{ t('adminUsers.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="(p) => { page = p; loadUsers() }"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? t('adminUsers.createTitle') : t('adminUsers.editTitle')"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item :label="t('auth.username')" prop="username">
          <el-input v-model="form.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item :label="t('auth.email')" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item :label="t('auth.password')" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="t('adminUsers.passwordHint')" />
        </el-form-item>
        <el-form-item :label="t('account.displayName')" prop="display_name">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item :label="t('account.phone')" prop="phone">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item :label="t('adminUsers.roleLabel')" prop="roles">
          <el-select v-model="form.roles" multiple style="width: 100%">
            <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('adminUsers.active')" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item :label="t('adminUsers.staff')" prop="is_staff">
          <el-switch v-model="form.is_staff" />
        </el-form-item>
        <el-form-item :label="t('adminUsers.superuser')" prop="is_superuser">
          <el-switch v-model="form.is_superuser" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="creditVisible" :title="t('adminUsers.credit.title')" width="520px">
      <div v-loading="creditLoading">
        <el-alert type="info" :closable="false" class="credit-summary">
          <template #title>
            <span>{{ creditUsername }} · {{ t('adminUsers.credit.current') }}</span>
          </template>
          <div class="credit-balance">
            <span>{{ t('adminUsers.credit.free') }}：<b>{{ creditBalance.free_credits }}</b></span>
            <span>{{ t('adminUsers.credit.purchased') }}：<b>{{ creditBalance.purchased_credits }}</b></span>
            <span>{{ t('adminUsers.credit.total') }}：<b>{{ creditBalance.total_credits }}</b></span>
          </div>
        </el-alert>

        <el-radio-group v-model="creditMode" class="credit-mode">
          <el-radio-button value="adjust">{{ t('adminUsers.credit.adjust') }}</el-radio-button>
          <el-radio-button value="set">{{ t('adminUsers.credit.set') }}</el-radio-button>
        </el-radio-group>

        <el-form label-width="150px" class="credit-form">
          <template v-if="creditMode === 'adjust'">
            <el-form-item :label="t('adminUsers.credit.freeDelta')">
              <el-input-number v-model="creditForm.free_delta" :min="-99999" :max="99999" :step="1" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item :label="t('adminUsers.credit.purchasedDelta')">
              <el-input-number v-model="creditForm.purchased_delta" :min="-99999" :max="99999" :step="1" controls-position="right" style="width: 100%" />
            </el-form-item>
            <div class="credit-hint">{{ t('adminUsers.credit.deltaHint') }}</div>
          </template>
          <template v-else>
            <el-form-item :label="t('adminUsers.credit.freeSet')">
              <el-input-number v-model="creditForm.free_credits" :min="0" :max="99999" :step="1" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item :label="t('adminUsers.credit.purchasedSet')">
              <el-input-number v-model="creditForm.purchased_credits" :min="0" :max="99999" :step="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </template>
          <el-form-item :label="t('adminUsers.credit.note')">
            <el-input v-model="creditForm.note" :placeholder="t('adminUsers.credit.noteHint')" maxlength="200" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="creditVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creditSaving" @click="submitCredit">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-users { max-width: 1180px; margin: 0 auto; }
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-head h2 { margin: 0; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.credit-summary { margin-bottom: 4px; }
.credit-balance { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 4px; font-size: 13px; color: var(--el-text-color-regular); }
.credit-balance b { color: var(--el-color-primary); font-size: 15px; }
.credit-mode { display: flex; margin: 16px 0 18px; }
.credit-form { padding-right: 4px; }
.credit-hint { margin: -6px 0 14px 150px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
