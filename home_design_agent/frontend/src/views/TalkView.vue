<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api/client'
import { useTerm } from '@/i18n'
import { resolveMediaUrl } from '@/utils/media'

const { t, tm, rt, locale } = useI18n()
const term = useTerm()
const router = useRouter()

const sessions = ref([])
const active = ref(null)
const messages = ref([])
const profile = ref(null)
const input = ref('')
const loading = ref(true)
const sending = ref(false)
const creating = ref(false)
const converting = ref(false)
const historyVisible = ref(false)
const messagePane = ref(null)
let sessionRequestId = 0
let disposed = false

const isActive = computed(() => active.value?.status === 'active')
const conversionReady = computed(() => Boolean(profile.value?.conversion_ready && isActive.value))
const completion = computed(() => Number(profile.value?.completion || 0))
const interactionLocked = computed(
  () => loading.value || sending.value || creating.value || converting.value,
)
const lastQuestion = computed(() => {
  const last = [...messages.value].reverse().find((item) => item.role === 'assistant')
  return last?.question_asked || ''
})
const latestHasOrderAction = computed(() => {
  const last = [...messages.value].reverse().find((item) => item.role === 'assistant')
  return toolResults(last).some((item) => item.kind === 'order_action')
})

const QUICK_REPLY_VALUES = {
  city: ['上海', '北京', '杭州', '深圳'],
  area: ['89平', '110平', '140平'],
  household: ['两人居住', '一家三口，有孩子', '和父母一起住'],
  style: ['现代简约', '原木风', '奶油风', '新中式'],
  budget_max: ['预算15到20万', '预算20到30万', '预算30到50万'],
  desired_timeline: ['三个月后入住', '年底前装好', '时间比较灵活'],
  pain_points: ['最担心增项', '在意环保健康', '担心工期拖延', '怕效果不落地'],
}

const quickReplies = computed(() => {
  const key = lastQuestion.value
  const values = QUICK_REPLY_VALUES[key] || []
  if (!values.length) return []
  const translated = tm(`talk.quickReplies.${key}`)
  const labels = Array.isArray(translated) ? translated.map((item) => rt(item)) : []
  return values.map((value, index) => ({ value, label: labels[index] || value }))
})

const STAGE_KEYS = {
  icebreak: 'icebreak',
  discovery: 'discovery',
  matching: 'matching',
  objection: 'objection',
  closing: 'closing',
  ordered: 'ordered',
  follow_up: 'followUp',
}

function unpackList(data) {
  return Array.isArray(data) ? data : data?.results || []
}

function extractError(error) {
  const data = error?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return Array.isArray(data.detail) ? data.detail.join('；') : String(data.detail)
  const first = data && Object.values(data)[0]
  if (first) return Array.isArray(first) ? first.join('；') : String(first)
  return error?.message || t('common.unknownError')
}

function stageLabel(conversation) {
  const key = STAGE_KEYS[conversation?.stage]
  return key ? t(`talk.stages.${key}`) : conversation?.stage_display || t('talk.preparing')
}

function displayMessage(message) {
  return message?.metadata?.is_welcome ? t('talk.welcome') : message?.content || ''
}

function toolResults(message) {
  const results = message?.metadata?.tool_results
  return Array.isArray(results) ? results : []
}

function money(value) {
  return value == null ? '' : `¥${Number(value).toLocaleString()}`
}

function toolPrice(item) {
  if (item?.price != null) return money(item.price)
  if (item?.price_min != null && item?.price_max != null) {
    return `${money(item.price_min)}–${money(item.price_max)}`
  }
  return item?.price_text || ''
}

function toolActionLabel(action) {
  return action?.type === 'convert' ? t('talk.tools.confirmOrder') : t('talk.tools.open')
}

function openToolPath(path) {
  if (path) router.push(path)
}

async function runToolAction(action) {
  if (!action || interactionLocked.value) return
  if (action.type === 'convert') {
    await convertToOrder()
    return
  }
  if (action.type === 'navigate') openToolPath(action.path)
}

