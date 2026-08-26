import communityCover01 from '@/assets/community/community-01.jpg'
import communityCover02 from '@/assets/community/community-02.jpg'
import communityCover03 from '@/assets/community/community-03.jpg'
import communityCover04 from '@/assets/community/community-04.jpg'
import communityCover05 from '@/assets/community/community-05.jpg'
import communityCover06 from '@/assets/community/community-06.jpg'
import communityCover07 from '@/assets/community/community-07.jpg'
import communityCover08 from '@/assets/community/community-08.jpg'
import communityCover09 from '@/assets/community/community-09.jpg'
import communityCover10 from '@/assets/community/community-10.jpg'
import communityCover11 from '@/assets/community/community-11.jpg'
import communityCover12 from '@/assets/community/community-12.jpg'
import communityCover13 from '@/assets/community/community-13.jpg'
import communityCover14 from '@/assets/community/community-14.jpg'
import communityCover15 from '@/assets/community/community-15.jpg'

const covers = [
  communityCover01,
  communityCover02,
  communityCover03,
  communityCover04,
  communityCover05,
  communityCover06,
  communityCover07,
  communityCover08,
  communityCover09,
  communityCover10,
  communityCover11,
  communityCover12,
  communityCover13,
  communityCover14,
  communityCover15,
]

