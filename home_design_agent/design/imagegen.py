"""效果图生成服务。

读取后台 GenerationConfig。两条链路相互独立：
- 效果图：image_enabled 时调用图像端点（默认 Pollinations，免费无 Key）。
  支持两种生图模式：文生图（只用提示词）与图生图（把上传的毛坯照片作为
  参考图一起提交，保留原始户型、门窗与视角），否则回退占位 SVG；
- 设计说明：enabled + api_key 时调用 OpenAI 兼容 chat（DeepSeek）写入
  RenderJob.design_note，否则规则文案兜底。
任一链路失败都会降级，不影响整单成功，保证链路可跑通。
"""
from __future__ import annotations

import base64
import logging
import json
import time
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile

from .models import Designer, Furniture, GenerationConfig, RenderJob, ServiceProvider
from .prompts import build_prompt_bundle, room_categories
from .dbwrite import retry_write

logger = logging.getLogger(__name__)

# MaiziAI 异步任务轮询参数。
# 图生图（带参考图）比文生图慢，多窗口并行时服务商侧还会排队，
# 单次 120s 起步，因此超时放到 300s；需与前端请求超时保持一致（见 api/client.js）。
MAIZI_POLL_INTERVAL = 3
MAIZI_POLL_TIMEOUT = 300

# 图生图参考图上限（服务商侧一般 3~9 张，这里只用上传的毛坯照片）
REFERENCE_IMAGE_LIMIT = 3
# 参考图提交前压到的最长边，控制请求体积（base64 会放大约 1/3）
REFERENCE_MAX_SIDE = 1024


def _parse_size(image_size: str) -> tuple[int, int]:
    try:
        w, h = (image_size or '1024x1024').lower().split('x')
        return int(w), int(h)
    except Exception:  # noqa: BLE001
        return 1024, 1024


def build_prompt(job: RenderJob, config: GenerationConfig, note_extra: str = '') -> str:
    """设计说明用的文本提示词；控制模块的补充要求会追加到末尾。"""
    template = config.prompt_template or ''
    prompt = template.format(
        style=job.style or '现代简约',
        room_type=job.room_type or '客厅',
        budget_tier=job.budget_tier or '品质',
        requirement=job.requirement or '整体协调、采光良好、收纳充足',
    )
    if note_extra:
        prompt = f'{prompt}\n额外控制要求：{note_extra}。'
    return prompt


def _furniture_descriptor(f: Furniture) -> str:
    """把一件家具库商品转成图像 prompt 里的一句描述。"""
    bits = [f.get_category_display(), f.name]
    if f.brand:
        bits.append(f.brand)
    if f.style:
        bits.append(f.style)
    return ' '.join(b for b in bits if b)


def _furniture_clause(furnitures=None) -> str:
    """家具库匹配结果转成 prompt 里的一句约束。"""
    if not furnitures:
        return ''
    items = '；'.join(_furniture_descriptor(f) for f in furnitures)
    return (
        f'画面中需包含以下家具：{items}，'
        'furnish the room with exactly these furniture pieces, arranged naturally'
    )


def build_image_prompt(job: RenderJob, furnitures=None, modules=None):
    """构造图像端点用的提示词，由 prompt 控制模块驱动。

    - 控制模块（灯光/材质/镜头/色彩……）由后端预设，前端只传 code；
    - 家具库匹配到的具体家具写入 prompt，做到「家具库融入渲染图」。
    返回 PromptBundle（正向 / 负向 / 设计说明补充 / 生效模块）。
    """
    return build_prompt_bundle(job, modules, _furniture_clause(furnitures))


