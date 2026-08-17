"""生图工作流引擎。

把一次渲染拆成可在后台编排的步骤序列：

    上传图预处理 → 画面分析 → 提示词装配 → 调用生图 → 成图后处理 → 交付

每个步骤是一个注册在 `STEP_HANDLERS` 里的处理器，签名统一为
`handler(ctx, params) -> str`（返回一句摘要写进执行日志）。
运营在 admin 里增删步骤、调顺序、改 JSON 参数即可改变流水线，无需改代码。

设计约束：
- 步骤之间通过 `WorkflowContext` 传递数据（上传图字节、prompt、生图结果……），
  不直接互相调用，方便任意增删与换序；
- 默认「单步失败不阻塞整单」，降级信息写入日志与 `job.error`，保证用户始终拿到图；
- 没有配置工作流时回退到内置默认步骤链，行为与改造前一致。

生图有两种步骤可选：
- `GENERATE_IMAGE`（文生图）：只用提示词，产出是「同类空间」的效果图；
- `EDIT_IMAGE`（图生图）：把预处理后的上传照片作为参考图一起提交，
  产出会沿用原始户型、门窗位置与拍摄视角，是「这间房装完的样子」。
"""
from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass, field

from django.core.files.base import ContentFile

from .dbwrite import retry_write
from .models import GenerationConfig, RenderJob, RenderWorkflow, WorkflowStep

logger = logging.getLogger(__name__)

# 未配置工作流时的内置链路（与改造前行为一致）
FALLBACK_STEPS = [
    (WorkflowStep.Kind.MATCH_FURNITURE, {}),
    (WorkflowStep.Kind.BUILD_PROMPT, {}),
    (WorkflowStep.Kind.EDIT_IMAGE, {}),
    (WorkflowStep.Kind.DESIGN_NOTE, {}),
    (WorkflowStep.Kind.MATCH_PROVIDER, {}),
]

# 图生图默认追加的空间保持约束：告诉模型「改装修，不改房子」
PRESERVE_CLAUSE = (
    'keep the exact same room from the reference photo: same floor plan, '
    'same window and door positions, same ceiling height and camera viewpoint; '
    'only add finishes, furniture and lighting'
)


@dataclass
class WorkflowContext:
    """步骤之间共享的运行时上下文。"""

    job: RenderJob
    config: GenerationConfig
    workflow_used: RenderWorkflow | None = None
    module_codes: list = field(default_factory=list)
    modules: list = field(default_factory=list)
    furnitures: list = field(default_factory=list)
    # 上传图（经预处理后的字节与格式），供生图步骤使用
    input_bytes: bytes | None = None
    input_format: str = ''
    input_meta: dict = field(default_factory=dict)
    # 提示词
    prompt: str = ''
    negative_prompt: str = ''
    note_extra: str = ''
    note_prompt: str = ''
    # 生图产物
    output_bytes: bytes | None = None
    output_ext: str = ''
    # 生图模式：'text2img' / 'img2img'
    generate_mode: str = ''
    warnings: list = field(default_factory=list)

    def load_input(self) -> bytes:
        """惰性读取上传图原始字节。"""
        if self.input_bytes is None:
            self.job.raw_photo.open('rb')
            try:
                self.input_bytes = self.job.raw_photo.read()
            finally:
                self.job.raw_photo.close()
        return self.input_bytes


# ---------------------------------------------------------------- 图像工具

def _open_image(data: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(data))


def _dump_image(img, fmt: str = 'PNG', quality: int = 92) -> bytes:
    buf = io.BytesIO()
    if fmt.upper() in ('JPG', 'JPEG'):
        img = img.convert('RGB')
        img.save(buf, 'JPEG', quality=quality)
    else:
        img.save(buf, fmt.upper())
    return buf.getvalue()


# ---------------------------------------------------------------- 步骤处理器

def step_validate_input(ctx: WorkflowContext, params: dict) -> str:
    """输入校验：兜底确认上传图可解析且尺寸合规。"""
    data = ctx.load_input()
    min_side = int(params.get('min_side', 256))
    with _open_image(data) as img:
        width, height = img.size
        fmt = img.format or ''
    if min(width, height) < min_side:
        raise ValueError(f'上传图过小（{width}×{height}，要求短边 ≥ {min_side}）')
    ctx.input_format = fmt
    ctx.input_meta.update({'width': width, 'height': height, 'format': fmt})
    return f'{fmt} {width}×{height}，{len(data) // 1024}KB'


