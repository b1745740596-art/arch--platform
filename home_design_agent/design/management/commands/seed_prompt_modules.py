from django.core.management.base import BaseCommand

from design.models import PromptModule

G = PromptModule.Group

# (code, name, group, description, prompt_fragment, negative_fragment,
#  note_fragment, weight, is_default)
MODULES = [
    # ---- 灯光氛围 ----
    ('lighting_soft', '柔和自然光', G.LIGHTING, '大面积漫射光，通透耐看',
     'soft diffused natural daylight, large windows, gentle light gradient',
     'harsh shadows, overexposed highlights', '优先保证自然采光与柔和过渡', 10, True),
    ('lighting_warm_night', '暖调夜景', G.LIGHTING, '夜晚暖光，突出灯具层次',
     'warm evening ambient lighting, layered lamps, cozy glow, subtle reflections',
     'flat lighting, daylight', '需说明主照明与辅助照明的分层方案', 11, False),
    ('lighting_dramatic', '戏剧光影', G.LIGHTING, '强对比光影，空间更有张力',
     'dramatic directional lighting, strong light and shadow contrast, cinematic',
     'flat even lighting', '注意控制阴影区域的功能照明补足', 12, False),

    # ---- 材质质感 ----
    ('material_wood', '木质温润', G.MATERIAL, '木饰面与木地板为主材',
     'warm wood veneer surfaces, oak flooring, natural wood grain texture',
     'plastic looking surfaces', '推荐木饰面等级与耐磨要求', 20, True),
    ('material_stone', '石材轻奢', G.MATERIAL, '岩板/大理石纹理提升质感',
     'marble and sintered stone surfaces, subtle veining, polished finish',
     'cheap tile texture', '需提示石材铺贴与拼缝工艺要求', 21, False),
    ('material_fabric', '布艺柔软', G.MATERIAL, '棉麻布艺与地毯增加柔软度',
     'linen and cotton upholstery, soft rugs, layered textiles',
     'stiff synthetic fabric', '补充布艺易清洁与更换建议', 22, False),
    ('material_metal', '金属点缀', G.MATERIAL, '细金属线条勾勒轮廓',
     'brushed metal accents, slim black or brass trim lines',
     'rusty metal, industrial clutter', '说明金属收边件的工艺与成本', 23, False),

    # ---- 镜头视角 ----
    ('camera_wide', '广角全景', G.CAMERA, '一眼看全空间关系',
     'wide angle interior shot, one point perspective, full room visible',
     'fisheye distortion', '', 30, True),
    ('camera_corner', '斜角构图', G.CAMERA, '两墙夹角，纵深更强',
     'two point perspective from room corner, strong depth',
     'flat frontal composition', '', 31, False),
    ('camera_detail', '局部特写', G.CAMERA, '聚焦核心家具与材质细节',
     'medium close-up on the key furniture group, shallow depth of field',
     'empty wide room', '侧重核心家具的选型理由', 32, False),

    # ---- 色彩基调 ----
    ('color_neutral', '中性米白', G.COLOR, '低饱和大面积浅色',
     'neutral off-white and beige palette, low saturation, calm tone',
     'saturated bright colors', '主辅色比例建议 7:2:1', 40, True),
    ('color_earth', '大地色系', G.COLOR, '棕、驼、陶土色更沉稳',
     'earth tone palette, terracotta and camel accents, warm muted colors',
     'cold blue tint', '注意深色占比对采光的影响', 41, False),
    ('color_contrast', '深浅对比', G.COLOR, '深色背景衬托浅色家具',
     'high contrast palette, deep charcoal walls with light furniture',
     'muddy mixed colors', '深色墙面需配合更强的照明', 42, False),

    # ---- 布局收纳 ----
    ('layout_storage', '收纳最大化', G.LAYOUT, '整墙柜与隐形收纳',
     'full height built-in cabinets, hidden storage, clutter free surfaces',
     'visible clutter', '给出每个功能区的收纳容量估算', 50, True),
    ('layout_open', '开放通透', G.LAYOUT, '减少隔断，动线更顺',
     'open plan layout, minimal partitions, clear circulation path',
     'cramped narrow passage', '提示承重墙与管线的可改动边界', 51, False),
    ('layout_multifunc', '多功能复合', G.LAYOUT, '一室多用，兼顾办公与休憩',
     'multifunctional zoning, work corner integrated with living area',
     'single purpose empty room', '说明各功能区的切换方式', 52, False),

    # ---- 情绪风格 ----
    ('mood_cozy', '温暖居家', G.MOOD, '生活气息，适合家庭',
     'cozy lived-in atmosphere, plants and books, homely details',
     'sterile showroom', '补充适合家庭成员的细节建议', 60, False),
    ('mood_clean', '克制极简', G.MOOD, '去繁就简，视觉安静',
     'restrained minimal styling, very few decorative objects, quiet composition',
     'busy decoration', '强调「少而精」的软装取舍', 61, True),
    ('mood_hotel', '酒店质感', G.MOOD, '整齐利落，接近样板间',
     'boutique hotel styling, crisp linens, symmetrical arrangement',
     'messy casual styling', '提示日常维护成本', 62, False),

    # ---- 画质控制 ----
    ('quality_photo', '写实照片级', G.QUALITY, '接近实拍的真实感',
     'photorealistic architectural photography, 8k, physically based rendering, high detail',
     'illustration, cartoon, cgi look', '', 70, True),
    ('quality_clean_geometry', '结构准确', G.QUALITY, '保持墙体与透视正确',
     'accurate architectural geometry, straight vertical lines, correct proportions',
     'warped walls, bent lines, impossible geometry', '需提示与原始户型的一致性', 71, True),
    ('quality_no_text', '无文字水印', G.QUALITY, '画面不出现文字与标识',
     'clean image without any text',
     'text, letters, watermark, logo, signature', '', 72, False),
]


class Command(BaseCommand):
    help = '填充后端预设的 prompt 控制模块（幂等，可重复执行）'

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true',
                            help='已存在的模块也覆盖更新提示词与配置')

    def handle(self, *args, **options):
        created_count = updated_count = 0
        for (code, name, group, description, fragment, negative,
             note, weight, is_default) in MODULES:
            defaults = dict(
                name=name, group=group, description=description,
                prompt_fragment=fragment, negative_fragment=negative,
                note_fragment=note, weight=weight, is_default=is_default,
                is_active=True,
            )
            obj, created = PromptModule.objects.get_or_create(code=code, defaults=defaults)
            if created:
                created_count += 1
            elif options['update']:
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save()
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'prompt modules ready: created={created_count} updated={updated_count} '
            f'total={PromptModule.objects.count()}'
        ))
