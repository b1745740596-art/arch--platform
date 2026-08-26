<script setup>
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import fallbackCover from '@/assets/hero.png'
import { communityPosts as posts } from '@/data/communityPosts'

const { t } = useI18n()
const router = useRouter()

function typeLabel(type) {
  return t(`community.${type}`)
}

function handleCoverError(event) {
  const image = event.currentTarget
  if (!image || image.dataset.fallbackApplied === 'true') return
  image.dataset.fallbackApplied = 'true'
  image.src = fallbackCover
}

function openPost(post) {
  router.push({ name: 'community-post', params: { id: post.id } })
}
</script>

<template>
  <section class="community-feed">
    <header class="community-header">
      <b>{{ t('community.title') }}</b>
      <span>{{ t('community.subtitle') }}</span>
    </header>
    <div class="post-grid">
      <button
        v-for="post in posts"
        :key="post.id"
        type="button"
        class="post-card"
        :aria-label="t('community.openPost', { title: post.title })"
        @click="openPost(post)"
      >
        <div class="post-cover" :style="{ aspectRatio: post.coverRatio }">
          <img
            :src="post.cover"
            :alt="post.title"
            loading="lazy"
            decoding="async"
            @error="handleCoverError"
          />
          <span class="post-type">{{ typeLabel(post.type) }}</span>
        </div>
        <div class="post-copy">
          <b>{{ post.title }}</b>
          <div class="post-meta">
            <span class="post-author"><i>{{ post.author.slice(0, 1) }}</i>{{ post.author }}</span>
            <span class="post-like"><el-icon><Star /></el-icon>{{ post.likes }}</span>
          </div>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.community-feed { margin: 0; }

.community-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  padding: 4px 2px;
}

.community-header b { font-size: 16px; color: var(--brand-green-deep); }
.community-header span { font-size: 12px; color: var(--brand-muted); }

.post-grid {
  columns: 2;
  column-gap: 8px;
}

.post-card {
  display: block;
  width: 100%;
  margin: 0 0 8px;
  padding: 0;
  border: 1px solid var(--app-border);
  border-radius: 11px;
  overflow: hidden;
  background: #fff;
  color: var(--brand-ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
  break-inside: avoid;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.post-card:active { transform: scale(0.985); }
.post-card:focus-visible { outline: 2px solid var(--brand-green); outline-offset: 2px; }

.post-cover {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  background: #eef5f1;
}
.post-cover img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.post-type {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(20, 45, 35, 0.62);
  color: #fff;
  font-size: 9px;
  font-weight: 800;
  line-height: 1.2;
}

.post-copy { padding: 7px 8px 8px; }
.post-copy b { display: block; font-size: 11px; line-height: 1.35; }

.post-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: 7px;
  color: var(--brand-muted);
  font-size: 9px;
}

.post-author {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.post-author i {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--brand-green-soft);
  color: var(--brand-green);
  font-size: 8px;
  font-style: normal;
  font-weight: 800;
}

.post-like { display: inline-flex; align-items: center; gap: 2px; flex: 0 0 auto; }
.post-like .el-icon { font-size: 10px; }

</style>
