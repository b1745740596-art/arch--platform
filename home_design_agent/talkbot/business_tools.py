"""Read-only business tools exposed to TalkBot as structured message cards."""

from __future__ import annotations

from urllib.parse import urlparse

from django.db.models import Q

from design.models import (
    Designer,
    DesignScheme,
    Furniture,
    HomeOrder,
    RenderJob,
    ServiceProvider,
)

from . import strategy
from .models import Conversation


RESULT_LIMIT = 4

PRODUCT_TERMS = (
    '家具', '建材', '家电', '软装', '商品', '产品', '沙发', '床', '桌', '椅',
    '柜', '灯', '瓷砖', '地板', '板材', '涂料', '窗帘',
)
PROVIDER_TERMS = (
    '商户', '商家', '服务商', '施工队', '装修公司', '供应商', '材料商', '设计团队',
)
DESIGNER_TERMS = ('设计师', '设计顾问')
RENDER_TERMS = ('效果图', '生图', '渲染图', '设计图', '空间图', '意向图')
OWN_RENDER_TERMS = ('我的效果图', '我生成的效果图', '我的生图', '我的渲染图', '我的设计图')
SCHEME_TERMS = ('设计方案', '装修方案', '预方案', '我的方案', '方案推荐', '看看方案')
ORDER_LIST_TERMS = ('我的订单', '查看订单', '订单状态', '订单进度', '订单号', '已下单')
ORDER_CREATE_TERMS = ('帮我下单', '我要下单', '立即下单', '确认下单', '创建订单', '生成订单', '生成方案订单')
CAPABILITY_TERMS = ('你能做什么', '有哪些功能', '可以帮我什么', '全部服务', '功能介绍')

