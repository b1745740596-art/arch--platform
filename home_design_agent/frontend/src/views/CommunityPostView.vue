<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import fallbackCover from '@/assets/hero.png'
import { communityPosts, getCommunityPost } from '@/data/communityPosts'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const liked = ref(false)
const saved = ref(false)
const followed = ref(false)
const post = computed(() => getCommunityPost(route.params.id))
const likeCount = computed(() => (post.value?.likes || 0) + (liked.value ? 1 : 0))
const relatedPosts = computed(() => {
  if (!post.value) return []
  return communityPosts
    .filter((item) => item.id !== post.value.id)
    .sort((left, right) => Number(right.type === post.value.type) - Number(left.type === post.value.type))
    .slice(0, 4)
})

function goBack() {
  if (window.history.state?.back) {
    router.back()
    return
  }
  router.replace('/my-home')
}

function openPost(id) {
  router.push({ name: 'community-post', params: { id } })
}

function scrollToComments() {
  document.querySelector('#community-comments')?.scrollIntoView({ behavior: 'smooth' })
}

function handleCoverError(event) {
  const image = event.currentTarget
  if (!image || image.dataset.fallbackApplied === 'true') return
  image.dataset.fallbackApplied = 'true'
  image.src = fallbackCover
}

function resetInteractionState() {
  liked.value = false
  saved.value = false
  followed.value = false
  window.scrollTo({ top: 0, behavior: 'auto' })
}

onMounted(resetInteractionState)
watch(() => route.params.id, resetInteractionState)
</script>

<template>
  <section v-if="post" class="community-post-page">
    <header class="post-detail-header">
      <button type="button" class="round-action" :aria-label="t('community.back')" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <span>{{ t('community.note') }}</span>
      <button
        type="button"
        class="round-action"
        :class="{ active: saved }"
        :aria-label="t('community.favorite')"
        @click="saved = !saved"
      >
        <el-icon><CollectionTag /></el-icon>
      </button>
    </header>

    <div class="post-detail-shell">
      <div class="post-visual">
        <img :src="post.cover" :alt="post.title" @error="handleCoverError" />
        <span>1 / 1</span>
      </div>

      <article class="post-article">
        <div class="author-row">
          <span class="author-avatar">{{ post.author.slice(0, 1) }}</span>
          <div class="author-copy">
            <b>{{ post.author }}</b>
            <small>{{ t(`community.${post.type}`) }} · {{ post.publishedAt }}</small>
          </div>
          <button
            type="button"
            class="follow-button"
            :class="{ followed }"
            @click="followed = !followed"
          >
            {{ followed ? t('community.followed') : t('community.follow') }}
          </button>
        </div>

        <h1>{{ post.title }}</h1>
        <p class="post-lead">{{ post.summary }}</p>
        <p v-for="paragraph in post.body" :key="paragraph" class="post-paragraph">{{ paragraph }}</p>

        <div class="post-tags">
          <span v-for="tag in post.tags" :key="tag"># {{ tag }}</span>
        </div>

        <div class="post-published">{{ t('community.publishedAt', { time: post.publishedAt }) }}</div>

        <section id="community-comments" class="comments-section">
          <h2>{{ t('community.comments', { count: post.comments.length }) }}</h2>
          <div v-for="comment in post.comments" :key="comment.id" class="comment-row">
            <span class="comment-avatar">{{ comment.author.slice(0, 1) }}</span>
            <div class="comment-body">
              <b>{{ comment.author }}</b>
              <p>{{ comment.content }}</p>
            </div>
            <span class="comment-like"><el-icon><Star /></el-icon>{{ comment.likes }}</span>
          </div>
        </section>
      </article>
    </div>

    <section class="related-section">
      <h2>{{ t('community.related') }}</h2>
      <div class="related-grid">
        <button
          v-for="item in relatedPosts"
          :key="item.id"
          type="button"
          class="related-card"
          @click="openPost(item.id)"
        >
          <img :src="item.cover" :alt="item.title" @error="handleCoverError" />
          <span>{{ item.title }}</span>
        </button>
      </div>
    </section>

    <div class="post-action-dock">
      <button type="button" class="comment-entry" @click="scrollToComments">
        {{ t('community.saySomething') }}
      </button>
      <button type="button" :class="{ active: liked }" @click="liked = !liked">
        <el-icon><StarFilled v-if="liked" /><Star v-else /></el-icon>
        <span>{{ likeCount }}</span>
      </button>
      <button type="button" :class="{ active: saved }" @click="saved = !saved">
        <el-icon><CollectionTag /></el-icon>
        <span>{{ post.favorites + (saved ? 1 : 0) }}</span>
      </button>
      <button type="button" @click="scrollToComments">
        <el-icon><ChatDotRound /></el-icon>
        <span>{{ post.comments.length }}</span>
      </button>
    </div>
  </section>

  <section v-else class="post-not-found">
    <el-icon><Picture /></el-icon>
    <h1>{{ t('community.notFound') }}</h1>
    <el-button type="primary" @click="router.replace('/my-home')">{{ t('community.backToFeed') }}</el-button>
  </section>
</template>

<style scoped>
.community-post-page {
  --detail-border: rgba(17, 24, 39, 0.08);
  position: relative;
  padding-bottom: 74px;
}