def step_auto_orient(ctx: WorkflowContext, params: dict) -> str:
    """按 EXIF 方向摆正上传图，避免手机竖拍被转 90 度。"""
    from PIL import ImageOps

    data = ctx.load_input()
    with _open_image(data) as img:
        fixed = ImageOps.exif_transpose(img)
        changed = fixed.size != img.size
        ctx.input_bytes = _dump_image(fixed, 'PNG')
    return '已按 EXIF 摆正' if changed else '方向正常，无需处理'


def step_resize_input(ctx: WorkflowContext, params: dict) -> str:
    """把上传图压到合适尺寸，减少上传体积与生图耗时。"""
    max_side = int(params.get('max_side', 1536))
    data = ctx.load_input()
    with _open_image(data) as img:
        width, height = img.size
        if max(width, height) <= max_side:
            return f'{width}×{height} 未超过 {max_side}，跳过'
        scale = max_side / max(width, height)
        target = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = img.convert('RGB').resize(target, _resample())
        ctx.input_bytes = _dump_image(resized, params.get('format', 'PNG'))
    ctx.input_meta.update({'width': target[0], 'height': target[1]})
    return f'{width}×{height} → {target[0]}×{target[1]}'


def _resample():
    from PIL import Image

    return getattr(Image, 'LANCZOS', Image.BICUBIC)


def step_enhance_input(ctx: WorkflowContext, params: dict) -> str:
    """增强上传图：毛坯房照片通常偏暗偏灰，先修一版再喂给生图模型。"""
    from PIL import ImageEnhance

    brightness = float(params.get('brightness', 1.08))
    contrast = float(params.get('contrast', 1.12))
    sharpness = float(params.get('sharpness', 1.15))
    data = ctx.load_input()
    with _open_image(data) as img:
        out = img.convert('RGB')
        out = ImageEnhance.Brightness(out).enhance(brightness)
        out = ImageEnhance.Contrast(out).enhance(contrast)
        out = ImageEnhance.Sharpness(out).enhance(sharpness)
        ctx.input_bytes = _dump_image(out, 'PNG')
    return f'亮度×{brightness} 对比×{contrast} 锐化×{sharpness}'


def step_analyze_input(ctx: WorkflowContext, params: dict) -> str:
    """分析上传图，把客观特征写进提示词，让生图更贴合原始空间。"""
    import colorsys

    data = ctx.load_input()
    with _open_image(data) as img:
        small = img.convert('RGB').resize((64, 64), _resample())
        pixels = list(small.getdata())
    count = len(pixels) or 1
    avg = [sum(channel) / count / 255 for channel in zip(*pixels)]
    hue, sat, val = colorsys.rgb_to_hsv(*avg)
    orientation = 'portrait'
    width = ctx.input_meta.get('width') or 0
    height = ctx.input_meta.get('height') or 0
    if width and height:
        orientation = 'landscape' if width >= height else 'portrait'
    brightness_label = 'dim' if val < 0.35 else ('bright' if val > 0.65 else 'medium')
    tone_label = 'warm' if hue < 0.12 or hue > 0.8 else ('cool' if 0.45 < hue < 0.75 else 'neutral')
    ctx.input_meta.update({
        'brightness': brightness_label,
        'tone': tone_label,
        'orientation': orientation,
        'saturation': round(sat, 3),
    })
    if params.get('inject_prompt', True):
        ctx.input_meta['prompt_hint'] = (
            f'{orientation} composition, original room is {brightness_label} '
            f'with {tone_label} tone'
        )
    return f'亮度={brightness_label} 色调={tone_label} 构图={orientation}'


