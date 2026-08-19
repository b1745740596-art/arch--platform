<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const posts = [
  {
    type: 'furniture',
    title: '小户型客厅怎么选沙发？这三款值得看',
    author: '木木家的装修笔记',
    summary: '低靠背、细腿设计更适合小空间，视觉更轻盈。',
    tone: 'green',
  },
  {
    type: 'designer',
    title: '现代简约不翻车：灯光这样布置',
    author: '设计师林岚',
    summary: '主灯 + 局部氛围灯，空间层次感会明显提升。',
    tone: 'teal',
  },
  {
    type: 'furniture',
    title: '原木餐桌和岩板餐桌怎么选？',
    author: '入住一年的小鹿',
    summary: '有小朋友的家庭更推荐圆角款，安全也好打理。',
    tone: 'mint',
  },
  {
    type: 'contractor',
    title: '旧房翻新，这些施工顺序别搞反',
    author: '匠心施工队',
    summary: '先水电再墙地面，最后定制柜与软装进场。',
    tone: 'sky',
  },
]

function typeLabel(type) {
  return t(`community.${type}`)
}

function toneClass(tone) {
  return `tone-${tone}`
}
</script>

<template>
  <section class="community-feed">
    <el-collapse>
      <el-collapse-item :title="t('community.title')" name="feed">
        <div class="post-grid">
          <article v-for="post in posts" :key="post.title" class="post-card">
            <div class="post-cover" :class="toneClass(post.tone)">
              <el-icon><Picture /></el-icon>
              <span>{{ typeLabel(post.type) }}</span>
            </div>
            <div class="post-copy">
              <b>{{ post.title }}</b>
              <span class="post-author">{{ post.author }}</span>
              <p>{{ post.summary }}</p>
            </div>
          </article>
        </div>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<style scoped>
.community-feed { margin-top: 14px; }
.community-feed :deep(.el-collapse) {
  border: 1px solid var(--app-border);
  border-radius: 16px;
  overflow: hidden;
  background: var(--app-surface);
}
.community-feed :deep(.el-collapse-item__header) {
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 800;
  color: var(--brand-green-deep);
  background: #fff;
}
.community-feed :deep(.el-collapse-item__content) { padding: 0 12px 12px; }

.post-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.post-card {
  border: 1px solid var(--app-border);
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

.post-cover {
  aspect-ratio: 16 / 9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
}
.post-cover .el-icon { font-size: 28px; }
.tone-green { background: linear-gradient(135deg, #35bd8d, #23a97c); }
.tone-teal { background: linear-gradient(135deg, #4cc6b0, #2aa28d); }
.tone-mint { background: linear-gradient(135deg, #7fd6b2, #4cb58f); }
.tone-sky { background: linear-gradient(135deg, #77b9e8, #4a9ac9); }

.post-copy { padding: 9px 10px 10px; }
.post-copy b { display: block; font-size: 13px; line-height: 1.4; }
.post-author { display: block; margin-top: 4px; color: var(--brand-muted); font-size: 11px; }
.post-copy p { margin: 6px 0 0; color: var(--brand-ink); font-size: 11px; line-height: 1.5; }

@media (max-width: 720px) {
  .post-grid { grid-template-columns: 1fr; }
}
</style>