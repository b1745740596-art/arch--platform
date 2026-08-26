<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { api } from '@/api/client'

const props = defineProps({
  draft: { type: Object, required: true },
  hasImages: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['apply-patch'])
const { t, locale } = useI18n()

const stage = ref('')
const completedStages = ref([])
const currentMessage = ref('')
const quickReplies = ref([])
const input = ref('')
const loading = ref(false)
const ready = ref(false)
const progress = ref(0)
const historyVisible = ref(false)
const history = ref([])
const initialized = ref(false)

const canSend = computed(
  () => Boolean(input.value.trim()) && !loading.value && !props.disabled,
)

function draftPayload() {
  return {
    has_images: props.hasImages,
    plan_name: props.draft.plan_name || '',
    room_type: props.draft.room_type || '',
    style: props.draft.style || '',
    budget_tier: props.draft.budget_tier || '',
    requirement: props.draft.requirement || '',
    module_codes: Array.isArray(props.draft.moduleCodes) ? [...props.draft.moduleCodes] : [],
    workflow_id: props.draft.workflowId ?? null,
  }
}

function addHistory(role, content) {
  const value = String(content || '').trim()
  if (!value) return
  history.value.push({ role, content: value, at: Date.now() })
  if (history.value.length > 30) history.value.splice(0, history.value.length - 30)
}

async function advance(message = '', showUser = true) {
  if (loading.value || props.disabled) return
  const value = String(message || '').trim()
  if (showUser && value) addHistory('user', value)
  loading.value = true
  try {
    const response = await api.promptCoachTurn({
      message: value,
      stage: stage.value,
      completed_stages: completedStages.value,
      history: history.value.slice(-10).map(({ role, content }) => ({ role, content })),
      draft: draftPayload(),
      locale: locale.value,
    })
    if (response?.form_patch && Object.keys(response.form_patch).length) {
      emit('apply-patch', response.form_patch)
    }
    stage.value = response?.stage || stage.value
    completedStages.value = Array.isArray(response?.completed_stages)
      ? response.completed_stages
      : completedStages.value
    quickReplies.value = Array.isArray(response?.quick_replies) ? response.quick_replies : []
    ready.value = Boolean(response?.ready_to_generate)
    progress.value = Number(response?.progress || 0)
    currentMessage.value = response?.message || t('designer.fallback')
    addHistory('assistant', currentMessage.value)
  } catch (error) {
    const msg = error?.response?.data?.detail || error?.message || t('common.unknownError')
    currentMessage.value = t('designer.unavailable')
    addHistory('assistant', currentMessage.value)
    ElMessage.error(t('designer.failed', { msg }))
  } finally {
    loading.value = false
    initialized.value = true
  }
}

function send() {
  if (!canSend.value) return
  const value = input.value.trim()
  input.value = ''
  void advance(value)
}

function useReply(reply) {
  if (loading.value || props.disabled) return
  void advance(reply)
}

onMounted(() => {
  void advance('', false)
})

watch(
  () => [props.hasImages, props.draft.room_type, props.draft.style, props.draft.budget_tier],
  () => {
    if (!initialized.value || loading.value) return
    const fieldReady = {
      upload: props.hasImages,
      room: Boolean(props.draft.room_type),
      style: Boolean(props.draft.style),
      budget: Boolean(props.draft.budget_tier),
    }[stage.value]
    if (fieldReady) void advance('', false)
  },
)
</script>

<template>
  <section class="designer-card" aria-live="polite">
    <button type="button" class="designer-head" @click="historyVisible = true">
      <span class="designer-avatar">设</span>
      <span class="designer-title">
        <b>{{ t('designer.title') }}</b>
        <small>{{ ready ? t('designer.ready') : t('designer.guiding') }}</small>
      </span>
      <span class="designer-progress">{{ progress }}%</span>
      <el-icon><Clock /></el-icon>
    </button>

    <div class="designer-message" :class="{ loading }">
      <span v-if="loading">{{ t('designer.thinking') }}</span>
      <span v-else>{{ currentMessage || t('designer.welcome') }}</span>
    </div>

    <div v-if="quickReplies.length" class="designer-replies">
      <button
        v-for="reply in quickReplies"
        :key="reply"
        type="button"
        :disabled="loading || disabled"
        @click="useReply(reply)"
      >
        {{ reply }}
      </button>
    </div>

    <div class="designer-input">
      <el-input
        v-model="input"
        :disabled="loading || disabled"
        :placeholder="t('designer.placeholder')"
        maxlength="500"
        @keyup.enter="send"
      />
      <el-button type="primary" circle :disabled="!canSend" :aria-label="t('designer.send')" @click="send">
        <el-icon><Promotion /></el-icon>
      </el-button>
    </div>

    <el-drawer
      v-model="historyVisible"
      direction="btt"
      size="68%"
      :title="t('designer.history')"
      append-to-body
    >
      <div class="designer-history">
        <div
          v-for="(item, index) in history"
          :key="`${item.at}-${index}`"
          class="history-bubble"
          :class="item.role"
        >
          <small>{{ item.role === 'assistant' ? t('designer.title') : t('designer.you') }}</small>
          <p>{{ item.content }}</p>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.designer-card {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid rgba(35, 169, 124, 0.22);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(240, 252, 247, 0.98), rgba(255, 255, 255, 0.98));
  box-shadow: 0 10px 24px rgba(35, 169, 124, 0.08);
}

.designer-head {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 9px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--brand-ink);
  font: inherit;
  text-align: left;
}

.designer-avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(135deg, #35bd8d, #16865f);
  font-size: 13px;
  font-weight: 750;
}

.designer-title { display: flex; flex: 1; min-width: 0; flex-direction: column; }
.designer-title b { font-size: 14px; }
.designer-title small { color: var(--brand-muted); font-size: 10px; }
.designer-progress { color: #17865f; font-size: 11px; font-weight: 700; }
.designer-head .el-icon { color: var(--brand-muted); }

.designer-message {
  display: -webkit-box;
  height: 44px;
  margin: 9px 0 8px;
  overflow: hidden;
  color: var(--brand-ink);
  font-size: 13px;
  line-height: 22px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.designer-message.loading { color: var(--brand-muted); }

.designer-replies {
  display: flex;
  gap: 7px;
  margin-bottom: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}
.designer-replies::-webkit-scrollbar { display: none; }
.designer-replies button {
  flex: 0 0 auto;
  padding: 6px 10px;
  border: 1px solid rgba(35, 169, 124, 0.22);
  border-radius: 999px;
  background: #fff;
  color: #176b4f;
  font: inherit;
  font-size: 11px;
}
.designer-replies button:disabled { opacity: 0.55; }

.designer-input { display: flex; align-items: center; gap: 8px; }
.designer-input .el-button { flex: 0 0 auto; color: #fff; }

.designer-history { display: flex; flex-direction: column; gap: 10px; padding-bottom: 24px; }
.history-bubble { max-width: 86%; }
.history-bubble.user { align-self: flex-end; text-align: right; }
.history-bubble small { color: var(--brand-muted); font-size: 10px; }
.history-bubble p {
  margin: 3px 0 0;
  padding: 9px 11px;
  border-radius: 13px;
  background: #f1f5f3;
  color: var(--brand-ink);
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
}
.history-bubble.user p { background: #dff5ec; }
</style>
