"""Prompt 控制模块：后端预设提示词，生图时按所选模块组装。

设计要点：
- 客户端只提交模块 `code`，真正的提示词文本保存在后端 `PromptModule` 中，
  避免把提示词工程暴露给前端，也方便运营在 admin 里调优；
- 组装结果同时产出正向 prompt、负向 prompt 与设计说明补充要求；
- 提供「发散选项」建议：按空间/风格/预算组合出若干套模块组合，
  供前端一键套用或分别开窗并行生成。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import PromptModule

# 前端可选枚举（严格约束的唯一来源）
ROOM_TYPES = ['客厅', '主卧', '次卧', '衣帽间', '厨房', '卫生间', '书房', '餐厅']
STYLES = ['现代简约', '现代轻奢', '意式极简', '北欧', '中式', '日式']
BUDGET_TIERS = ['经济', '品质', '高端']

# 空间 → 允许出现的家具品类。家具库没有空间字段，用品类做约束，
# 避免「客厅里摆床」这类图生图后特别刺眼的错配。
# 建材/灯具/软装为通用品类，任何空间都可出现。
ROOM_CATEGORIES = {
    '客厅': ['sofa', 'table', 'cabinet', 'appliance'],
    '主卧': ['bed', 'cabinet', 'table'],
    '次卧': ['bed', 'cabinet', 'table'],
    '衣帽间': ['cabinet', 'table'],
    '厨房': ['cabinet', 'appliance', 'table'],
    '卫生间': ['cabinet', 'appliance'],
    '书房': ['table', 'cabinet', 'sofa'],
    '餐厅': ['table', 'cabinet', 'appliance'],
}
ROOM_NEUTRAL_CATEGORIES = ['light', 'material', 'decor']


def room_categories(room_type: str) -> list:
    """该空间可用的家具品类；未知空间返回空列表表示不过滤。"""
    specific = ROOM_CATEGORIES.get(room_type or '')
    if not specific:
        return []
    return specific + ROOM_NEUTRAL_CATEGORIES

# 输入约束（与前端校验共用同一份口径）
REQUIREMENT_MAX_LENGTH = 300
MAX_MODULES = 6
VARIANT_MAX = 4
IMAGE_CONSTRAINTS = {
    'max_bytes': 10 * 1024 * 1024,
    'min_bytes': 10 * 1024,
    'allowed_types': ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'],
    'min_side': 512,
    'max_side': 8000,
    'max_aspect_ratio': 3.0,
}

# 分组的选择规则：是否多选、最多选几个
GROUP_RULES = {
    PromptModule.Group.LIGHTING: {'multiple': True, 'max_select': 2},
    PromptModule.Group.MATERIAL: {'multiple': True, 'max_select': 2},
    PromptModule.Group.CAMERA: {'multiple': False, 'max_select': 1},
    PromptModule.Group.COLOR: {'multiple': False, 'max_select': 1},
    PromptModule.Group.LAYOUT: {'multiple': True, 'max_select': 2},
    PromptModule.Group.MOOD: {'multiple': True, 'max_select': 2},
    PromptModule.Group.QUALITY: {'multiple': True, 'max_select': 2},
}

# 发散建议：每套方案的定位与偏好分组，取值时按分组挑选可用模块
VARIANT_RECIPES = [
    {
        'key': 'ambience',
        'title': '氛围优先',
        'summary': '强调灯光层次与情绪感，适合看重「住进去的感觉」。',
        'groups': [PromptModule.Group.LIGHTING, PromptModule.Group.MOOD,
                   PromptModule.Group.COLOR],
    },
    {
        'key': 'material',
        'title': '质感优先',
        'summary': '突出材质与工艺细节，适合关注用料与耐看度。',
        'groups': [PromptModule.Group.MATERIAL, PromptModule.Group.QUALITY,
                   PromptModule.Group.COLOR],
    },
    {
        'key': 'space',
        'title': '空间效率优先',
        'summary': '放大空间感与收纳能力，适合小户型与实用主义。',
        'groups': [PromptModule.Group.LAYOUT, PromptModule.Group.CAMERA,
                   PromptModule.Group.LIGHTING],
    },
    {
        'key': 'showcase',
        'title': '出片优先',
        'summary': '按样板间视角构图，适合用于对比展示与决策汇报。',
        'groups': [PromptModule.Group.CAMERA, PromptModule.Group.QUALITY,
                   PromptModule.Group.MOOD],
    },
]


@dataclass
class PromptBundle:
    """一次生图所需的全部提示词材料。"""

    positive: str = ''
    negative: str = ''
    note_extra: str = ''
    modules: list = field(default_factory=list)


def parse_module_codes(raw) -> list[str]:
    """解析前端提交的 module_codes，兼容逗号串与数组两种形态。"""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        items = []
        for chunk in raw:
            items.extend(str(chunk).split(','))
    else:
        items = str(raw).split(',')
    codes = []
    for item in items:
        code = item.strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def resolve_modules(codes, room_type: str = '', style: str = '') -> list[PromptModule]:
    """把 code 列表解析为模块对象；为空时回退到默认模块。

    只接受启用且适配当前空间/风格的模块，未知 code 直接忽略，
    保证前端传什么都不会污染 prompt。
    """
    qs = PromptModule.objects.filter(is_active=True)
    codes = parse_module_codes(codes)
    if codes:
        found = {m.code: m for m in qs.filter(code__in=codes)}
        picked = [found[c] for c in codes if c in found]
        picked = [m for m in picked if m.matches(room_type, style)]
        if picked:
            return picked[:MAX_MODULES]
    defaults = [m for m in qs.filter(is_default=True) if m.matches(room_type, style)]
    return defaults[:MAX_MODULES]


def build_prompt_bundle(job, modules=None, furniture_clause: str = '') -> PromptBundle:
    """按控制模块组装图像 prompt（正向 / 负向 / 设计说明补充）。"""
    modules = list(modules or [])
    modules.sort(key=lambda m: (m.weight, m.pk or 0))

    parts = [
        f'{job.style or "modern minimalist"} style {job.room_type or "living room"} interior design',
        'photorealistic interior rendering of the same room from the uploaded photo',
    ]
    for module in modules:
        fragment = (module.prompt_fragment or '').strip()
        if fragment:
            parts.append(fragment)
    if job.requirement:
        parts.append(job.requirement)
    if job.budget_tier:
        parts.append(f'{job.budget_tier} budget')
    if furniture_clause:
        parts.append(furniture_clause)

    negatives = ['low quality', 'blurry', 'distorted perspective', 'watermark', 'text overlay']
    for module in modules:
        negative = (module.negative_fragment or '').strip()
        if negative:
            negatives.append(negative)

    note_bits = [m.note_fragment.strip() for m in modules if (m.note_fragment or '').strip()]

    return PromptBundle(
        positive=', '.join(p for p in parts if p),
        negative=', '.join(dict.fromkeys(negatives)),
        note_extra='；'.join(dict.fromkeys(note_bits)),
        modules=modules,
    )


def module_payload(module: PromptModule) -> dict:
    """模块对前端的公开字段（不含 prompt 文本）。"""
    return {
        'id': module.pk,
        'code': module.code,
        'name': module.name,
        'group': module.group,
        'group_display': module.get_group_display(),
        'description': module.description,
        'is_default': module.is_default,
    }


def option_payload(room_type: str = '', style: str = '') -> dict:
    """前端下拉/标签所需的全部选项与约束。"""
    modules = [
        m for m in PromptModule.objects.filter(is_active=True)
        if m.matches(room_type, style)
    ]
    used_groups = []
    for module in modules:
        if module.group not in used_groups:
            used_groups.append(module.group)
    groups = []
    for group in PromptModule.Group:
        if group.value not in used_groups:
            continue
        rule = GROUP_RULES.get(group, {'multiple': True, 'max_select': 2})
        groups.append({
            'key': group.value,
            'label': group.label,
            'multiple': rule['multiple'],
            'max_select': rule['max_select'],
        })
    return {
        'room_types': ROOM_TYPES,
        'styles': STYLES,
        'budget_tiers': BUDGET_TIERS,
        'modules': [module_payload(m) for m in modules],
        'groups': groups,
        'constraints': {
            'requirement_max_length': REQUIREMENT_MAX_LENGTH,
            'image': IMAGE_CONSTRAINTS,
            'max_modules': MAX_MODULES,
            'variant_max': VARIANT_MAX,
        },
    }


def suggest_variants(room_type: str = '', style: str = '', budget_tier: str = '') -> list[dict]:
    """发散选项：给出若干套模块组合，供一键套用或分别开窗并行生成。"""
    modules = [
        m for m in PromptModule.objects.filter(is_active=True)
        if m.matches(room_type, style)
    ]
    by_group: dict[str, list[PromptModule]] = {}
    for module in modules:
        by_group.setdefault(module.group, []).append(module)

    variants = []
    for index, recipe in enumerate(VARIANT_RECIPES):
        codes, highlights = [], []
        for group in recipe['groups']:
            candidates = by_group.get(group.value if hasattr(group, 'value') else group, [])
            if not candidates:
                continue
            # 同一分组内按索引轮换，让不同方案落在不同模块上
            module = candidates[index % len(candidates)]
            if module.code in codes:
                continue
            codes.append(module.code)
            highlights.append(f'{module.get_group_display()}：{module.name}')
        if not codes:
            continue
        summary = recipe['summary']
        if budget_tier:
            summary = f'{summary}（按「{budget_tier}」预算档呈现）'
        variants.append({
            'key': recipe['key'],
            'title': recipe['title'],
            'summary': summary,
            'module_codes': codes[:MAX_MODULES],
            'highlights': highlights,
        })
    return variants[:VARIANT_MAX]
