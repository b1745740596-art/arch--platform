import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    CustomerRequirement,
    Designer,
    DesignScheme,
    Furniture,
    Lead,
    Owner,
    Project,
    PromptModule,
    RenderJob,
    RenderWorkflow,
    ServiceProvider,
    WorkflowStep,
)
from .prompts import (
    BUDGET_TIERS,
    IMAGE_CONSTRAINTS,
    MAX_MODULES,
    REQUIREMENT_MAX_LENGTH,
    ROOM_TYPES,
    STYLES,
    module_payload,
    parse_module_codes,
)

# 输入内容风控：联系方式 / 链接 / 注入字符
SENSITIVE_CONTACT_RE = re.compile(
    r'(1[3-9]\d{9})'                      # 手机号
    r'|([\w.+-]+@[\w-]+\.[\w.]+)'         # 邮箱
    r'|(\d{17}[\dXx])'                    # 身份证
    r'|(\d{3,4}-?\d{7,8})'                # 固话
)
URL_RE = re.compile(r'(https?://|www\.)', re.IGNORECASE)
INJECTION_RE = re.compile(r'[<>{}]')


def _validate_choice(value, allowed, label):
    """枚举字段严格校验：只接受后端下发的候选值。"""
    text = (value or '').strip()
    if text and text not in allowed:
        raise serializers.ValidationError(
            f'{label}只能是：' + '、'.join(allowed))
    return text


def _image_dimensions(value):
    """读取上传图片的真实像素尺寸，读取失败返回 (0, 0) 交由其他规则兜底。"""
    try:
        from PIL import Image

        pointer = value.tell() if hasattr(value, 'tell') else 0
        value.seek(0)
        with Image.open(value) as img:
            size = img.size
        value.seek(pointer)
        return size
    except Exception:  # noqa: BLE001
        try:
            value.seek(0)
        except Exception:  # noqa: BLE001
            pass
        return 0, 0


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = '__all__'


class DesignSchemeSerializer(serializers.ModelSerializer):
    budget_tier_display = serializers.CharField(source='get_budget_tier_display', read_only=True)

    class Meta:
        model = DesignScheme
        fields = '__all__'


class ProjectSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    schemes = DesignSchemeSerializer(many=True, read_only=True)
    scheme_count = serializers.IntegerField(source='schemes.count', read_only=True)

    class Meta:
        model = Project
        fields = '__all__'