.post-detail-header {
  position: sticky;
  top: 0;
  z-index: 25;
  display: grid;
  grid-template-columns: 38px 1fr 38px;
  align-items: center;
  gap: 10px;
  max-width: 1080px;
  margin: 0 auto 12px;
  padding: 8px 2px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.post-detail-header > span { text-align: center; font-size: 14px; font-weight: 800; }

.round-action {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 1px solid var(--detail-border);
  border-radius: 50%;
  background: #fff;
  color: var(--brand-ink);
  font-size: 18px;
  cursor: pointer;
}

.round-action.active { color: var(--brand-green); background: var(--brand-green-soft); }

.post-detail-shell {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(360px, 0.88fr);
  max-width: 1080px;
  margin: 0 auto;
  overflow: hidden;
  border: 1px solid var(--detail-border);
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 20px 52px rgba(17, 24, 39, 0.08);
}

.post-visual {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 620px;
  background: #f4f5f4;
}

.post-visual img {
  width: 100%;
  height: 100%;
  max-height: 760px;
  object-fit: contain;
  display: block;
}

.post-visual > span {
  position: absolute;
  right: 14px;
  bottom: 14px;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.58);
  color: #fff;
  font-size: 11px;
}

.post-article { padding: 22px 24px 28px; border-left: 1px solid var(--detail-border); }

.author-row { display: flex; align-items: center; gap: 10px; }
.author-avatar,
.comment-avatar {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 50%;
  background: linear-gradient(145deg, #dff6ec, #a9e5cc);
  color: #147a57;
  font-weight: 800;
}
.author-avatar { width: 40px; height: 40px; font-size: 15px; }
.author-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.author-copy b { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.author-copy small { color: var(--brand-muted); font-size: 10px; }

.follow-button {
  min-width: 68px;
  padding: 7px 13px;
  border: 1px solid var(--brand-green);
  border-radius: 999px;
  background: var(--brand-green);
  color: #fff;
  font: inherit;
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}
.follow-button.followed { border-color: var(--detail-border); background: #fff; color: var(--brand-muted); }

.post-article h1 { margin: 24px 0 10px; font-size: 23px; line-height: 1.38; }
.post-lead { margin: 0 0 16px; color: #374151; font-size: 14px; font-weight: 650; line-height: 1.8; }
.post-paragraph { margin: 0 0 14px; color: #374151; font-size: 13px; line-height: 1.9; }

.post-tags { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 18px; }
.post-tags span { color: #16865f; font-size: 12px; }
.post-published { margin-top: 18px; color: var(--brand-muted); font-size: 10px; }

.comments-section { margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--detail-border); }
.comments-section h2,
.related-section h2 { margin: 0 0 14px; font-size: 15px; }
.comment-row { display: flex; align-items: flex-start; gap: 9px; padding: 11px 0; }
.comment-avatar { width: 30px; height: 30px; font-size: 11px; }
.comment-body { min-width: 0; flex: 1; }
.comment-body b { color: var(--brand-muted); font-size: 10px; font-weight: 650; }
.comment-body p { margin: 3px 0 0; color: #374151; font-size: 12px; line-height: 1.6; }
.comment-like { display: inline-flex; align-items: center; gap: 2px; color: var(--brand-muted); font-size: 10px; }

.related-section { max-width: 1080px; margin: 28px auto 0; }
.related-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.related-card {
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--detail-border);
  border-radius: 14px;
  background: #fff;
  color: var(--brand-ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.related-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; }
.related-card span { display: -webkit-box; margin: 9px 10px 11px; overflow: hidden; font-size: 11px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }

.post-action-dock {
  position: fixed;
  left: 50%;
  bottom: max(12px, env(safe-area-inset-bottom));
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(560px, calc(100vw - 28px));
  padding: 9px 10px;
  border: 1px solid var(--detail-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 14px 40px rgba(17, 24, 39, 0.15);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transform: translateX(-50%);
}

.post-action-dock button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 42px;
  padding: 7px 5px;
  border: 0;
  background: transparent;
  color: #4b5563;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.post-action-dock button.active { color: var(--brand-green); }
.post-action-dock .el-icon { font-size: 19px; }
.post-action-dock .comment-entry {
  flex: 1;
  justify-content: flex-start;
  min-width: 0;
  padding: 9px 13px;
  border-radius: 999px;
  background: #f3f4f6;
  color: var(--brand-muted);
}

.post-not-found { display: grid; place-items: center; gap: 12px; min-height: 55vh; text-align: center; }
.post-not-found .el-icon { color: var(--brand-muted); font-size: 42px; }
.post-not-found h1 { margin: 0; font-size: 18px; }

@media (max-width: 760px) {
  .community-post-page { margin: -12px; padding-bottom: 76px; }
  .post-detail-header { margin-bottom: 0; padding: 9px 12px; border-bottom: 1px solid var(--detail-border); }
  .post-detail-shell { display: block; border: 0; border-radius: 0; box-shadow: none; }
  .post-visual { min-height: 0; aspect-ratio: 4 / 3; }
  .post-visual img { height: 100%; object-fit: cover; }
  .post-article { padding: 18px 16px 24px; border: 0; }
  .post-article h1 { margin-top: 20px; font-size: 19px; }
  .post-lead { font-size: 13px; }
  .post-paragraph { font-size: 13px; line-height: 1.8; }
  .related-section { margin: 12px 16px 0; padding-top: 18px; border-top: 1px solid var(--detail-border); }
  .related-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .post-action-dock { bottom: max(8px, env(safe-area-inset-bottom)); }
}
</style>
