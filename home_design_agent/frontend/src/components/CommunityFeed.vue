<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const titles = [
  '小户型客厅怎么选沙发？这三款值得看',
  '现代简约不翻车：灯光这样布置',
  '原木餐桌和岩板餐桌怎么选？',
  '旧房翻新，这些施工顺序别搞反',
  '奶油风卧室配色，照着抄就行',
  '卫生间干湿分离，小空间也能做',
  '阳台封窗前后对比，真的太香了',
  '客厅不放电视柜，收纳反而更多',
  '无主灯设计避坑指南',
  '开放式厨房到底适不适合你？',
  '玄关柜这样设计，回家不再乱',
  '儿童房家具怎么选更安全？',
  '意式极简沙发的搭配思路',
  '窗帘颜色选错，整个家都暗了',
  '小书房也能拥有双人办公位',
  '卫生间瓷砖美缝，颜色这样选',
  '原木风装修预算怎么控制？',
  '卧室床头背景墙的三种做法',
  '客厅地毯尺寸到底买多大？',
  '浅色地板和深色地板怎么选？',
  '灯具色温怎么选才不显廉价？',
  '厨房台面高度按身高定，更省力',
  '客餐厅一体化布局要注意什么？',
  '衣柜内部格局这样规划更实用',
  '奶油风沙发颜色搭配建议',
  '旧房墙面翻新，先处理这些',
  '书架墙和电视墙可以兼得吗？',
  '入户门改色，低成本提升质感',
  '小卫生间收纳技巧，真的能装',
  '阳台洗衣柜布局，尺寸别踩坑',
]

const authors = [
  '木木家的装修笔记',
  '设计师林岚',
  '入住一年的小鹿',
  '匠心施工队',
  '奶油风收纳研究所',
  '极简家装指南',
  '小户型改造手记',
  '原木生活家',
]

const summaries = [
  '低靠背、细腿设计更适合小空间，视觉更轻盈。',
  '主灯 + 局部氛围灯，空间层次感会明显提升。',
  '有小朋友的家庭更推荐圆角款，安全也好打理。',
  '先水电再墙地面，最后定制柜与软装进场。',
  '浅色搭配更显大，家具选择也要尽量轻量。',
  '提前预留水电点位，后期使用会方便很多。',
  '动线顺畅比多打柜子更重要，先规划再施工。',
  '颜色不要超过三种，整体会更耐看。',
]

const types = ['furniture', 'designer', 'contractor']

const visibleTitles = titles.slice(0, 15)

const covers = Array.from(
  { length: visibleTitles.length },
  (_, index) => `/media/renders/render_${index + 1}.png`,
)

const posts = visibleTitles.map((title, index) => ({
  type: types[index % types.length],
  title,
  author: authors[index % authors.length],
  summary: summaries[index % summaries.length],
  cover: covers[index],
}))

function typeLabel(type) {
  return t(`community.${type}`)
}
</script>

<template>
  <section class="community-feed">
    <header class="community-header">
      <b>{{ t('community.title') }}</b>
      <span>{{ t('community.subtitle') }}</span>
    </header>
    <div class="post-grid">
      <article v-for="post in posts" :key="post.title" class="post-card">
        <div class="post-cover">
          <img :src="post.cover" :alt="post.title" loading="lazy" decoding="async" />
          <span class="post-type">{{ typeLabel(post.type) }}</span>
        </div>
        <div class="post-copy">
          <b>{{ post.title }}</b>
          <span class="post-author">{{ post.author }}</span>
          <p>{{ post.summary }}</p>
        </div>
      </article>
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
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.post-card {
  border: 1px solid var(--app-border);
  border-radius: 11px;
  overflow: hidden;
  background: #fff;
}

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
.post-author { display: block; margin-top: 3px; color: var(--brand-muted); font-size: 9px; }
.post-copy p { margin: 5px 0 0; color: var(--brand-ink); font-size: 10px; line-height: 1.4; }

@media (max-width: 720px) {
  .post-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>