def _placeholder_svg(job: RenderJob) -> bytes:
    text = f'{job.style or "现代简约"} · {job.room_type or "客厅"} 效果图（占位）'
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="768">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#e8eef5"/><stop offset="1" stop-color="#cfd8e3"/>'
        '</linearGradient></defs>'
        '<rect width="1024" height="768" fill="url(#g)"/>'
        f'<text x="512" y="384" font-size="34" fill="#4a5568" '
        'text-anchor="middle" font-family="sans-serif">'
        f'{text}</text>'
        '<text x="512" y="430" font-size="20" fill="#718096" '
        'text-anchor="middle" font-family="sans-serif">'
        '（未配置图像 API，启用后将生成真实效果图）</text>'
        '</svg>'
    )
    return svg.encode('utf-8')


FURNITURE_PLACEHOLDER_COLORS = {
    'sofa': ('#e6efe9', '#4a7c59'),
    'bed': ('#efe9f5', '#6b5b95'),
    'table': ('#f5efe6', '#8c6d46'),
    'cabinet': ('#eef1f5', '#4a5568'),
    'light': ('#fbf3e0', '#b8860b'),
    'appliance': ('#e9f0f5', '#2c5f7c'),
    'material': ('#f0f0ee', '#5f6368'),
    'decor': ('#f7ecec', '#a05252'),
}


def _furniture_placeholder_svg(furniture: Furniture) -> bytes:
    """家具商品图占位：品类配色 + 名称，保证前端始终有图可展示。"""
    bg, fg = FURNITURE_PLACEHOLDER_COLORS.get(furniture.category, ('#eef1f5', '#4a5568'))
    name = _xml_escape(furniture.name)
    category = _xml_escape(furniture.get_category_display())
    brand = _xml_escape(furniture.brand or '')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="450">'
        f'<rect width="600" height="450" fill="{bg}"/>'
        f'<rect x="24" y="24" width="552" height="402" fill="none" stroke="{fg}" '
        'stroke-width="2" stroke-dasharray="10 8" opacity="0.5"/>'
        f'<text x="300" y="200" font-size="30" fill="{fg}" text-anchor="middle" '
        f'font-family="sans-serif">{category}</text>'
        f'<text x="300" y="252" font-size="22" fill="{fg}" text-anchor="middle" '
        f'font-family="sans-serif" opacity="0.8">{name}</text>'
        f'<text x="300" y="296" font-size="18" fill="{fg}" text-anchor="middle" '
        f'font-family="sans-serif" opacity="0.6">{brand}</text>'
        '</svg>'
    )
    return svg.encode('utf-8')


def _xml_escape(text: str) -> str:
    return (
        text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    )


def build_furniture_image_prompt(furniture: Furniture) -> str:
    """家具商品图提示词：白底电商产品图，突出单件商品。"""
    parts = [
        f'product photo of {furniture.name}',
        furniture.get_category_display(),
    ]
    if furniture.style:
        parts.append(f'{furniture.style} style')
    if furniture.brand:
        parts.append(furniture.brand)
    parts.append(
        'e-commerce catalog shot, single item, clean white background, '
        'studio lighting, photorealistic, high detail, no text, no watermark'
    )
    return ', '.join(p for p in parts if p)


def ensure_furniture_image(furniture: Furniture, config: GenerationConfig | None = None) -> Furniture:
    """确保家具有商品图。已有图直接复用；否则生成一次并落库。

    启用真实生图时走图像端点，失败或未启用时回退占位 SVG，
    保证前端家具清单始终能展示图片。
    """
    if furniture.image:
        return furniture

    config = config or GenerationConfig.load()
    image_prompt = build_furniture_image_prompt(furniture)
    try:
        if not config.image_enabled:
            raise RuntimeError('未启用真实生图')
        provider = (config.image_provider or 'pollinations').lower()
        if provider == 'maizi':
            ext, data = 'png', _gen_image_maizi(config, image_prompt)
        elif provider == 'openai':
            ext, data = 'png', _gen_image_openai(config, image_prompt)
        else:
            ext, data = 'jpg', _gen_image_pollinations(config, image_prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning('furniture %s image fallback: %s', furniture.pk, exc)
        ext, data = 'svg', _furniture_placeholder_svg(furniture)

    retry_write(
        lambda: furniture.image.save(f'furniture_{furniture.pk}.{ext}', ContentFile(data), save=True),
        label=f'furniture#{furniture.pk}.image',
    )
    return furniture


def _call_chat_design_note(config: GenerationConfig, prompt: str) -> str:
    """调用 OpenAI 兼容 chat/completions（DeepSeek），返回设计说明文本。"""
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key, base_url=config.api_base or None)
    resp = client.chat.completions.create(
        model=config.model or 'deepseek-chat',
        messages=[
            {'role': 'system', 'content': '你是资深室内设计师，输出专业、可落地的中文装修设计建议。'},
            {'role': 'user', 'content': prompt},
        ],
        temperature=0.7,
        stream=False,
    )
    return (resp.choices[0].message.content or '').strip()