const seeds = [
  {
    title: '小户型客厅怎么选沙发？这三款值得看',
    author: '木木家的装修笔记',
    type: 'furniture',
    summary: '低靠背、细腿设计更适合小空间，视觉更轻盈。',
    tags: ['小户型', '客厅', '沙发选购'],
    body: [
      '小户型选沙发，尺寸比造型更重要。建议先给主要通道留出至少 80cm，再确定沙发的最大宽度，避免买回来才发现空间被塞满。',
      '低靠背、细腿和离地款能让墙面与地面露得更多，视觉上会轻很多。颜色可以跟墙面同色系，再用抱枕和地毯增加层次。',
      '如果家里经常来客，优先选模块化或带贵妃位的组合；储物沙发看起来实用，但要确认打开方式不会挡住茶几。',
    ],
  },
  {
    title: '现代简约不翻车：灯光这样布置',
    author: '设计师林岚',
    type: 'designer',
    summary: '主灯 + 局部氛围灯，空间层次感会明显提升。',
    tags: ['现代简约', '灯光设计', '装修避坑'],
    body: [
      '灯光不是越多越好，而是要跟着生活场景走。客厅基础照明、阅读照明和电视背景氛围光最好分路控制。',
      '全屋色温建议控制在 3000K 到 4000K，同一视线范围不要混用差异太大的色温。显色指数尽量选 Ra90 以上，家具颜色会更自然。',
      '射灯离墙距离、光束角和墙面材质要一起考虑。施工前先做灯位图，能避免后期出现眩光和亮斑。',
    ],
  },
  {
    title: '原木餐桌和岩板餐桌怎么选？',
    author: '入住一年的小鹿',
    type: 'furniture',
    summary: '有小朋友的家庭更推荐圆角款，安全也好打理。',
    tags: ['餐厅', '餐桌', '家具选购'],
    body: [
      '原木餐桌触感温润，日常的小划痕也更容易融入使用痕迹；岩板耐高温、好擦洗，更适合做饭频率高的家庭。',
      '选择时不要只看台面，桌腿位置会直接影响座位舒适度。建议现场坐下试一试，确认腿部不会碰到支撑结构。',
      '有孩子的家庭优先圆角或大倒角，桌面高度建议在 72cm 到 76cm，并和现有餐椅一起核对。',
    ],
  },
  {
    title: '旧房翻新，这些施工顺序别搞反',
    author: '匠心施工队',
    type: 'contractor',
    summary: '先水电再墙地面，最后定制柜与软装进场。',
    tags: ['旧房翻新', '施工顺序', '装修经验'],
    body: [
      '旧房翻新第一步不是拆，而是确认哪些结构能动、哪些管线必须保留。拆除前把燃气、水电和公共管道位置标清楚。',
      '标准顺序通常是拆除、结构处理、水电、泥木、油漆、安装和软装。门窗、空调和定制柜需要更早完成复尺与下单。',
      '每个隐蔽工程节点都要拍照留档，尤其是水电走向和防水闭水测试，后期安装与维修都会用到。',
    ],
  },
  {
    title: '奶油风卧室配色，照着抄就行',
    author: '奶油风收纳研究所',
    type: 'designer',
    summary: '浅色搭配更显大，家具选择也要尽量轻量。',
    tags: ['奶油风', '卧室', '配色'],
    body: [
      '奶油风的关键不是全屋刷成米白，而是让墙面、柜体和布艺保持低对比度，再用木色或焦糖色做少量强调。',
      '墙面可以选偏暖的低饱和颜色，床和窗帘尽量避免过冷的灰。材质上混合棉麻、绒面和哑光木纹会更有层次。',
      '小卧室不要堆太多弧形家具，一个圆角床头柜或一盏柔和壁灯就足够建立氛围。',
    ],
  },
  {
    title: '卫生间干湿分离，小空间也能做',
    author: '极简家装指南',
    type: 'contractor',
    summary: '提前预留水电点位，后期使用会方便很多。',
    tags: ['卫生间', '干湿分离', '小空间'],
    body: [
      '面积有限时，可以用玻璃隔断、浴帘或半墙完成轻量分区。先保证马桶与淋浴的使用尺寸，再考虑造型。',
      '地漏要位于最低点，淋浴区坡度与门槛止水要在贴砖前确认。玻璃门开启方向不能撞到马桶、龙头或毛巾架。',
      '镜柜、壁龛和台盆柜可以承担主要收纳，但水电点位必须提前跟柜体图一起核对。',
    ],
  },
  {
    title: '阳台封窗前后对比，真的太香了',
    author: '小户型改造手记',
    type: 'contractor',
    summary: '动线顺畅比多打柜子更重要，先规划再施工。',
    tags: ['阳台改造', '封窗', '空间利用'],
    body: [
      '封窗之前先确定阳台最终用途：洗衣、休闲还是并入客厅。不同用途决定保温、防水、插座和排水的做法。',
      '窗框型材、玻璃配置和开启扇数量要结合楼层、风压与朝向选择，不要只比较单价。高层还要确认物业和当地规范。',
      '如果并入室内，要重点处理原门垛、地面高差与空调负荷，避免视觉上连通了，体感却不舒适。',
    ],
  },
  {
    title: '客厅不放电视柜，收纳反而更多',
    author: '原木生活家',
    type: 'designer',
    summary: '颜色不要超过三种，整体会更耐看。',
    tags: ['客厅收纳', '电视墙', '空间规划'],
    body: [
      '取消成品电视柜后，可以把收纳整合进一整面薄柜，视觉更统一，也能减少卫生死角。',
      '常用物品放在腰部高度，低频物品放高处；开放格只保留少量展示，否则很容易重新变乱。',
      '电视、音响、路由器和游戏机的散热与走线要提前规划，柜门内建议预留通风孔和检修空间。',
    ],
  },
  {
    title: '无主灯设计避坑指南',
    author: '设计师林岚',
    type: 'designer',
    summary: '光束角、离墙距离和防眩结构要一起考虑。',
    tags: ['无主灯', '照明设计', '避坑'],
    body: [
      '无主灯不等于满天筒灯。先按沙发、餐桌、柜体和过道划分照明任务，再决定灯具类型与数量。',
      '经常活动的区域要重视防眩，洗墙灯要根据层高和离墙距离选光束角。只照地面、不照立面的空间会显得压抑。',
      '调光系统能提升体验，但要确认驱动、电源和面板协议兼容，施工前最好做一个样板回路。',
    ],
  },
  {
    title: '开放式厨房到底适不适合你？',
    author: '入住一年的小鹿',
    type: 'designer',
    summary: '做饭频率、燃气规范和收纳习惯比颜值更重要。',
    tags: ['开放式厨房', '厨房布局', '生活方式'],
    body: [
      '开放式厨房适合重视互动、轻油烟或空间采光不足的家庭，但必须先确认当地燃气与消防要求。',
      '高频爆炒家庭要认真评估油烟机风量、补风和清洁成本，也可以考虑玻璃移门做可开可合的方案。',
      '台面上的小家电会直接影响整洁度，设计阶段要给咖啡机、电饭煲和净水设备安排固定位置。',
    ],
  },
  {
    title: '玄关柜这样设计，回家不再乱',
    author: '木木家的装修笔记',
    type: 'furniture',
    summary: '换鞋、挂衣、放包和临时置物要各有位置。',
    tags: ['玄关', '收纳设计', '柜体'],
    body: [
      '玄关柜要从回家动作出发：开门后先放钥匙和包，再换鞋、挂外套，常用区域应集中在顺手的一侧。',
      '底部悬空适合放当天穿的鞋，中部留开放格，柜内结合抽屉、挂衣区和可调层板，比整齐等分更实用。',
      '柜体深度不足时可以斜放鞋或做超薄翻斗柜，但要给扫地机器人和插座留位置。',
    ],
  },
  {
    title: '儿童房家具怎么选更安全？',
    author: '奶油风收纳研究所',
    type: 'furniture',
    summary: '稳定、防夹和可成长，比一次性做满更重要。',
    tags: ['儿童房', '家具安全', '成长空间'],
    body: [
      '高柜和书架必须可靠固定到墙体，抽屉要有防脱落结构，活动家具尽量选择圆角和稳定底座。',
      '孩子成长很快，桌椅高度、收纳位置和活动区域最好可以调整。先留出自由空间，比把房间一次做满更耐用。',
      '选材时关注检测报告与涂层耐久度，入住前保持充分通风，软装也要定期清洁。',
    ],
  },
  {
    title: '意式极简沙发的搭配思路',
    author: '极简家装指南',
    type: 'furniture',
    summary: '用材质和比例建立高级感，不需要堆装饰。',
    tags: ['意式极简', '沙发搭配', '客厅'],
    body: [
      '意式极简强调低重心和清晰比例，沙发可以选深灰、暖棕或低饱和米色，再搭配体量轻的茶几。',
      '同一空间里保留一到两种主材质即可，例如皮革搭配木材，或布艺搭配石材，避免每件家具都抢视觉中心。',
      '地毯尺寸要覆盖沙发前脚和主要座位区，灯具与艺术品用来补充纵向层次。',
    ],
  },
  {
    title: '窗帘颜色选错，整个家都暗了',
    author: '原木生活家',
    type: 'designer',
    summary: '先看墙面和采光，再决定窗帘的明度与冷暖。',
    tags: ['窗帘', '软装配色', '采光'],
    body: [
      '窗帘占据大面积立面，颜色最好跟墙面保持同一冷暖方向，明度可以略深一档，空间会更有层次。',
      '北向或采光弱的房间避免大面积冷灰和深色；西晒强的空间可以使用遮光性能更好的面料，并搭配纱帘柔化光线。',
      '下单前把面料样品带回家，分别在白天和开灯后观察，现场效果通常比门店灯光更可信。',
    ],
  },
  {
    title: '小书房也能拥有双人办公位',
    author: '小户型改造手记',
    type: 'designer',
    summary: '连续桌面配合垂直收纳，小空间也能保持舒适。',
    tags: ['书房', '双人办公', '小户型'],
    body: [
      '双人位不一定要两张独立书桌，一张连续桌面更节省支撑结构，也方便共享插座与照明。',
      '每人建议预留至少 90cm 宽度和独立抽屉，显示器支架可以释放桌面。上方吊柜不要压得太低，避免坐下后有压迫感。',
      '视频会议背景、自然光方向和空调风口都要一起考虑，吸音窗帘或软包能改善两人同时工作的干扰。',
    ],
  },
]

const commentSeeds = [
  ['这个尺寸建议很实用，准备照着量一遍。', '收藏了，等定方案时再回来复习。'],
  ['终于有人把重点讲清楚了。', '想看更多真实落地前后对比。'],
  ['正好卡在这个选择上，感谢分享。', '施工节点提醒太及时了。'],
]

export const communityPosts = seeds.map((seed, index) => ({
  id: String(index + 1),
  ...seed,
  cover: covers[index],
  coverRatio: ['4 / 5', '1 / 1', '3 / 4'][index % 3],
  likes: 128 + index * 37,
  favorites: 46 + index * 19,
  publishedAt: `${index + 2} 天前`,
  comments: commentSeeds[index % commentSeeds.length].map((content, commentIndex) => ({
    id: `${index + 1}-${commentIndex + 1}`,
    author: ['阿禾的家', '改造中的乐乐'][commentIndex],
    content,
    likes: 6 + index + commentIndex * 3,
  })),
}))

export function getCommunityPost(id) {
  return communityPosts.find((post) => post.id === String(id)) || null
}