CATEGORY_TERMS = (
    (Furniture.Category.SOFA, ('沙发',)),
    (Furniture.Category.BED, ('床', '床垫')),
    (Furniture.Category.TABLE, ('桌', '椅', '餐桌', '茶几')),
    (Furniture.Category.CABINET, ('柜', '衣柜', '橱柜', '收纳')),
    (Furniture.Category.LIGHT, ('灯', '照明')),
    (Furniture.Category.APPLIANCE, ('家电', '电器')),
    (Furniture.Category.MATERIAL, ('建材', '瓷砖', '地板', '板材', '涂料')),
    (Furniture.Category.DECOR, ('软装', '窗帘', '摆件', '地毯')),
)


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _safe_url(value: str | None, *, allow_relative: bool = False) -> str:
    value = (value or '').strip()
    if allow_relative and value.startswith('/media/'):
        return value
    parsed = urlparse(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


def _file_url(field) -> str:
    if not field or not getattr(field, 'name', ''):
        return ''
    try:
        return _safe_url(field.url, allow_relative=True)
    except ValueError:
        return ''


def _card(kind: str, title: str, items: list[dict], **extra) -> dict:
    return {
        'schema_version': 1,
        'kind': kind,
        'title': title,
        'items': items[:RESULT_LIMIT],
        **extra,
    }


def _product_card(profile, text: str) -> dict:
    category = None
    if not ('家具' in text and '建材' in text):
        category = next((value for value, terms in CATEGORY_TERMS if _contains(text, terms)), None)

    base = Furniture.objects.filter(is_active=True)
    if category:
        base = base.filter(category=category)
    filtered = base
    if profile.style:
        filtered = filtered.filter(style__icontains=profile.style)
    products = list(filtered[:RESULT_LIMIT])
    if not products and profile.style:
        products = list(base[:RESULT_LIMIT])

    items = []
    for product in products:
        subtitle = ' · '.join(filter(None, (product.get_category_display(), product.brand)))
        badges = [value for value in (product.style, *(product.rooms or [])[:2]) if value]
        items.append({
            'id': product.id,
            'entity': 'furniture',
            'title': product.name,
            'subtitle': subtitle,
            'description': product.spec or product.supplier,
            'price': product.price,
            'image_url': _file_url(product.image),
            'href': _safe_url(product.buy_url),
            'badges': badges,
        })
    return _card(
        'products',
        '家具建材推荐',
        items,
        empty_message='当前商品库没有匹配项，可进入生图设计后按空间重新匹配。',
        action={'type': 'navigate', 'path': '/render'},
    )


def _provider_card(profile, text: str) -> dict:
    kind = None
    if any(term in text for term in ('施工队', '装修公司')):
        kind = ServiceProvider.Kind.CONSTRUCTION
    elif any(term in text for term in ('供应商', '材料商')):
        kind = ServiceProvider.Kind.SUPPLIER
    elif '设计团队' in text:
        kind = ServiceProvider.Kind.DESIGN

    base = ServiceProvider.objects.filter(is_active=True)
    if kind:
        base = base.filter(kind=kind)
    filtered = base.filter(city=profile.city) if profile.city else base
    providers = list(filtered[:RESULT_LIMIT])
    if not providers and profile.city:
        providers = list(base[:RESULT_LIMIT])

    items = [{
        'id': provider.id,
        'entity': 'provider',
        'title': provider.name,
        'subtitle': ' · '.join(filter(None, (provider.get_kind_display(), provider.city))),
        'description': provider.qualification or provider.response_speed,
        'rating': str(provider.rating),
        'price_text': provider.quote_range,
        'badges': [value for value in (provider.response_speed,) if value],
    } for provider in providers]
    return _card(
        'providers',
        '商户与服务商',
        items,
        empty_message='当前商户库没有匹配项，完善城市后可获得更准确的推荐。',
    )


def _designer_card(profile) -> dict:
    base = Designer.objects.filter(is_active=True)
    filtered = base.filter(city=profile.city) if profile.city else base
    designers = list(filtered[:RESULT_LIMIT])
    if not designers and profile.city:
        designers = list(base[:RESULT_LIMIT])
    if profile.style:
        designers.sort(key=lambda item: profile.style not in (item.styles or []))

    items = [{
        'id': designer.id,
        'entity': 'designer',
        'title': designer.name,
        'subtitle': ' · '.join(filter(None, (designer.title, designer.city))),
        'description': designer.intro[:120],
        'rating': str(designer.rating),
        'image_url': _file_url(designer.avatar),
        'badges': [f'{designer.years}年经验', *(designer.styles or [])[:2]],
    } for designer in designers]
    return _card('designers', '设计师推荐', items, empty_message='当前没有匹配的设计师。')


def _render_card(conversation, *, style: str = '', own_only: bool = False) -> dict:
    """Return successful renders from the public library, optionally by style.

    Render results are shared catalogue assets. Raw photos and project details
    remain private; public cards expose only the finished image and its style.
    """
    jobs = RenderJob.objects.filter(status=RenderJob.Status.SUCCESS).filter(
        Q(result_image__isnull=False) & ~Q(result_image='')
        | ~Q(result_image_url=''),
    )
    if own_only:
        jobs = jobs.filter(project__user=conversation.user)
    normalized_style = (style or '').strip().removesuffix('风格').removesuffix('风')
    if normalized_style:
        jobs = jobs.filter(style__icontains=normalized_style)
    jobs = jobs.select_related('project', 'project__user').order_by('-created_at')[:RESULT_LIMIT]

    items = []
    for job in jobs:
        image_url = _file_url(job.result_image) or _safe_url(job.result_image_url)
        if not image_url:
            continue
        is_owner = job.project.user_id == conversation.user_id
        items.append({
            'id': job.id,
            'entity': 'render',
            'title': ' · '.join(filter(None, (job.room_type, job.style))) or f'效果图 #{job.id}',
            'subtitle': job.project.title if is_owner else '平台公开效果图库',
            'description': (
                job.design_note[:120]
                if is_owner
                else '平台公开效果图，可作为装修风格参考。'
            ),
            'image_url': image_url,
            'status': job.get_status_display(),
            'badges': [value for value in (job.style, job.room_type) if value],
        })
    title = f'{style}风格效果图' if style else ('我的效果图' if own_only else 'AI 效果图库')
    return _card(
        'renders',
        title,
        items,
        empty_message=(
            f'效果图库暂时没有匹配“{style}”的图片，可以上传房屋照片生成专属效果图。'
            if style
            else '还没有可展示的效果图，上传一张房屋照片即可开始生成。'
        ),
        action={'type': 'navigate', 'path': '/render'},
    )


def _scheme_card(conversation) -> dict:
    schemes = (
        DesignScheme.objects.filter(project__user=conversation.user)
        .select_related('project')
        .order_by('-created_at')[:RESULT_LIMIT]
    )
    items = [{
        'id': scheme.id,
        'entity': 'scheme',
        'title': scheme.name,
        'subtitle': ' · '.join(filter(None, (scheme.style, scheme.get_budget_tier_display()))),
        'description': '；'.join((scheme.highlights or [])[:2]),
        'price_min': scheme.budget_min,
        'price_max': scheme.budget_max,
        'image_url': _file_url(scheme.cover_image),
        'path': f'/projects/{scheme.project_id}',
        'badges': ['已收藏'] if scheme.is_favorited else [],
    } for scheme in schemes]
    return _card(
        'schemes',
        '装修设计方案',
        items,
        empty_message='当前还没有方案，完成需求画像后可由机器人生成三档预方案。',
        action={'type': 'navigate', 'path': '/projects'},
    )


def _order_items(conversation) -> list[dict]:
    orders = (
        HomeOrder.objects.filter(user=conversation.user)
        .select_related('project')
        .order_by('-created_at')[:RESULT_LIMIT]
    )
    return [{
        'id': order.id,
        'entity': 'order',
        'title': order.title or order.project.title,
        'subtitle': order.order_no,
        'status': order.get_status_display(),
        'price': order.total_amount,
        'price_min': order.amount_min,
        'price_max': order.amount_max,
        'path': '/my-home?tab=orders',
    } for order in orders]


def order_list_card(conversation) -> dict:
    return _card(
        'orders',
        '项目订单',
        _order_items(conversation),
        empty_message='当前还没有项目订单。',
        action={'type': 'navigate', 'path': '/my-home?tab=orders'},
    )


def order_action_card(conversation, profile) -> dict:
    if conversation.order_id:
        return order_list_card(conversation)
    missing = strategy.conversion_missing(profile)
    return _card(
        'order_action',
        '机器人下单',
        [],
        ready=not missing and conversation.status == Conversation.Status.ACTIVE,
        missing=[strategy.FIELD_LABELS.get(field, field) for field in missing],
        empty_message=(
            '订单资料已齐，请确认后生成三档预方案和待确认订单；此操作不会自动扣款。'
            if not missing
            else '下单前还需要补充：' + '、'.join(
                strategy.FIELD_LABELS.get(field, field) for field in missing
            )
        ),
        action=(
            {'type': 'convert'}
            if not missing and conversation.status == Conversation.Status.ACTIVE
            else None
        ),
    )


def completed_order_card(order: HomeOrder) -> dict:
    return _card(
        'orders',
        '项目订单已创建',
        [{
            'id': order.id,
            'entity': 'order',
            'title': order.title or order.project.title,
            'subtitle': order.order_no,
            'status': order.get_status_display(),
            'price': order.total_amount,
            'price_min': order.amount_min,
            'price_max': order.amount_max,
            'path': '/my-home?tab=orders',
        }],
        action={'type': 'navigate', 'path': '/my-home?tab=orders'},
    )


def _capability_card() -> dict:
    return _card('capabilities', '我可以直接调用这些服务', [{
        'id': 'render', 'entity': 'capability', 'title': 'AI 生图设计',
        'description': '查看已有效果图或上传房屋照片开始生成。', 'path': '/render',
    }, {
        'id': 'products', 'entity': 'capability', 'title': '家具建材',
        'description': '按风格、空间和品类匹配商品与购买链接。',
    }, {
        'id': 'providers', 'entity': 'capability', 'title': '商户与服务商',
        'description': '按城市展示施工队、设计团队和供应商。',
    }, {
        'id': 'orders', 'entity': 'capability', 'title': '项目方案与下单',
        'description': '查看方案和订单，资料齐全后确认创建待确认订单。',
        'path': '/my-home?tab=orders',
    }])


def collect_tool_results(
    conversation,
    profile,
    text: str,
    *,
    style_mentioned: bool = False,
) -> list[dict]:
    """Select business tools from explicit requests and newly mentioned styles."""
    text = (text or '').strip()
    results = []
    if _contains(text, CAPABILITY_TERMS):
        results.append(_capability_card())
    if style_mentioned and profile.style:
        results.append(_render_card(conversation, style=profile.style))
    elif _contains(text, RENDER_TERMS):
        results.append(_render_card(
            conversation,
            style=profile.style if profile.style and not _contains(text, OWN_RENDER_TERMS) else '',
            own_only=_contains(text, OWN_RENDER_TERMS),
        ))
    if _contains(text, PRODUCT_TERMS):
        results.append(_product_card(profile, text))
    if _contains(text, PROVIDER_TERMS):
        results.append(_provider_card(profile, text))
    if _contains(text, DESIGNER_TERMS):
        results.append(_designer_card(profile))
    if _contains(text, SCHEME_TERMS):
        results.append(_scheme_card(conversation))
    if _contains(text, ORDER_LIST_TERMS):
        results.append(order_list_card(conversation))
    elif _contains(text, ORDER_CREATE_TERMS):
        results.append(order_action_card(conversation, profile))
    return results


def tool_result_intro(results: list[dict]) -> str:
    if not results:
        return ''
    order_action = next((item for item in results if item.get('kind') == 'order_action'), None)
    if order_action:
        if order_action.get('ready'):
            return '订单资料已经准备好，请在下方卡片中确认；确认前不会创建订单，也不会扣款。'
        return order_action.get('empty_message', '')
    titles = list(dict.fromkeys(item.get('title', '') for item in results if item.get('title')))
    return f'我已为你调用并展示：{"、".join(titles)}。'
