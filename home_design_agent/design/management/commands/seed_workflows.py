from django.core.management.base import BaseCommand

from design.models import RenderWorkflow, WorkflowStep

K = WorkflowStep.Kind

# (name, description, is_default, [(order, kind, name, params)])
WORKFLOWS = [
    (
        '标准交付流程', '上传图校正增强 → 分析 → 装配提示词 → 图生图 → 调色 → 水印交付', True,
        [
            (10, K.VALIDATE_INPUT, '输入校验', {'min_side': 512}),
            (20, K.AUTO_ORIENT, '按 EXIF 摆正', {}),
            (30, K.RESIZE_INPUT, '压到 1536px', {'max_side': 1536}),
            (40, K.ENHANCE_INPUT, '毛坯照片增强',
             {'brightness': 1.08, 'contrast': 1.12, 'sharpness': 1.15}),
            (50, K.ANALYZE_INPUT, '画面分析', {'inject_prompt': True}),
            (60, K.MATCH_FURNITURE, '匹配家具库', {'limit': 6}),
            (70, K.BUILD_PROMPT, '装配提示词', {'use_image_analysis': True}),
            (80, K.EDIT_IMAGE, '图生图（保留原空间）',
             {'preserve_space': True, 'fallback_to_text2img': True, 'max_side': 1024}),
            (90, K.POSTPROCESS, '成图调色',
             {'brightness': 1.02, 'contrast': 1.05, 'saturation': 1.06, 'sharpness': 1.08}),
            (100, K.RESIZE_OUTPUT, '交付尺寸', {'max_side': 1600}),
            (110, K.WATERMARK, '加水印',
             {'text': 'AI 效果图 · 仅供参考', 'position': 'bottom_right', 'opacity': 0.45}),
            (120, K.DESIGN_NOTE, '生成设计说明', {}),
            (130, K.MATCH_PROVIDER, '匹配服务商', {}),
        ],
    ),
    (
        '快速预览流程', '图生图 + 跳过增强与水印，最快出图，用于多方案并行对比', False,
        [
            (10, K.VALIDATE_INPUT, '输入校验', {'min_side': 512}),
            (20, K.RESIZE_INPUT, '压到 1024px', {'max_side': 1024}),
            (30, K.MATCH_FURNITURE, '匹配家具库', {'limit': 4}),
            (40, K.BUILD_PROMPT, '装配提示词', {'use_image_analysis': False}),
            (50, K.EDIT_IMAGE, '图生图（保留原空间）',
             {'preserve_space': True, 'fallback_to_text2img': True, 'max_side': 768}),
            (60, K.RESIZE_OUTPUT, '交付尺寸', {'max_side': 1200}),
            (70, K.DESIGN_NOTE, '生成设计说明', {}),
            (80, K.MATCH_PROVIDER, '匹配服务商', {}),
        ],
    ),
    (
        '高保真出片流程', '图生图 + 强化输入与成图质感，加统一风格兜底，用于对外汇报', False,
        [
            (10, K.VALIDATE_INPUT, '输入校验', {'min_side': 768}),
            (20, K.AUTO_ORIENT, '按 EXIF 摆正', {}),
            (30, K.RESIZE_INPUT, '压到 2048px', {'max_side': 2048}),
            (40, K.ENHANCE_INPUT, '毛坯照片增强',
             {'brightness': 1.05, 'contrast': 1.15, 'sharpness': 1.25}),
            (50, K.ANALYZE_INPUT, '画面分析', {'inject_prompt': True}),
            (60, K.MATCH_FURNITURE, '匹配家具库', {'limit': 6}),
            (70, K.BUILD_PROMPT, '装配提示词', {'use_image_analysis': True}),
            (75, K.APPEND_PROMPT, '统一质感兜底',
             {'positive': 'architectural digest quality, professional interior photography',
              'negative': 'cluttered composition, unrealistic proportions'}),
            (80, K.EDIT_IMAGE, '图生图（保留原空间）',
             {'preserve_space': True, 'fallback_to_text2img': True, 'max_side': 1280}),
            (90, K.POSTPROCESS, '成图调色',
             {'brightness': 1.03, 'contrast': 1.08, 'saturation': 1.1, 'sharpness': 1.15}),
            (100, K.WATERMARK, '加水印',
             {'text': 'AI 效果图 · 仅供参考', 'position': 'bottom_left', 'opacity': 0.35}),
            (110, K.DESIGN_NOTE, '生成设计说明', {}),
            (120, K.MATCH_PROVIDER, '匹配服务商', {}),
        ],
    ),
    (
        '灵感文生图流程', '不参考上传照片，只按风格与需求出图，用于早期风格探索', False,
        [
            (10, K.VALIDATE_INPUT, '输入校验', {'min_side': 512}),
            (20, K.MATCH_FURNITURE, '匹配家具库', {'limit': 4}),
            (30, K.BUILD_PROMPT, '装配提示词', {'use_image_analysis': False}),
            (40, K.GENERATE_IMAGE, '文生图', {}),
            (50, K.RESIZE_OUTPUT, '交付尺寸', {'max_side': 1200}),
            (60, K.DESIGN_NOTE, '生成设计说明', {}),
            (70, K.MATCH_PROVIDER, '匹配服务商', {}),
        ],
    ),
]


class Command(BaseCommand):
    help = '填充预置生图工作流（幂等；--reset 重建步骤）'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='已存在的工作流也清空步骤并按预置重建')

    def handle(self, *args, **options):
        for name, description, is_default, steps in WORKFLOWS:
            workflow, created = RenderWorkflow.objects.get_or_create(
                name=name,
                defaults=dict(description=description, is_default=is_default, is_active=True),
            )
            if created or options['reset']:
                workflow.description = description
                workflow.is_default = is_default
                workflow.is_active = True
                workflow.save()
                workflow.steps.all().delete()
                for order, kind, step_name, params in steps:
                    WorkflowStep.objects.create(
                        workflow=workflow, order=order, kind=kind,
                        name=step_name, params=params,
                    )
                action = '创建' if created else '重建'
                self.stdout.write(f'{action} {name}：{len(steps)} 个步骤')
            else:
                self.stdout.write(f'跳过 {name}（已存在，用 --reset 重建）')

        self.stdout.write(self.style.SUCCESS(
            f'workflows ready: {RenderWorkflow.objects.count()} 个工作流，'
            f'{WorkflowStep.objects.count()} 个步骤，'
            f'默认={RenderWorkflow.objects.filter(is_default=True).first()}'
        ))