def step_mark_doors(ctx: WorkflowContext, params: dict) -> str:
    """识别上传图中的门洞，并注入「门洞区域禁止摆放家具」的提示词约束。

    门洞通常表现为竖直的长方形开口，且底部接近地面。这里用边缘检测 +
    轮廓比例过滤做启发式识别，精度适合生成效果图的软约束，不作为精确测量。
    """
    import cv2
    import numpy as np

    data = ctx.load_input()
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('无法解析上传图，无法标记门洞')
    height, width = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(
        blurred,
        int(params.get('canny_low', 50)),
        int(params.get('canny_high', 150)),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    aspect_min = float(params.get('aspect_min', 1.5))
    aspect_max = float(params.get('aspect_max', 3.8))
    min_area_ratio = float(params.get('min_area_ratio', 0.008))
    min_w_ratio = float(params.get('min_w_ratio', 0.04))
    max_w_ratio = float(params.get('max_w_ratio', 0.45))
    min_h_ratio = float(params.get('min_h_ratio', 0.20))
    max_h_ratio = float(params.get('max_h_ratio', 0.95))
    max_doors = int(params.get('max_doors', 8))

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, box_w, box_h = cv2.boundingRect(contour)
        aspect = box_h / box_w if box_w else 0.0
        bottom = y + box_h
        if area < width * height * min_area_ratio:
            continue
        if not (aspect_min <= aspect <= aspect_max):
            continue
        if not (min_w_ratio * width <= box_w <= max_w_ratio * width):
            continue
        if not (min_h_ratio * height <= box_h <= max_h_ratio * height):
            continue
        if bottom < height * 0.35 or bottom > height * 0.98:
            continue
        candidates.append((area, x, y, box_w, box_h))

    candidates.sort(key=lambda item: item[0], reverse=True)
    doors = []
    for _, x, y, box_w, box_h in candidates:
        overlap = False
        for door in doors:
            ix = max(x, door['x'])
            iy = max(y, door['y'])
            ixx = min(x + box_w, door['x'] + door['w'])
            iyy = min(y + box_h, door['y'] + door['h'])
            inter = max(0, ixx - ix) * max(0, iyy - iy)
            union = box_w * box_h + door['w'] * door['h'] - inter
            if union and inter / union > 0.35:
                overlap = True
                break
        if overlap:
            continue
        doors.append({'x': x, 'y': y, 'w': box_w, 'h': box_h})
        if len(doors) >= max_doors:
            break

    ctx.input_meta['door_openings'] = doors

    if params.get('inject_prompt', True):
        positive = (
            'keep all door openings and walkways completely clear; '
            'do not place any furniture, cabinetry, plants or storage in front of any door'
        )
        negative = (
            'furniture blocking a doorway, furniture in front of doors, '
            'obstructed entrances and walkways'
        )
        if ctx.prompt:
            ctx.prompt = f'{ctx.prompt}, {positive}'
            ctx.negative_prompt = (
                f'{ctx.negative_prompt}, {negative}'
                if ctx.negative_prompt
                else negative
            )
        else:
            existing_hint = ctx.input_meta.get('prompt_hint') or ''
            ctx.input_meta['prompt_hint'] = (
                f'{existing_hint}, {positive}' if existing_hint else positive
            )
        note = '门洞区域保持畅通，不可摆放家具、柜体或遮挡物；'
        ctx.note_extra = f'{ctx.note_extra}{note}' if ctx.note_extra else note

    if not doors:
        return '未识别到明显门洞，已注入通用门洞避让约束'
    summaries = '、'.join(
        f'({d["x"]},{d["y"]},{d["w"]}×{d["h"]})' for d in doors
    )
    return f'识别到 {len(doors)} 个门洞：{summaries}'


def step_match_furniture(ctx: WorkflowContext, params: dict) -> str:
    """匹配家具库，并按需补齐商品图。"""
    from .imagegen import _match_furnitures

    limit = int(params.get('limit', 6))
    ctx.furnitures = _match_furnitures(ctx.job, ctx.config, limit=limit)
    names = '、'.join(f.name for f in ctx.furnitures[:3])
    return f'匹配 {len(ctx.furnitures)} 件：{names}…' if ctx.furnitures else '家具库为空'


def step_build_prompt(ctx: WorkflowContext, params: dict) -> str:
    """用 prompt 控制模块装配提示词，可叠加上一步的画面分析结论。"""
    from .imagegen import build_image_prompt, build_prompt
    from .prompts import resolve_modules

    ctx.modules = resolve_modules(ctx.module_codes, ctx.job.room_type, ctx.job.style)
    retry_write(
        lambda: ctx.job.prompt_modules.set(ctx.modules),
        label=f'job#{ctx.job.pk}.prompt_modules',
    )
    bundle = build_image_prompt(ctx.job, ctx.furnitures, ctx.modules)
    ctx.prompt = bundle.positive
    ctx.negative_prompt = bundle.negative
    ctx.note_extra = bundle.note_extra

    hint = ctx.input_meta.get('prompt_hint')
    if hint and params.get('use_image_analysis', True):
        ctx.prompt = f'{ctx.prompt}, {hint}'
    ctx.note_prompt = build_prompt(ctx.job, ctx.config, ctx.note_extra)
    return f'{len(ctx.modules)} 个模块，prompt {len(ctx.prompt)} 字符'


def step_append_prompt(ctx: WorkflowContext, params: dict) -> str:
    """在装配结果后追加固定片段，用于全局风格兜底或统一约束。"""
    positive = (params.get('positive') or '').strip()
    negative = (params.get('negative') or '').strip()
    if positive:
        ctx.prompt = f'{ctx.prompt}, {positive}' if ctx.prompt else positive
    if negative:
        ctx.negative_prompt = (
            f'{ctx.negative_prompt}, {negative}' if ctx.negative_prompt else negative
        )
    return f'追加正向 {len(positive)} / 负向 {len(negative)} 字符'


def step_generate_image(ctx: WorkflowContext, params: dict) -> str:
    """文生图：只用提示词调用图像端点；未启用真实生图时写占位图。"""
    from .imagegen import _generate_image, _placeholder_svg

    if not ctx.prompt:
        step_build_prompt(ctx, {})
    if not ctx.config.image_enabled:
        ctx.output_bytes = _placeholder_svg(ctx.job)
        ctx.output_ext = 'svg'
        return '未启用真实生图，写入占位图'
    ext, data = _generate_image(ctx.config, ctx.prompt)
    ctx.output_bytes = data
    ctx.output_ext = ext
    ctx.generate_mode = 'text2img'
    return f'生成 {ext} 图，{len(data) // 1024}KB'


def step_edit_image(ctx: WorkflowContext, params: dict) -> str:
    """图生图：把预处理后的上传照片作为参考图提交，保留原始空间结构。

    params：
    - preserve_space（默认 true）：追加「保持户型/门窗/视角不变」的约束；
    - fallback_to_text2img（默认 true）：服务商不支持参考图或调用失败时，
      退回文生图，保证用户仍能拿到图；
    - max_side：参考图提交前压到的最长边（默认取工作流预处理后的尺寸）。
    """
    from .imagegen import _generate_image, _placeholder_svg, provider_supports_reference

    if not ctx.prompt:
        step_build_prompt(ctx, {})
    if not ctx.config.image_enabled:
        ctx.output_bytes = _placeholder_svg(ctx.job)
        ctx.output_ext = 'svg'
        return '未启用真实生图，写入占位图'

    fallback = bool(params.get('fallback_to_text2img', True))
    prompt = ctx.prompt
    if params.get('preserve_space', True):
        prompt = f'{prompt}, {PRESERVE_CLAUSE}'

    if not provider_supports_reference(ctx.config):
        if not fallback:
            raise RuntimeError(
                f'服务商 {ctx.config.image_provider} 不支持参考图，无法图生图')
        ext, data = _generate_image(ctx.config, ctx.prompt)
        ctx.output_bytes, ctx.output_ext, ctx.generate_mode = data, ext, 'text2img'
        ctx.warnings.append('服务商不支持参考图，已退回文生图')
        return f'服务商 {ctx.config.image_provider} 不支持参考图，退回文生图（{ext}）'

    reference = ctx.load_input()
    max_side = params.get('max_side')
    if max_side:
        reference = _shrink_bytes(reference, int(max_side))
    try:
        ext, data = _generate_image(ctx.config, prompt, [reference])
        ctx.output_bytes, ctx.output_ext, ctx.generate_mode = data, ext, 'img2img'
        return f'图生图成功：参考图 {len(reference) // 1024}KB → {ext} 图 {len(data) // 1024}KB'
    except Exception as exc:  # noqa: BLE001
        if not fallback:
            raise
        logger.warning('img2img failed on job %s, fallback to text2img: %s', ctx.job.pk, exc)
        ext, data = _generate_image(ctx.config, ctx.prompt)
        ctx.output_bytes, ctx.output_ext, ctx.generate_mode = data, ext, 'text2img'
        ctx.warnings.append(f'图生图失败已退回文生图（{exc}）')
        return f'图生图失败（{exc}），已退回文生图'


def _shrink_bytes(data: bytes, max_side: int) -> bytes:
    """按最长边压缩字节流，供参考图提交前控制体积。"""
    with _open_image(data) as img:
        if max(img.size) <= max_side:
            return data
        scale = max_side / max(img.size)
        target = (max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale)))
        return _dump_image(img.convert('RGB').resize(target, _resample()), 'JPEG')