def _gen_image_pollinations(config: GenerationConfig, image_prompt: str) -> bytes:
    """Pollinations 免费文生图：GET /prompt/{prompt}，返回 JPEG 字节。"""
    width, height = _parse_size(config.image_size)
    base = (config.image_api_base or 'https://image.pollinations.ai').rstrip('/')
    encoded = urllib.parse.quote(image_prompt, safe='')
    params = {
        'width': width, 'height': height,
        'model': config.image_model or 'flux',
        'nologo': 'true', 'safe': 'true',
    }
    url = f'{base}/prompt/{encoded}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'home-design-agent/1.0'})
    with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310
        data = resp.read()
    if not data or len(data) < 512:
        raise RuntimeError('Pollinations 返回空图像')
    return data


def _http_json(url: str, api_key: str, payload: dict | None = None, timeout: int = 60) -> dict:
    """向 OpenAI 兼容端点发 JSON 请求（GET/POST），返回解析后的字典。"""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'User-Agent': 'home-design-agent/1.0',
    }
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode('utf-8'))


def _gen_image_maizi(
    config: GenerationConfig, image_prompt: str, reference_images: list | None = None,
) -> bytes:
    """MaiziAI 异步生图：提交任务 → 轮询 /v1/tasks/{id} → 下载 result_urls[0]。

    传入 reference_images 时走图生图：参考图以 data URL 放进 `images` 字段
    （该服务商接受的参考图入参），模型会沿用原始空间的户型、门窗与视角。
    """
    base = (config.image_api_base or 'https://www.maizitech.xyz/v1').rstrip('/')
    model = config.image_model or 'gpt-image-2-official'
    payload = {'model': model, 'prompt': image_prompt, 'n': 1}
    size = (config.image_size or '').strip()
    if size:
        payload['size'] = size
    if reference_images:
        payload['images'] = [_data_url(item) for item in reference_images[:REFERENCE_IMAGE_LIMIT]]

    submitted = _http_json(f'{base}/images/generations', config.image_api_key, payload)
    items = submitted.get('data') or []
    if not items:
        raise RuntimeError(f'MaiziAI 未返回任务：{submitted}')
    task_id = items[0].get('task_id')
    # 部分模型可能同步直返 url/b64
    if not task_id:
        return _download_image(items[0].get('url'))

    deadline = time.time() + MAIZI_POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(MAIZI_POLL_INTERVAL)
        task = _http_json(f'{base}/tasks/{task_id}', config.image_api_key, timeout=30)
        status = (task.get('status') or '').lower()
        if status in ('completed', 'succeeded', 'success'):
            urls = task.get('result_urls') or []
            if not urls:
                raise RuntimeError('MaiziAI 任务完成但无结果 URL')
            return _download_image(urls[0])
        if status in ('failed', 'error', 'canceled'):
            raise RuntimeError(f'MaiziAI 生成失败：{task.get("error_msg") or status}')
    raise RuntimeError(f'MaiziAI 生成超时（{MAIZI_POLL_TIMEOUT}s），task={task_id}')


