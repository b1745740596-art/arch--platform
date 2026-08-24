"""Lightweight keyword/tag retrieval with structured-data augmentation."""

from __future__ import annotations

import re

from design.models import ServiceProvider
from payments.models import PricingPlan

from .models import KnowledgeDocument


def _terms(text: str) -> set[str]:
    text = (text or '').lower()
    chunks = set(re.findall(r'[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}', text))
    chinese = ''.join(re.findall(r'[\u4e00-\u9fff]', text))
    chunks.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return {item for item in chunks if item}


def retrieve(query: str, profile=None, limit: int = 3) -> list[dict]:
    query_terms = _terms(query)
    if profile:
        query_terms.update(_terms(' '.join([
            profile.city or '', profile.style or '', ' '.join(profile.pain_points or []),
        ])))

    scored = []
    documents = KnowledgeDocument.objects.select_related('base').filter(
        is_active=True,
        base__is_active=True,
    )
    for document in documents:
        haystack = ' '.join([
            document.title, document.content, document.base.category,
            ' '.join(str(tag) for tag in (document.tags or [])),
        ])
        overlap = len(query_terms & _terms(haystack))
        if overlap > 0:
            score = overlap * 10 + max(0, 100 - document.priority) / 10
            scored.append((score, {
                'source': document.base.get_category_display(),
                'title': document.title,
                'content': document.content[:800],
            }))

    results = [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:limit]]

    if any(term in query for term in ('价格', '报价', '预算', '套餐', '多少钱', '费用', '花费')):
        for pricing in PricingPlan.objects.filter(is_active=True).order_by('sort_order', 'price_cents')[:3]:
            results.append({
                'source': '平台套餐',
                'title': pricing.name,
                'content': f'{pricing.name}：¥{pricing.price}，包含 {pricing.credits} 次生成额度。',
            })

    if profile and profile.city and len(results) < limit:
        provider = ServiceProvider.objects.filter(is_active=True, city=profile.city).order_by('-rating').first()
        if provider:
            results.append({
                'source': '服务商资料',
                'title': provider.name,
                'content': f'{provider.name}，评分 {provider.rating}分，报价参考：{provider.quote_range or "需量房确认"}。',
            })
    return results[: max(limit, 1)]