class ProjectListSerializer(serializers.ModelSerializer):
    """列表用轻量序列化，不展开方案。"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    scheme_count = serializers.IntegerField(source='schemes.count', read_only=True)

    class Meta:
        model = Project
        fields = (
            'id', 'title', 'city', 'community', 'area', 'floorplan',
            'budget_min', 'budget_max', 'status', 'status_display',
            'scheme_count', 'created_at',
        )


class LeadSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ('status',)


class CustomerRequirementSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CustomerRequirement
        fields = '__all__'
        read_only_fields = ('status',)

    def validate_phone(self, value):
        value = (value or '').strip()
        if not re.fullmatch(r'1[3-9]\d{9}', value):
            raise serializers.ValidationError('请输入正确的 11 位手机号。')
        return value

    def validate(self, attrs):
        budget_min = attrs.get('budget_min')
        budget_max = attrs.get('budget_max')
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise serializers.ValidationError({'budget_min': '预算下限不能大于预算上限。'})
        return attrs


class ServiceProviderSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = ServiceProvider
        fields = '__all__'


class DesignerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designer
        fields = '__all__'


class FurnitureSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Furniture
        fields = '__all__'

    def get_image_url(self, obj):
        """商品图地址：优先本地图片文件，无图返回 None 由前端占位。"""
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class WorkflowStepSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    label = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowStep
        fields = ('id', 'order', 'kind', 'kind_display', 'label', 'is_active', 'continue_on_error')

    def get_label(self, obj):
        return obj.name or obj.get_kind_display()


class RenderWorkflowSerializer(serializers.ModelSerializer):
    """工作流对前端只暴露结构，不暴露步骤参数（属于后台编排细节）。"""

    steps = serializers.SerializerMethodField()
    step_count = serializers.SerializerMethodField()
    mode = serializers.SerializerMethodField()
    mode_display = serializers.SerializerMethodField()

    class Meta:
        model = RenderWorkflow
        fields = ('id', 'name', 'description', 'is_default', 'steps', 'step_count',
                  'mode', 'mode_display')

    def get_steps(self, obj):
        active = [s for s in obj.steps.all() if s.is_active]
        return WorkflowStepSerializer(active, many=True).data

    def get_step_count(self, obj):
        return sum(1 for s in obj.steps.all() if s.is_active)

    def get_mode(self, obj):
        """生图模式：含图生图步骤则为 img2img，否则 text2img。"""
        kinds = {s.kind for s in obj.steps.all() if s.is_active}
        return 'img2img' if WorkflowStep.Kind.EDIT_IMAGE in kinds else 'text2img'

    def get_mode_display(self, obj):
        return '图生图（保留原空间）' if self.get_mode(obj) == 'img2img' else '文生图（风格探索）'


class RenderJobSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    furnitures = FurnitureSerializer(many=True, read_only=True)
    contractor = ServiceProviderSerializer(read_only=True)
    designer = DesignerSerializer(read_only=True)
    result_url = serializers.SerializerMethodField()
    workflow_name = serializers.CharField(source='workflow.name', read_only=True, default='')
    workflow_steps = serializers.SerializerMethodField()
    render_mode = serializers.SerializerMethodField()
    module_codes = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        help_text='prompt 控制模块编码，逗号分隔，如 lighting_soft,material_wood',
    )
    applied_modules = serializers.SerializerMethodField()

    class Meta:
        model = RenderJob
        fields = '__all__'
        read_only_fields = (
            'prompt', 'negative_prompt', 'design_note', 'result_image', 'result_image_url',
            'status', 'error', 'furnitures', 'contractor', 'designer', 'prompt_modules',
            'workflow_log',
        )

    def get_result_url(self, obj):
        if obj.result_image:
            return obj.result_image.url
        return obj.result_image_url or None

    def get_applied_modules(self, obj):
        """本次生效的 prompt 控制模块（仅公开名称，不暴露提示词文本）。"""
        return [module_payload(m) for m in obj.prompt_modules.all()]

    def get_workflow_steps(self, obj):
        """工作流执行轨迹：步骤名 / 状态 / 摘要 / 耗时，供前端展示处理过程。"""
        return [
            {
                'order': item.get('order'),
                'name': item.get('name', ''),
                'status': item.get('status', ''),
                'detail': item.get('detail', ''),
                'elapsed_ms': item.get('elapsed_ms', 0),
            }
            for item in (obj.workflow_log or [])
        ]

    def get_render_mode(self, obj):
        """实际生效的生图模式：图生图成功则 img2img，退回或文生图则 text2img。"""
        for item in (obj.workflow_log or []):
            if item.get('kind') != WorkflowStep.Kind.EDIT_IMAGE:
                continue
            detail = item.get('detail') or ''
            if item.get('status') == 'ok' and '图生图成功' in detail:
                return 'img2img'
            return 'text2img'
        return 'text2img'

    # ---- 输入严格约束（与前端校验同口径，后端为最终防线）----

    def validate_room_type(self, value):
        return _validate_choice(value, ROOM_TYPES, '空间类型')

    def validate_style(self, value):
        return _validate_choice(value, STYLES, '目标风格')

    def validate_budget_tier(self, value):
        return _validate_choice(value, BUDGET_TIERS, '预算档位')

    def validate_requirement(self, value):
        text = (value or '').strip()
        if not text:
            return text
        if len(text) > REQUIREMENT_MAX_LENGTH:
            raise serializers.ValidationError(
                f'需求描述不能超过 {REQUIREMENT_MAX_LENGTH} 个字符。')
        if SENSITIVE_CONTACT_RE.search(text):
            raise serializers.ValidationError('需求描述中请勿填写手机号、邮箱、身份证等个人信息。')
        if URL_RE.search(text):
            raise serializers.ValidationError('需求描述中请勿填写链接。')
        if INJECTION_RE.search(text):
            raise serializers.ValidationError('需求描述中包含非法字符（< > { }）。')
        return text

    def validate_raw_photo(self, value):
        if value is None:
            raise serializers.ValidationError('请上传毛坯照片。')
        limits = IMAGE_CONSTRAINTS
        size = getattr(value, 'size', 0) or 0
        if size > limits['max_bytes']:
            raise serializers.ValidationError(
                f'照片不能大于 {limits["max_bytes"] // 1024 // 1024}MB。')
        if size < limits['min_bytes']:
            raise serializers.ValidationError(
                f'照片不能小于 {limits["min_bytes"] // 1024}KB，请上传更清晰的原图。')
        width, height = _image_dimensions(value)
        if width and height:
            if min(width, height) < limits['min_side']:
                raise serializers.ValidationError(
                    f'照片宽高均需不小于 {limits["min_side"]}px（当前 {width}×{height}）。')
            if max(width, height) > limits['max_side']:
                raise serializers.ValidationError(
                    f'照片宽高均需不大于 {limits["max_side"]}px（当前 {width}×{height}）。')
            ratio = max(width, height) / min(width, height)
            if ratio > limits['max_aspect_ratio']:
                raise serializers.ValidationError(
                    f'照片长宽比需在 1:{limits["max_aspect_ratio"]:.0f} ~ '
                    f'{limits["max_aspect_ratio"]:.0f}:1 之间（当前 {ratio:.1f}:1）。')
        return value

    def validate_module_codes(self, value):
        codes = parse_module_codes(value)
        if len(codes) > MAX_MODULES:
            raise serializers.ValidationError(f'最多选择 {MAX_MODULES} 个控制模块。')
        if codes:
            known = set(
                PromptModule.objects.filter(is_active=True, code__in=codes)
                .values_list('code', flat=True)
            )
            unknown = [c for c in codes if c not in known]
            if unknown:
                raise serializers.ValidationError(
                    '存在无效的控制模块：' + '、'.join(unknown))
        return ','.join(codes)


User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """用户端注册：只创建普通用户，不授予后台访问权限。"""

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    password2 = serializers.CharField(min_length=8, write_only=True)

    def validate_username(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('请输入用户名。')
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('该用户名已被注册。')
        return value

    def validate_email(self, value):
        value = (value or '').strip().lower()
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError('该邮箱已被注册。')
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password2'):
            raise serializers.ValidationError({'password2': '两次输入的密码不一致。'})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email') or '',
            password=validated_data['password'],
            is_staff=False,
            is_superuser=False,
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
