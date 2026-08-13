// 后端下发的中文枚举/展示文案 → 英文显示映射。
// 提交给后端的值始终保持中文原值，这里只影响界面展示。
const TERMS = {
  // 空间
  客厅: 'Living room',
  主卧: 'Master bedroom',
  次卧: 'Second bedroom',
  厨房: 'Kitchen',
  卫生间: 'Bathroom',
  书房: 'Study',
  餐厅: 'Dining room',
  // 风格
  现代简约: 'Modern minimalist',
  现代轻奢: 'Modern luxe',
  意式极简: 'Italian minimalist',
  北欧: 'Nordic',
  中式: 'Chinese',
  日式: 'Japanese',
  // 预算档
  经济: 'Economy',
  品质: 'Quality',
  高端: 'Premium',
  // 项目状态
  建档中: 'Drafting',
  识别完成: 'Recognized',
  需求澄清: 'Requirements',
  方案生成: 'Schemes ready',
  已留资: 'Lead captured',
  已签约: 'Signed',
  // 生成任务状态
  待生成: 'Pending',
  生成中: 'Running',
  成功: 'Success',
  失败: 'Failed',
  // 家具品类
  沙发: 'Sofa',
  床: 'Bed',
  桌椅: 'Table & chairs',
  柜类: 'Cabinet',
  灯具: 'Lighting',
  家电: 'Appliance',
  建材: 'Building material',
  软装: 'Soft furnishing',
  // 模块分组
  灯光氛围: 'Lighting mood',
  材质质感: 'Material texture',
  镜头视角: 'Camera angle',
  色彩基调: 'Color tone',
  布局收纳: 'Layout & storage',
  情绪风格: 'Mood & style',
  画质控制: 'Image quality',
  其他选项: 'Other options',
}

/** 在英文界面下把后端中文术语转为英文；未收录则原样返回。 */
export function translateTerm(value, locale) {
  if (value == null || value === '') return value
  if (locale !== 'en-US') return value
  return TERMS[String(value).trim()] || value
}