def _download_image(url: str | None) -> bytes:
    if not url:
        raise RuntimeError('图像 URL 为空')
    req = urllib.request.Request(url, headers={'User-Agent': 'home-design-agent/1.0'})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        data = resp.read()
    if not data or len(data) < 512:
        raise RuntimeError('下载到的图像为空')
    return data


def _shrink_reference(data: bytes, max_side: int = REFERENCE_MAX_SIDE) -> tuple[bytes, str]:
    """把参考图压到合适尺寸再提交，返回 (字节, mime)。失败则原样返回。"""
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            out = img.convert('RGB')
            if max(out.size) > max_side:
                scale = max_side / max(out.size)
                out = out.resize(
                    (max(1, int(out.size[0] * scale)), max(1, int(out.size[1] * scale))),
                    getattr(Image, 'LANCZOS', Image.BICUBIC),
                )
            buf = io.BytesIO()
            out.save(buf, 'JPEG', quality=88)
            return buf.getvalue(), 'image/jpeg'
    except Exception as exc:  # noqa: BLE001
        logger.warning('reference image shrink failed, send as-is: %s', exc)
        return data, 'image/png'


def _data_url(data: bytes) -> str:
    """参考图转 data URL，供 OpenAI 兼容 JSON 端点传图。"""
    payload, mime = _shrink_reference(data)
    return f'data:{mime};base64,' + base64.b64encode(payload).decode('ascii')


def _gen_image_openai(
    config: GenerationConfig, image_prompt: str, reference_images: list | None = None,
) -> bytes:
    """OpenAI 兼容 images.generate / images.edit，返回 PNG 字节。

    有参考图时走 images.edit（官方图生图端点），无参考图时走 images.generate。
    """
    import io

    from openai import OpenAI

    client = OpenAI(api_key=config.image_api_key, base_url=(config.image_api_base or None))
    if reference_images:
        files = []
        for index, item in enumerate(reference_images[:REFERENCE_IMAGE_LIMIT]):
            payload, _mime = _shrink_reference(item)
            buf = io.BytesIO(payload)
            buf.name = f'reference_{index}.jpg'
            files.append(buf)
        resp = client.images.edit(
            model=config.image_model or 'gpt-image-1',
            image=files if len(files) > 1 else files[0],
            prompt=image_prompt,
            size=config.image_size or '1024x1024',
            n=1,
        )
        return base64.b64decode(resp.data[0].b64_json)
    resp = client.images.generate(
        model=config.image_model or 'gpt-image-1',
        prompt=image_prompt,
        size=config.image_size or '1024x1024',
        n=1,
    )
    b64 = resp.data[0].b64_json
    return base64.b64decode(b64)


def _generate_image(
    config: GenerationConfig, image_prompt: str, reference_images: list | None = None,
) -> tuple[str, bytes]:
    """按配置生成效果图，返回 (扩展名, 字节)。失败抛异常由上层降级。

    reference_images 非空时走图生图（把上传照片作为参考图一起提交）；
    Pollinations 不支持参考图，会退回文生图并由调用方记录降级信息。
    """
    provider = (config.image_provider or 'pollinations').lower()
    if provider == 'maizi':
        return 'png', _gen_image_maizi(config, image_prompt, reference_images)
    if provider == 'openai':
        return 'png', _gen_image_openai(config, image_prompt, reference_images)
    return 'jpg', _gen_image_pollinations(config, image_prompt)


def provider_supports_reference(config: GenerationConfig) -> bool:
    """当前服务商是否支持参考图（图生图）。"""
    return (config.image_provider or 'pollinations').lower() in ('maizi', 'openai')