def step_postprocess(ctx: WorkflowContext, params: dict) -> str:
    """成图调色：统一观感，弥补模型输出偏灰偏暗。"""
    from PIL import ImageEnhance

    if not _has_bitmap_output(ctx):
        return '无位图产物，跳过'
    brightness = float(params.get('brightness', 1.02))
    contrast = float(params.get('contrast', 1.05))
    saturation = float(params.get('saturation', 1.05))
    sharpness = float(params.get('sharpness', 1.08))
    with _open_image(ctx.output_bytes) as img:
        out = img.convert('RGB')
        out = ImageEnhance.Brightness(out).enhance(brightness)
        out = ImageEnhance.Contrast(out).enhance(contrast)
        out = ImageEnhance.Color(out).enhance(saturation)
        out = ImageEnhance.Sharpness(out).enhance(sharpness)
        ctx.output_bytes = _dump_image(out, 'PNG')
    ctx.output_ext = 'png'
    return f'亮度×{brightness} 对比×{contrast} 饱和×{saturation}'


def step_resize_output(ctx: WorkflowContext, params: dict) -> str:
    """按交付要求缩放成图，控制前端加载体积。"""
    if not _has_bitmap_output(ctx):
        return '无位图产物，跳过'
    max_side = int(params.get('max_side', 1600))
    with _open_image(ctx.output_bytes) as img:
        width, height = img.size
        if max(width, height) <= max_side:
            return f'{width}×{height} 未超过 {max_side}，跳过'
        scale = max_side / max(width, height)
        target = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized = img.convert('RGB').resize(target, _resample())
        ctx.output_bytes = _dump_image(resized, params.get('format', 'PNG'))
    ctx.output_ext = params.get('format', 'png').lower()
    return f'{width}×{height} → {target[0]}×{target[1]}'