function formatTime(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat(locale.value, { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function createClientMessageId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes)
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256)
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0'))
  return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10).join('')}`
}

function messageClientId(message) {
  return message?.client_message_id || message?.client_id || message?.metadata?.client_message_id || ''
}

function wait(milliseconds) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds))
}

function mergeSessionSummary(id, patch = {}, moveToFront = false) {
  const index = sessions.value.findIndex((item) => item.id === id)
  const current = index >= 0 ? sessions.value[index] : { id }
  const { messages: _messages, ...summary } = patch || {}
  const next = { ...current, ...summary, id }
  if (index >= 0) sessions.value.splice(index, 1)
  if (moveToFront || index < 0) sessions.value.unshift(next)
  else sessions.value.splice(index, 0, next)
}

function applyConversation(data, { closeHistory = false, moveToFront = false } = {}) {
  if (!data) return
  active.value = data
  profile.value = data.profile || null
  messages.value = data.messages || []
  mergeSessionSummary(data.id, data, moveToFront)
  if (closeHistory) historyVisible.value = false
}

async function scrollBottom() {
  await nextTick()
  if (messagePane.value) messagePane.value.scrollTop = messagePane.value.scrollHeight
}

async function openSession(sessionOrId, { force = false } = {}) {
  const id = typeof sessionOrId === 'object' ? sessionOrId.id : sessionOrId
  if (!id || (!force && interactionLocked.value)) return
  const requestId = ++sessionRequestId
  loading.value = true
  try {
    const data = await api.getTalkSession(id)
    if (disposed || requestId !== sessionRequestId) return
    applyConversation(data, { closeHistory: true })
    await scrollBottom()
  } catch (error) {
    if (!disposed && requestId === sessionRequestId) {
      ElMessage.error(t('talk.loadFailed', { msg: extractError(error) }))
    }
  } finally {
    if (!disposed && requestId === sessionRequestId) loading.value = false
  }
}

async function startNew({ force = false } = {}) {
  if (creating.value || sending.value || converting.value || (loading.value && !force)) return
  const requestId = ++sessionRequestId
  creating.value = true
  loading.value = true
  try {
    const data = await api.createTalkSession()
    if (disposed || requestId !== sessionRequestId) return
    applyConversation(data, { closeHistory: true, moveToFront: true })
    input.value = ''
    await scrollBottom()
  } catch (error) {
    if (!disposed && requestId === sessionRequestId) {
      ElMessage.error(t('talk.createFailed', { msg: extractError(error) }))
    }
  } finally {
    creating.value = false
    if (!disposed && requestId === sessionRequestId) loading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    sessions.value = unpackList(await api.listTalkSessions())
    const candidate = sessions.value.find((item) => item.status === 'active') || sessions.value[0]
    if (candidate) {
      await openSession(candidate.id, { force: true })
    } else {
      await startNew({ force: true })
    }
  } catch (error) {
    if (!disposed) {
      ElMessage.error(t('talk.loadFailed', { msg: extractError(error) }))
      loading.value = false
    }
  }
}

async function reconcileFailedSend(sessionId, clientMessageId) {
  try {
    const data = await api.getTalkSession(sessionId)
    const canonicalMessages = data.messages || []
    const acceptedIndex = canonicalMessages.findIndex(
      (message) => message.role === 'user' && messageClientId(message) === clientMessageId,
    )
    if (acceptedIndex < 0) return { accepted: false, replyReady: false }

    const replyReady = canonicalMessages.some(
      (message) => message.role === 'assistant' && messageClientId(message) === clientMessageId,
    )
    if (!disposed && active.value?.id === sessionId) {
      applyConversation(data, { moveToFront: true })
      await scrollBottom()
    } else {
      mergeSessionSummary(sessionId, data, true)
    }
    return { accepted: true, replyReady }
  } catch {
    return { accepted: false, replyReady: false }
  }
}

async function send(textOverride = '') {
  const content = (textOverride || input.value).trim()
  if (!content || interactionLocked.value || !active.value || !isActive.value) return

  const sessionId = active.value.id
  const clientMessageId = createClientMessageId()
  const optimistic = {
    id: `local-${clientMessageId}`,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
    client_message_id: clientMessageId,
    metadata: { client_message_id: clientMessageId },
    pending: true,
  }
  messages.value.push(optimistic)
  input.value = ''
  sending.value = true
  await scrollBottom()
  try {
    const data = await api.sendTalkMessage(sessionId, content, clientMessageId)
    if (disposed) return
    const summary = {
      ...(data.conversation || {}),
      profile: data.profile,
      updated_at: new Date().toISOString(),
    }
    mergeSessionSummary(sessionId, summary, true)
    if (active.value?.id !== sessionId) return

    const index = messages.value.findIndex((item) => item.id === optimistic.id)
    if (index >= 0) {
      messages.value[index] = data.user_message || { ...optimistic, pending: false }
    }
    if (data.message && !messages.value.some((item) => item.id === data.message.id)) {
      messages.value.push(data.message)
    }
    profile.value = data.profile
    active.value = {
      ...active.value,
      ...data.conversation,
      profile: data.profile,
      messages: messages.value,
      updated_at: summary.updated_at,
    }
    await scrollBottom()
  } catch (error) {
    let reconciled = await reconcileFailedSend(sessionId, clientMessageId)
    for (let attempt = 0; reconciled.accepted && !reconciled.replyReady && attempt < 6; attempt += 1) {
      await wait(2000)
      if (disposed) return
      reconciled = await reconcileFailedSend(sessionId, clientMessageId)
    }
    if (disposed) return
    if (reconciled.accepted) {
      const message = t(reconciled.replyReady ? 'talk.sendRecovered' : 'talk.sendAccepted')
      if (reconciled.replyReady) ElMessage.success(message)
      else ElMessage.info(message)
    } else if (active.value?.id === sessionId) {
      const index = messages.value.findIndex((item) => item.id === optimistic.id)
      if (index >= 0) {
        messages.value[index] = { ...messages.value[index], pending: false, failed: true }
      }
      ElMessage.error(t('talk.sendFailed', { msg: extractError(error) }))
    }
  } finally {
    sending.value = false
  }
}

async function convertToOrder() {
  if (!conversionReady.value || interactionLocked.value) return
  const sessionId = active.value.id
  converting.value = true
  try {
    await ElMessageBox.confirm(
      t('talk.consentDetail'),
      t('talk.consentTitle'),
      {
        confirmButtonText: t('talk.confirmOrder'),
        cancelButtonText: t('common.cancel'),
        type: 'info',
      },
    )
  } catch {
    converting.value = false
    return
  }

  try {
    const data = await api.convertTalkSession(sessionId, true)
    if (disposed) return
    mergeSessionSummary(sessionId, data.conversation, true)
    if (active.value?.id !== sessionId) return
    applyConversation(data.conversation, { moveToFront: true })
    ElMessage.success(t('talk.orderCreated'))
    await scrollBottom()
  } catch (error) {
    ElMessage.error(t('talk.convertFailed', { msg: extractError(error) }))
  } finally {
    converting.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => {
  disposed = true
  sessionRequestId += 1
})
</script>

<template>
  <section class="talk-page">
    <aside class="talk-history">
      <div class="history-head">
        <div>
          <small>{{ t('talk.historyEyebrow') }}</small>
          <h2>{{ t('talk.history') }}</h2>
        </div>
        <el-button
          circle
          type="primary"
          plain
          :loading="creating"
          :disabled="interactionLocked"
          :aria-label="t('talk.newSession')"
          @click="startNew()"
        >
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
      <div class="history-list">
        <button
          v-for="session in sessions"
          :key="session.id"
          type="button"
          class="history-item"
          :class="{ active: active?.id === session.id }"
          :disabled="interactionLocked"
          :aria-current="active?.id === session.id ? 'page' : undefined"
          @click="openSession(session.id)"
        >
          <span class="history-icon"><el-icon><ChatLineRound /></el-icon></span>
          <span class="history-copy">
            <b>{{ session.title || t('talk.untitled') }}</b>
            <small>{{ stageLabel(session) }} · {{ formatTime(session.updated_at) }}</small>
          </span>
        </button>
      </div>
    </aside>

    <main class="talk-card" v-loading="loading">
      <header class="talk-head">
        <div class="advisor">
          <span class="advisor-avatar"><el-icon><Service /></el-icon></span>
          <span>
            <b>{{ t('talk.title') }}</b>
            <small><i></i>{{ t('talk.online') }} · {{ stageLabel(active) }}</small>
          </span>
        </div>
        <div class="mobile-actions">
          <el-button
            size="small"
            circle
            plain
            :disabled="interactionLocked"
            :aria-label="t('talk.openHistory')"
            @click="historyVisible = true"
          >
            <el-icon><ChatLineRound /></el-icon>
          </el-button>
          <el-button
            size="small"
            circle
            plain
            :loading="creating"
            :disabled="interactionLocked"
            :aria-label="t('talk.newSession')"
            @click="startNew()"
          >
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
      </header>

      <div v-if="profile" class="profile-progress">
        <div class="progress-copy">
          <span>{{ t('talk.profileProgress') }}</span>
          <b>{{ completion }}%</b>
        </div>
        <el-progress :percentage="completion" :stroke-width="6" :show-text="false" color="#23a97c" />
        <div class="profile-facts">
          <span v-if="profile.city">{{ profile.city }}</span>
          <span v-if="profile.area">{{ profile.area }}㎡</span>
          <span v-if="profile.style">{{ term(profile.style) }}</span>
          <span v-for="pain in (profile.pain_points || []).slice(0, 2)" :key="pain">{{ term(pain) }}</span>
        </div>
      </div>

      <div ref="messagePane" class="message-pane" aria-live="polite">
        <div class="day-label">{{ t('talk.today') }}</div>
        <article
          v-for="message in messages"
          :key="message.id"
          class="message-row"
          :class="`is-${message.role}`"
        >
          <span v-if="message.role === 'assistant'" class="bubble-avatar"><el-icon><Service /></el-icon></span>
          <div class="bubble-wrap" :class="{ 'has-tools': toolResults(message).length }">
            <div class="bubble" :class="{ pending: message.pending, failed: message.failed }">
              {{ displayMessage(message) }}
            </div>
            <section
              v-for="result in toolResults(message)"
              :key="`${message.id}-${result.kind}`"
              class="tool-card"
            >
              <header class="tool-card-head">
                <b>{{ result.title }}</b>
                <el-tag v-if="result.ready" size="small" type="success">{{ t('talk.tools.ready') }}</el-tag>
              </header>
              <div v-if="result.items?.length" class="tool-grid">
                <article v-for="item in result.items" :key="`${result.kind}-${item.id}`" class="tool-item">
                  <el-image
                    v-if="resolveMediaUrl(item.image_url)"
                    :src="resolveMediaUrl(item.image_url)"
                    fit="cover"
                    class="tool-image"
                    :preview-src-list="[resolveMediaUrl(item.image_url)]"
                    preview-teleported
                  >
                    <template #error>
                      <div class="tool-image tool-image-placeholder"><el-icon><Picture /></el-icon></div>
                    </template>
                  </el-image>
                  <div v-else-if="['products', 'renders', 'schemes', 'designers'].includes(result.kind)" class="tool-image tool-image-placeholder">
                    <el-icon><Picture /></el-icon>
                  </div>
                  <div class="tool-item-body">
                    <div class="tool-item-title">
                      <b>{{ item.title }}</b>
                      <el-tag v-if="item.status" size="small" effect="plain">{{ item.status }}</el-tag>
                    </div>
                    <small v-if="item.subtitle">{{ item.subtitle }}</small>
                    <div v-if="item.badges?.length" class="tool-badges">
                      <span v-for="badge in item.badges" :key="badge">{{ badge }}</span>
                    </div>
                    <p v-if="item.description">{{ item.description }}</p>
                    <div class="tool-item-foot">
                      <strong v-if="toolPrice(item)">{{ toolPrice(item) }}</strong>
                      <span v-if="item.rating">{{ t('talk.tools.rating', { rating: item.rating }) }}</span>
                      <el-button v-if="item.path" link type="primary" size="small" @click="openToolPath(item.path)">
                        {{ t('talk.tools.details') }}
                      </el-button>
                      <a v-if="item.href" :href="item.href" target="_blank" rel="noopener noreferrer">
                        {{ t('talk.tools.buy') }}
                      </a>
                    </div>
                  </div>
                </article>
              </div>
              <p v-else-if="result.empty_message" class="tool-empty">{{ result.empty_message }}</p>
              <el-button
                v-if="result.action"
                class="tool-action"
                :type="result.action.type === 'convert' ? 'primary' : 'success'"
                plain
                round
                size="small"
                :loading="result.action.type === 'convert' && converting"
                :disabled="interactionLocked || (result.action.type === 'convert' && !conversionReady)"
                @click="runToolAction(result.action)"
              >
                {{ toolActionLabel(result.action) }}
              </el-button>
            </section>
            <time>{{ formatTime(message.created_at) }}</time>
          </div>
        </article>
        <article v-if="sending" class="message-row is-assistant" role="status" :aria-label="t('talk.replying')">
          <span class="bubble-avatar"><el-icon><Service /></el-icon></span>
          <div class="bubble typing"><i></i><i></i><i></i></div>
        </article>
      </div>

      <div v-if="quickReplies.length && isActive" class="quick-replies">
        <button
          v-for="option in quickReplies"
          :key="option.value"
          type="button"
          :disabled="interactionLocked"
          @click="send(option.value)"
        >
          {{ option.label }}
        </button>
      </div>

      <div v-if="conversionReady && !latestHasOrderAction" class="conversion-card">
        <span class="conversion-icon"><el-icon><CircleCheckFilled /></el-icon></span>
        <div>
          <b>{{ t('talk.readyTitle') }}</b>
          <small>{{ t('talk.readyHint') }}</small>
        </div>
        <el-button type="primary" round :loading="converting" @click="convertToOrder">
          {{ t('talk.createOrder') }}
        </el-button>
      </div>

      <div v-else-if="active?.status === 'converted'" class="conversion-card is-done">
        <span class="conversion-icon"><el-icon><CircleCheckFilled /></el-icon></span>
        <div>
          <b>{{ t('talk.completedTitle') }}</b>
          <small>{{ t('talk.completedHint') }}</small>
        </div>
        <el-button type="success" plain round @click="router.push({ path: '/my-home', query: { tab: 'orders' } })">
          {{ t('talk.viewOrder') }}
        </el-button>
      </div>

      <footer class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          resize="none"
          maxlength="1000"
          :disabled="!isActive || interactionLocked"
          :aria-label="t('talk.messageInputLabel')"
          :placeholder="isActive ? t('talk.placeholder') : t('talk.closedPlaceholder')"
          @keydown.enter.exact.prevent="send()"
        />
        <el-button
          class="send-button"
          type="primary"
          circle
          :disabled="!input.trim() || !isActive || interactionLocked"
          :loading="sending"
          :aria-label="t('chat.send')"
          @click="send()"
        >
          <el-icon v-if="!sending"><Promotion /></el-icon>
        </el-button>
      </footer>
      <p class="privacy-note"><el-icon><Lock /></el-icon>{{ t('talk.privacy') }}</p>
    </main>

    <el-drawer
      v-model="historyVisible"
      :title="t('talk.history')"
      direction="ltr"
      size="86%"
      append-to-body
    >
      <div class="drawer-history">
        <el-button
          class="drawer-new"
          type="primary"
          plain
          round
          :loading="creating"
          :disabled="interactionLocked"
          @click="startNew()"
        >
          <el-icon><Plus /></el-icon>{{ t('talk.newSession') }}
        </el-button>
        <p v-if="!sessions.length" class="history-empty">{{ t('talk.noSessions') }}</p>
        <div v-else class="history-list">
          <button
            v-for="session in sessions"
            :key="session.id"
            type="button"
            class="history-item"
            :class="{ active: active?.id === session.id }"
            :disabled="interactionLocked"
            :aria-current="active?.id === session.id ? 'page' : undefined"
            @click="openSession(session.id)"
          >
            <span class="history-icon"><el-icon><ChatLineRound /></el-icon></span>
            <span class="history-copy">
              <b>{{ session.title || t('talk.untitled') }}</b>
              <small>{{ stageLabel(session) }} · {{ formatTime(session.updated_at) }}</small>
            </span>
          </button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.talk-page {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 18px;
  min-height: min(760px, calc(100vh - 120px));
}

.talk-history,
.talk-card {
  border: 1px solid rgba(35, 169, 124, 0.12);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 45px rgba(50, 68, 58, 0.08);
}

.talk-history { border-radius: 24px; padding: 18px 12px; overflow: hidden; }
.history-head { display: flex; justify-content: space-between; align-items: center; padding: 0 6px 14px; }
.history-head small { color: var(--brand-green); font-size: 10px; letter-spacing: 0.12em; font-weight: 800; }
.history-head h2 { margin: 3px 0 0; color: var(--brand-ink); font-size: 18px; }
.history-list { display: flex; flex-direction: column; gap: 6px; max-height: calc(100vh - 210px); overflow-y: auto; }
.history-item { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px 10px; border: 0; border-radius: 15px; background: transparent; color: var(--brand-muted); text-align: left; cursor: pointer; }
.history-item:hover, .history-item.active { background: rgba(35, 169, 124, 0.09); color: var(--brand-green-deep); }
.history-item:disabled { cursor: wait; opacity: .55; }
.history-icon { flex: none; display: grid; place-items: center; width: 32px; height: 32px; border-radius: 10px; background: #fff; border: 1px solid rgba(35, 169, 124, 0.12); }
.history-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.history-copy b, .history-copy small { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.history-copy b { font-size: 13px; }
.history-copy small { color: var(--brand-muted); font-size: 10px; }

.talk-card { display: flex; flex-direction: column; min-width: 0; border-radius: 28px; overflow: hidden; }
.talk-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 22px; border-bottom: 1px solid rgba(35, 169, 124, 0.09); }
.advisor { display: flex; align-items: center; gap: 11px; }
.advisor > span:last-child { display: flex; flex-direction: column; gap: 3px; }
.advisor b { color: var(--brand-ink); font-size: 16px; }
.advisor small { display: flex; align-items: center; gap: 5px; color: var(--brand-muted); font-size: 11px; }
.advisor small i { width: 7px; height: 7px; border-radius: 50%; background: #35bd8d; box-shadow: 0 0 0 3px rgba(53, 189, 141, 0.13); }
.advisor-avatar, .bubble-avatar { display: grid; place-items: center; color: #fff; background: linear-gradient(145deg, #35bd8d, #168a65); box-shadow: 0 7px 18px rgba(35, 169, 124, 0.18); }
.advisor-avatar { width: 42px; height: 42px; border-radius: 15px; font-size: 21px; }
.mobile-actions { display: none; align-items: center; gap: 6px; }

.profile-progress { padding: 11px 22px 10px; background: linear-gradient(90deg, rgba(35, 169, 124, 0.07), rgba(245, 237, 221, 0.25)); }
.progress-copy { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; color: var(--brand-muted); font-size: 11px; }
.progress-copy b { color: var(--brand-green-deep); }
.profile-facts { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; min-height: 19px; }
.profile-facts span { padding: 2px 8px; border-radius: 999px; background: rgba(255,255,255,.75); color: var(--brand-wood-deep); font-size: 10px; }

.message-pane { flex: 1; min-height: 360px; overflow-y: auto; padding: 18px 22px; background: linear-gradient(180deg, rgba(248, 251, 249, .92), rgba(247, 243, 235, .58)); scroll-behavior: smooth; }
.day-label { width: max-content; margin: 0 auto 16px; padding: 3px 10px; border-radius: 999px; color: #8b968f; background: rgba(255,255,255,.75); font-size: 10px; }
.message-row { display: flex; align-items: flex-end; gap: 8px; margin: 11px 0; }
.message-row.is-user { justify-content: flex-end; }
.bubble-avatar { flex: none; width: 28px; height: 28px; border-radius: 10px; font-size: 14px; }
.bubble-wrap { max-width: min(76%, 570px); display: flex; flex-direction: column; gap: 3px; }
.bubble-wrap.has-tools { width: min(92%, 760px); max-width: min(92%, 760px); }
.bubble { padding: 10px 13px; border-radius: 17px; font-size: 14px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.is-assistant .bubble { color: #33443b; background: #fff; border: 1px solid rgba(35,169,124,.10); border-bottom-left-radius: 5px; box-shadow: 0 5px 14px rgba(48, 66, 56, .05); }
.is-user .bubble { color: #fff; background: linear-gradient(135deg, #35bd8d, #1c9a70); border-bottom-right-radius: 5px; box-shadow: 0 7px 18px rgba(35,169,124,.15); }
.bubble.pending { opacity: .65; }
.bubble.failed { outline: 2px solid rgba(245,108,108,.45); }
.bubble-wrap time { padding: 0 4px; color: #a3aaa6; font-size: 9px; }
.is-user .bubble-wrap time { text-align: right; }
.tool-card { margin-top: 5px; padding: 12px; border: 1px solid rgba(35,169,124,.14); border-radius: 16px; background: rgba(255,255,255,.96); box-shadow: 0 8px 22px rgba(48,66,56,.06); }
.tool-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 9px; }
.tool-card-head b { color: var(--brand-ink); font-size: 13px; }
.tool-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.tool-item { min-width: 0; overflow: hidden; border: 1px solid rgba(35,169,124,.10); border-radius: 12px; background: #f9fbfa; }
.tool-image { display: block; width: 100%; height: 112px; background: #edf3ef; }
.tool-image-placeholder { display: grid; place-items: center; color: #91a098; font-size: 26px; }
.tool-item-body { display: flex; flex-direction: column; gap: 4px; padding: 9px; }
.tool-item-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 6px; }
.tool-item-title b { min-width: 0; overflow: hidden; color: var(--brand-ink); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.tool-item-body > small { overflow: hidden; color: var(--brand-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.tool-item-body > p { display: -webkit-box; overflow: hidden; margin: 2px 0; color: #637168; font-size: 10px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.tool-badges { display: flex; flex-wrap: wrap; gap: 4px; }
.tool-badges span { padding: 1px 6px; border-radius: 999px; background: rgba(35,169,124,.08); color: var(--brand-green-deep); font-size: 9px; }
.tool-item-foot { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; min-height: 20px; color: var(--brand-muted); font-size: 10px; }
.tool-item-foot strong { margin-right: auto; color: #d66a35; font-size: 12px; }
.tool-item-foot a { color: var(--brand-green-deep); text-decoration: none; }
.tool-empty { margin: 0 0 9px; color: var(--brand-muted); font-size: 11px; line-height: 1.6; }
.tool-action { margin-top: 9px; width: 100%; }
.typing { display: flex; gap: 4px; width: 52px; }
.typing i { width: 5px; height: 5px; border-radius: 50%; background: #8e9d95; animation: typing 1.1s infinite ease-in-out; }
.typing i:nth-child(2) { animation-delay: .15s; }
.typing i:nth-child(3) { animation-delay: .3s; }
@keyframes typing { 0%, 70%, 100% { transform: translateY(0); opacity: .35; } 35% { transform: translateY(-4px); opacity: 1; } }

.quick-replies { display: flex; gap: 7px; padding: 8px 22px 4px; overflow-x: auto; }
.quick-replies button { flex: none; padding: 7px 11px; border: 1px solid rgba(35,169,124,.18); border-radius: 999px; color: var(--brand-green-deep); background: rgba(255,255,255,.9); font: inherit; font-size: 11px; cursor: pointer; }
.quick-replies button:hover { background: rgba(35,169,124,.08); }
.quick-replies button:disabled { cursor: wait; opacity: .55; }

.conversion-card { display: flex; align-items: center; gap: 10px; margin: 10px 22px 2px; padding: 11px 13px; border-radius: 16px; background: rgba(35,169,124,.08); border: 1px solid rgba(35,169,124,.13); }
.conversion-icon { flex: none; color: var(--brand-green); font-size: 22px; }
.conversion-card > div { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.conversion-card b { color: var(--brand-ink); font-size: 12px; }
.conversion-card small { color: var(--brand-muted); font-size: 10px; line-height: 1.45; }
.conversion-card.is-done { background: rgba(103,194,58,.08); }

.composer { display: flex; align-items: flex-end; gap: 9px; padding: 12px 22px 5px; }
.composer :deep(.el-textarea__inner) { min-height: 43px !important; padding: 11px 14px; border: 1px solid rgba(35,169,124,.13); border-radius: 17px; box-shadow: none; background: #f8faf9; }
.send-button { flex: none; width: 42px; height: 42px; font-size: 18px; }
.privacy-note { display: flex; align-items: center; justify-content: center; gap: 4px; margin: 3px 16px 10px; color: #99a29d; font-size: 9px; text-align: center; }
.drawer-history { display: flex; flex-direction: column; gap: 12px; min-height: 100%; }
.drawer-history .history-list { max-height: none; flex: 1; }
.drawer-new { width: 100%; flex: none; }
.history-empty { margin: 24px 0; color: var(--brand-muted); font-size: 13px; text-align: center; }

@media (max-width: 760px) {
  .talk-page { display: block; min-height: calc(100vh - 110px); }
  .talk-history { display: none; }
  .talk-card { min-height: calc(100vh - 112px); border-radius: 22px; }
  .mobile-actions { display: flex; }
  .talk-head, .profile-progress { padding-left: 15px; padding-right: 15px; }
  .message-pane { min-height: 0; padding: 14px 14px; }
  .bubble-wrap { max-width: 84%; }
  .bubble-wrap.has-tools { width: 94%; max-width: 94%; }
  .tool-grid { grid-template-columns: 1fr; }
  .tool-image { height: 150px; }
  .quick-replies { padding-left: 14px; padding-right: 14px; }
  .conversion-card { margin-left: 14px; margin-right: 14px; align-items: flex-start; flex-wrap: wrap; }
  .conversion-card .el-button { width: 100%; }
  .composer { padding-left: 14px; padding-right: 14px; }
}
</style>