def _rule_based_note(job: RenderJob) -> str:
    """未启用真实调用时的规则文案兜底。"""
    return (
        f'【{job.style or "现代简约"} · {job.room_type or "客厅"}】\n'
        f'预算档位：{job.budget_tier or "品质"}。\n'
        f'需求：{job.requirement or "整体协调、采光良好、收纳充足"}。\n'
        '建议以浅色调为主、动线清晰，优先满足收纳与采光；'
        '家具选择见下方推荐清单。（启用大模型后将生成更详细的定制化设计说明）'
    )


def _match_furnitures(job: RenderJob, config: GenerationConfig | None = None, limit: int = 6) -> list:
    """按空间与风格从家具库匹配家具并关联到任务，返回家具列表（供生图使用）。

    先按空间可用品类过滤（避免客厅里摆床这类错配），再按风格收窄；
    任一条件匹配不到时逐级放宽，保证清单不为空。
    """
    style = job.style or ''
    room_type = job.room_type or ''
    furnitures = Furniture.objects.filter(is_active=True)
    categories = room_categories(room_type)
    scoped = list(furnitures.filter(category__in=categories) if categories else furnitures)
    # rooms 为 JSON 列表，跨库 JSON 查询语法不一，这里在 Python 侧过滤；
    # 留空表示不限空间
    if room_type:
        scoped = [f for f in scoped if not f.rooms or room_type in f.rooms]
    styled = [f for f in scoped if f.style == style] if style else list(scoped)
    picked = styled[:limit]
    # 同风格不足时，用同空间的其他风格补齐；仍为空则放宽空间限制
    if len(picked) < limit:
        picked_ids = {f.pk for f in picked}
        picked += [f for f in scoped if f.pk not in picked_ids][: limit - len(picked)]
    if not picked:
        picked = list(furnitures[:limit])
    retry_write(lambda: job.furnitures.set(picked), label=f'job#{job.pk}.furnitures')
    # 补齐商品图，保证前端家具清单可展示图片（已有图的商品不重复生成）
    for furniture in picked:
        try:
            ensure_furniture_image(furniture, config)
        except Exception:  # noqa: BLE001
            logger.exception('ensure furniture image failed: %s', furniture.pk)
    return picked


def _match_providers(job: RenderJob) -> None:
    """匹配施工队与设计师。"""
    job.contractor = (
        ServiceProvider.objects.filter(is_active=True, kind=ServiceProvider.Kind.CONSTRUCTION)
        .order_by('-rating').first()
    )
    job.designer = Designer.objects.filter(is_active=True).order_by('-rating').first()
    retry_write(
        lambda: job.save(update_fields=['contractor', 'designer', 'updated_at']),
        label=f'job#{job.pk}.providers',
    )


def run_render_job(job: RenderJob, module_codes=None, workflow=None) -> RenderJob:
    """执行一次渲染任务，具体流程由后台可编排的工作流驱动。

    - module_codes：前端提交的 prompt 控制模块编码；为空时沿用任务上已关联的
      模块，仍为空则回退到后端默认模块。真正的提示词文本始终来自后端；
    - workflow：显式指定使用的生图工作流；为空时按工作流分类标签自动匹配
      空间/风格/预算档位，无匹配再回退默认工作流，仍无则走内置链路。
      上传图先经工作流的预处理步骤，成图再经后处理步骤，最后交付给用户。
    """
    from .workflow import deliver_output, run_workflow

    if module_codes is None:
        module_codes = [m.code for m in job.prompt_modules.all()]

    job.status = RenderJob.Status.RUNNING
    retry_write(
        lambda: job.save(update_fields=['status', 'updated_at']),
        label=f'job#{job.pk}.status',
    )

    ctx, log, errors = run_workflow(job, module_codes, workflow or job.workflow)
    deliver_output(ctx, errors)

    job.workflow = ctx.workflow_used
    job.workflow_log = log
    job.prompt = ctx.prompt
    job.negative_prompt = ctx.negative_prompt
    job.status = RenderJob.Status.SUCCESS
    job.error = '；'.join(errors)
    retry_write(job.save, label=f'job#{job.pk}.final')
    return job
