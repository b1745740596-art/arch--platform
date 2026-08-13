"""方案生成服务（PRD 5.3）。

当前实现为规则生成：按经济/品质/高端三档，结合项目面积与预算，
产出 ≥3 套结构化预方案。后续可替换为 LLM 生成，接口保持不变。
"""
from __future__ import annotations

from .models import DesignScheme, Project


_STYLE_PRESETS = [
    {
        'tier': DesignScheme.BudgetTier.ECONOMY,
        'name': '简约实用方案',
        'style': '现代简约',
        'unit_low': 900, 'unit_high': 1300,
        'highlights': ['高性价比主材', '开放式布局提升采光', '标准化收纳'],
        'risks': ['软装预算有限', '个性化定制项较少'],
        'suitable_for': '预算敏感的首次装修家庭',
        'layout': '客餐一体化，减少非承重隔断，主卧保留独立衣帽区。',
    },
    {
        'tier': DesignScheme.BudgetTier.QUALITY,
        'name': '品质舒适方案',
        'style': '现代轻奢',
        'unit_low': 1500, 'unit_high': 2200,
        'highlights': ['中高端主材与家电', '全屋定制收纳', '分区照明设计'],
        'risks': ['工期相对更长', '定制件交付周期需预留'],
        'suitable_for': '重视居住品质的三口之家',
        'layout': '功能分区清晰，增加中西厨/餐边柜，主卧套房化。',
    },
    {
        'tier': DesignScheme.BudgetTier.PREMIUM,
        'name': '高端定制方案',
        'style': '意式极简',
        'unit_low': 2600, 'unit_high': 4000,
        'highlights': ['进口主材与智能家居', '全屋定制+软装整装', '新风/中央空调'],
        'risks': ['预算较高', '需专业深化设计与项目管理'],
        'suitable_for': '追求品质与设计感的改善型家庭',
        'layout': '强调空间仪式感，客厅挑高感设计，主卧含独立衣帽间与卫浴。',
    },
]


def build_preview_schemes(project: Project) -> list[DesignScheme]:
    """基于项目生成 3 套预方案并落库，返回创建的对象列表。"""
    area = float(project.area) if project.area else 90.0
    schemes = []
    for preset in _STYLE_PRESETS:
        budget_min = int(area * preset['unit_low'])
        budget_max = int(area * preset['unit_high'])
        scheme = DesignScheme.objects.create(
            project=project,
            name=preset['name'],
            style=preset['style'],
            budget_tier=preset['tier'],
            layout=preset['layout'],
            highlights=preset['highlights'],
            risks=preset['risks'],
            suitable_for=preset['suitable_for'],
            budget_min=budget_min,
            budget_max=budget_max,
            assumptions=(
                f'按建筑面积 {area:.0f}㎡ 估算，单价区间 '
                f'{preset["unit_low"]}–{preset["unit_high"]} 元/㎡（含硬装，软装家电另计）。'
                '效果与最终落地存在差异，需现场量房与可施工校验后确认。'
            ),
        )
        schemes.append(scheme)
    return schemes