def step_watermark(ctx: WorkflowContext, params: dict) -> str:
    """给交付图加水印，标注 AI 生成与来源，避免被当作实拍。"""
    from PIL import Image, ImageDraw

    if not _has_bitmap_output(ctx):
        return '无位图产物，跳过'
    text = str(params.get('text') or 'AI 效果图 · 仅供参考')
    opacity = int(float(params.get('opacity', 0.45)) * 255)
    position = str(params.get('position', 'bottom_right'))
    margin = int(params.get('margin', 24))

    with _open_image(ctx.output_bytes) as img:
        base = img.convert('RGBA')
        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = _load_font(int(params.get('font_size', max(18, base.size[0] // 45))))
        box = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = box[2] - box[0], box[3] - box[1]
        positions = {
            'bottom_right': (base.size[0] - text_w - margin, base.size[1] - text_h - margin * 2),
            'bottom_left': (margin, base.size[1] - text_h - margin * 2),
            'top_right': (base.size[0] - text_w - margin, margin),
            'top_left': (margin, margin),
        }
        origin = positions.get(position, positions['bottom_right'])
        draw.text((origin[0] + 1, origin[1] + 1), text, font=font, fill=(0, 0, 0, opacity // 2))
        draw.text(origin, text, font=font, fill=(255, 255, 255, opacity))
        merged = Image.alpha_composite(base, overlay).convert('RGB')
        ctx.output_bytes = _dump_image(merged, 'PNG')
    ctx.output_ext = 'png'
    return f'水印「{text}」@{position}'


def _load_font(size: int):
    from PIL import ImageFont

    for path in (
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def step_design_note(ctx: WorkflowContext, params: dict) -> str:
    """生成 AI 设计说明，失败降级规则文案。"""
    from .imagegen import _call_chat_design_note, _rule_based_note, build_prompt

    if not ctx.note_prompt:
        ctx.note_prompt = build_prompt(ctx.job, ctx.config, ctx.note_extra)
    if ctx.config.enabled and ctx.config.api_key:
        ctx.job.design_note = _call_chat_design_note(ctx.config, ctx.note_prompt)
        return f'大模型生成 {len(ctx.job.design_note)} 字'
    ctx.job.design_note = _rule_based_note(ctx.job)
    return '未启用文本大模型，使用规则文案'


def step_match_provider(ctx: WorkflowContext, params: dict) -> str:
    """匹配推荐施工队与设计师。"""
    from .imagegen import _match_providers

    _match_providers(ctx.job)
    bits = []
    if ctx.job.contractor:
        bits.append(f'施工队={ctx.job.contractor.name}')
    if ctx.job.designer:
        bits.append(f'设计师={ctx.job.designer.name}')
    return '、'.join(bits) or '暂无可匹配服务商'


def _has_bitmap_output(ctx: WorkflowContext) -> bool:
    """占位 SVG 不是位图，后处理步骤需要跳过。"""
    return bool(ctx.output_bytes) and ctx.output_ext.lower() in ('png', 'jpg', 'jpeg', 'webp')


STEP_HANDLERS = {
    WorkflowStep.Kind.VALIDATE_INPUT: step_validate_input,
    WorkflowStep.Kind.AUTO_ORIENT: step_auto_orient,
    WorkflowStep.Kind.RESIZE_INPUT: step_resize_input,
    WorkflowStep.Kind.ENHANCE_INPUT: step_enhance_input,
    WorkflowStep.Kind.ANALYZE_INPUT: step_analyze_input,
    WorkflowStep.Kind.MARK_DOORS: step_mark_doors,
    WorkflowStep.Kind.MATCH_FURNITURE: step_match_furniture,
    WorkflowStep.Kind.BUILD_PROMPT: step_build_prompt,
    WorkflowStep.Kind.APPEND_PROMPT: step_append_prompt,
    WorkflowStep.Kind.GENERATE_IMAGE: step_generate_image,
    WorkflowStep.Kind.EDIT_IMAGE: step_edit_image,
    WorkflowStep.Kind.POSTPROCESS: step_postprocess,
    WorkflowStep.Kind.RESIZE_OUTPUT: step_resize_output,
    WorkflowStep.Kind.WATERMARK: step_watermark,
    WorkflowStep.Kind.DESIGN_NOTE: step_design_note,
    WorkflowStep.Kind.MATCH_PROVIDER: step_match_provider,
}


def _plan(workflow: RenderWorkflow | None):
    """得到 [(kind, params, label, continue_on_error)] 执行计划。"""
    if workflow is None:
        return [
            (kind, params, WorkflowStep.Kind(kind).label, True)
            for kind, params in FALLBACK_STEPS
        ]
    steps = workflow.active_steps()
    if not steps:
        return [
            (kind, params, WorkflowStep.Kind(kind).label, True)
            for kind, params in FALLBACK_STEPS
        ]
    return [
        (s.kind, s.params or {}, s.name or s.get_kind_display(), s.continue_on_error)
        for s in steps
    ]


def run_workflow(job: RenderJob, module_codes=None, workflow: RenderWorkflow | None = None):
    """按工作流执行一次渲染，返回 (context, log, errors)。

    未显式指定 workflow 时，会按任务的空间/风格/预算档位与工作流分类标签
    自动匹配；无匹配再回退默认工作流。引擎只负责调度与记录；具体行为都在步骤处理器里。
    上传图经预处理步骤后才进入生图，成图经后处理步骤后才交付给用户。
    """
    config = GenerationConfig.load()
    workflow = RenderWorkflow.resolve(workflow, job=job)
    ctx = WorkflowContext(
        job=job, config=config, workflow_used=workflow, module_codes=module_codes or [])

    log, errors = [], []
    for index, (kind, params, label, continue_on_error) in enumerate(_plan(workflow), start=1):
        handler = STEP_HANDLERS.get(kind)
        entry = {'order': index, 'kind': kind, 'name': label}
        if handler is None:
            entry.update(status='skipped', detail='未实现的步骤类型')
            log.append(entry)
            continue
        started = time.time()
        try:
            detail = handler(ctx, params or {})
            entry.update(status='ok', detail=detail or '')
        except Exception as exc:  # noqa: BLE001
            logger.exception('workflow step %s failed on job %s', kind, job.pk)
            entry.update(status='failed', detail=str(exc))
            errors.append(f'{label}失败（{exc}）')
            if not continue_on_error or (workflow and workflow.stop_on_error):
                entry['detail'] += '｜已终止后续步骤'
                entry['elapsed_ms'] = int((time.time() - started) * 1000)
                log.append(entry)
                break
        entry['elapsed_ms'] = int((time.time() - started) * 1000)
        log.append(entry)

    return ctx, log, errors


def deliver_output(ctx: WorkflowContext, errors: list) -> None:
    """把工作流产物落到 job 上；没有产物时写占位图，保证前端有图可展示。"""
    from .imagegen import _placeholder_svg

    job = ctx.job
    # 降级提示（如图生图退回文生图）与错误同渠道回传，便于前端与运营感知
    errors.extend(ctx.warnings)
    if ctx.output_bytes:
        ext = ctx.output_ext or 'png'
        job.result_image.save(f'render_{job.pk}.{ext}', ContentFile(ctx.output_bytes), save=False)
    else:
        job.result_image.save(
            f'render_{job.pk}.svg', ContentFile(_placeholder_svg(job)), save=False)
        errors.append('工作流未产出图像，已回退占位图')
