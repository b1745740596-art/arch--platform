<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const input = ref('')
const messages = ref([{ role: 'assistant', text: t('chat.welcome') }])

function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  ElMessage.info(t('chat.comingSoon'))
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="t('chat.title')"
    width="min(420px, 92vw)"
    align-center
    class="app-chat-dialog"
  >
    <div class="chat-body">
      <div class="messages">
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message"
          :class="`is-${message.role}`"
        >
          {{ message.text }}
        </div>
      </div>
      <div class="chat-input">
        <el-input
          v-model="input"
          :placeholder="t('chat.placeholder')"
          @keyup.enter="send"
        />
        <el-button type="primary" @click="send">{{ t('chat.send') }}</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.chat-body { display: flex; flex-direction: column; gap: 12px; }
.messages {
  min-height: 220px;
  max-height: 46vh;
  overflow: auto;
  padding: 12px;
  border-radius: 16px;
  background: rgba(47, 107, 79, 0.05);
  border: 1px solid rgba(47, 107, 79, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.message {
  max-width: 80%;
  padding: 9px 12px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.6;
}
.message.is-assistant {
  align-self: flex-start;
  background: #fff;
  color: var(--brand-ink);
  border: 1px solid rgba(47, 107, 79, 0.10);
}
.message.is-user {
  align-self: flex-end;
  background: linear-gradient(135deg, #3b7a5b, #2f6b4f);
  color: #fff;
}
.chat-input { display: flex; gap: 8px; }
.chat-input .el-input { flex: 1; }
</style>