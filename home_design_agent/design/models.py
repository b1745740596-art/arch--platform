from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class TimestampedModel(models.Model):
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        abstract = True


class Owner(TimestampedModel):
    """业主（PRD 七：用户/业主）。"""

    class HouseStatus(models.TextChoices):
        NEW = 'new', '新房'
        OLD = 'old', '旧房翻新'
        RENT = 'rent', '出租房'

    name = models.CharField('姓名', max_length=50)
    phone = models.CharField('手机号', max_length=20, db_index=True)
    city = models.CharField('城市', max_length=50, blank=True)
    community = models.CharField('小区', max_length=100, blank=True)
    house_status = models.CharField(
        '房屋状态', max_length=10, choices=HouseStatus.choices, blank=True,
    )
    preference_tags = models.JSONField('偏好标签', default=list, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '业主'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.name}（{self.phone}）'


class Project(TimestampedModel):
    """房屋项目（PRD 七：房屋项目）。"""

    class Status(models.TextChoices):
        DRAFT = 'draft', '建档中'
        RECOGNIZED = 'recognized', '识别完成'
        REQUIREMENT = 'requirement', '需求澄清'
        SCHEME = 'scheme', '方案生成'
        LEAD = 'lead', '已留资'
        SIGNED = 'signed', '已签约'

    owner = models.ForeignKey(
        Owner, on_delete=models.CASCADE, related_name='projects',
        verbose_name='业主', null=True, blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='home_projects', verbose_name='关联用户', null=True, blank=True,
    )
    title = models.CharField('项目名称', max_length=100, blank=True)
    city = models.CharField('城市', max_length=50, blank=True)
    community = models.CharField('小区', max_length=100, blank=True)
    floorplan = models.ImageField('户型图', upload_to='floorplans/', null=True, blank=True)
    raw_photo = models.ImageField('毛坯照片', upload_to='raw_photos/', null=True, blank=True)
    area = models.DecimalField('面积(㎡)', max_digits=7, decimal_places=2, null=True, blank=True)
    room_structure = models.JSONField('房间结构', default=dict, blank=True)
    requirement_summary = models.JSONField('需求摘要', default=dict, blank=True)
    budget_min = models.PositiveIntegerField('预算下限(元)', null=True, blank=True)
    budget_max = models.PositiveIntegerField('预算上限(元)', null=True, blank=True)
    status = models.CharField('项目状态', max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        verbose_name = verbose_name_plural = '房屋项目'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title or f'项目#{self.pk}'


class DesignScheme(TimestampedModel):
    """设计方案（PRD 七：设计方案；PRD 5.3 每套方案展示项）。"""

    class BudgetTier(models.TextChoices):
        ECONOMY = 'economy', '经济'
        QUALITY = 'quality', '品质'
        PREMIUM = 'premium', '高端'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='schemes', verbose_name='房屋项目',
    )
    name = models.CharField('方案名称', max_length=100)
    style = models.CharField('风格定位', max_length=50, blank=True)
    budget_tier = models.CharField('预算档位', max_length=10, choices=BudgetTier.choices, default=BudgetTier.QUALITY)
    layout = models.TextField('空间布局说明', blank=True)
    highlights = models.JSONField('亮点', default=list, blank=True)
    risks = models.JSONField('风险提示', default=list, blank=True)
    suitable_for = models.CharField('适合人群', max_length=100, blank=True)
    budget_min = models.PositiveIntegerField('预算下限(元)', null=True, blank=True)
    budget_max = models.PositiveIntegerField('预算上限(元)', null=True, blank=True)
    cover_image = models.ImageField('风格图', upload_to='schemes/', null=True, blank=True)
    bom = models.JSONField('BOM初版', default=list, blank=True)
    version = models.PositiveIntegerField('版本', default=1)
    is_favorited = models.BooleanField('已收藏', default=False)
    # 可施工校验状态（PRD 九：效果图与落地差异）
    buildable_checked = models.BooleanField('已做可施工校验', default=False)
    assumptions = models.TextField('方案假设与预算口径', blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '设计方案'
        ordering = ('project', '-version')

    def __str__(self):
        return f'{self.name}（{self.get_budget_tier_display()}）'


class Lead(TimestampedModel):
    """线索/留资（PRD 5.5：预约顾问、提交联系方式）。"""

    class Status(models.TextChoices):
        NEW = 'new', '待分配'
        ASSIGNED = 'assigned', '已分配'
        CONTACTED = 'contacted', '已联系'
        CLOSED = 'closed', '已关闭'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='leads', verbose_name='房屋项目',
    )
    scheme = models.ForeignKey(
        DesignScheme, on_delete=models.SET_NULL, related_name='leads',
        verbose_name='意向方案', null=True, blank=True,
    )
    contact_name = models.CharField('联系人', max_length=50)
    contact_phone = models.CharField('联系电话', max_length=20)
    city = models.CharField('城市', max_length=50, blank=True)
    community = models.CharField('小区', max_length=100, blank=True)
    remark = models.TextField('备注', blank=True)
    status = models.CharField('状态', max_length=10, choices=Status.choices, default=Status.NEW)

    class Meta:
        verbose_name = verbose_name_plural = '线索留资'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.contact_name}（{self.contact_phone}）'


class ServiceProvider(TimestampedModel):
    """服务商（PRD 七：服务商；试点期撮合用）。"""

    class Kind(models.TextChoices):
        DESIGN = 'design', '设计团队'
        CONSTRUCTION = 'construction', '施工队'
        SUPPLIER = 'supplier', '供应商'

    name = models.CharField('名称', max_length=100)
    kind = models.CharField('类型', max_length=20, choices=Kind.choices)
    city = models.CharField('城市', max_length=50, blank=True)
    qualification = models.CharField('资质', max_length=200, blank=True)
    cases = models.JSONField('案例', default=list, blank=True)
    quote_range = models.CharField('报价区间', max_length=100, blank=True)
    rating = models.DecimalField('评分', max_digits=3, decimal_places=1, default=0)
    response_speed = models.CharField('响应速度', max_length=50, blank=True)
    deposit = models.PositiveIntegerField('保证金(元)', null=True, blank=True)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '服务商'
        ordering = ('-rating', '-created_at')

    def __str__(self):
        return f'{self.name}（{self.get_kind_display()}）'


class Designer(TimestampedModel):
    """设计师。"""

    name = models.CharField('姓名', max_length=50)
    title = models.CharField('头衔', max_length=50, blank=True)
    city = models.CharField('城市', max_length=50, blank=True)
    styles = models.JSONField('擅长风格', default=list, blank=True)
    years = models.PositiveIntegerField('从业年限', default=0)
    rating = models.DecimalField('评分', max_digits=3, decimal_places=1, default=0)
    avatar = models.ImageField('头像', upload_to='designers/', null=True, blank=True)
    intro = models.TextField('简介', blank=True)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '设计师'
        ordering = ('-rating', '-created_at')

    def __str__(self):
        return self.name


class Furniture(TimestampedModel):
    """家具/建材/家电商品（用于效果图关联展示：名称、购买链接等）。"""

    class Category(models.TextChoices):
        SOFA = 'sofa', '沙发'
        BED = 'bed', '床'
        TABLE = 'table', '桌椅'
        CABINET = 'cabinet', '柜类'
        LIGHT = 'light', '灯具'
        APPLIANCE = 'appliance', '家电'
        MATERIAL = 'material', '建材'
        DECOR = 'decor', '软装'

    name = models.CharField('商品名称', max_length=120)
    category = models.CharField('品类', max_length=20, choices=Category.choices)
    brand = models.CharField('品牌', max_length=80, blank=True)
    model = models.CharField('型号', max_length=80, blank=True)
    spec = models.CharField('规格', max_length=120, blank=True)
    style = models.CharField('适配风格', max_length=50, blank=True)
    rooms = models.JSONField('适用空间', default=list, blank=True,
        help_text='如 ["客厅","餐厅"]；留空表示不限空间。生图时按此过滤，避免客厅出现衣柜这类错配')
    price = models.PositiveIntegerField('参考价(元)', null=True, blank=True)
    buy_url = models.URLField('购买链接', blank=True)
    image = models.ImageField('商品图', upload_to='furniture/', null=True, blank=True)
    supplier = models.CharField('供应商', max_length=100, blank=True)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '家具商品'
        ordering = ('category', '-created_at')

    def __str__(self):
        return f'{self.name}（{self.get_category_display()}）'


class PromptModule(TimestampedModel):
    """Prompt 控制模块：后端预设的提示词片段，生图时按选择组装进最终 prompt。

    每个模块负责画面的一个可控维度（灯光、材质、镜头、色彩……），
    前端只传 code，真正的提示词文本由后端维护，避免把 prompt 暴露给客户端。
    """

    class Group(models.TextChoices):
        LIGHTING = 'lighting', '灯光氛围'
        MATERIAL = 'material', '材质质感'
        CAMERA = 'camera', '镜头视角'
        COLOR = 'color', '色彩基调'
        LAYOUT = 'layout', '布局收纳'
        MOOD = 'mood', '情绪风格'
        QUALITY = 'quality', '画质控制'

    code = models.SlugField('模块编码', max_length=50, unique=True,
        help_text='前端提交用的稳定标识，如 lighting_soft')
    name = models.CharField('模块名称', max_length=60)
    group = models.CharField('所属分组', max_length=20, choices=Group.choices)
    description = models.CharField('模块说明', max_length=200, blank=True,
        help_text='展示给用户的一句话说明')
    prompt_fragment = models.TextField('提示词片段',
        help_text='拼接进图像 prompt 的英文片段，如 soft diffused lighting, warm ambient glow')
    negative_fragment = models.CharField('负向片段', max_length=300, blank=True,
        help_text='需要规避的内容，如 harsh shadows')
    note_fragment = models.CharField('设计说明补充', max_length=200, blank=True,
        help_text='拼进设计说明提示词的中文补充要求')
    weight = models.PositiveSmallIntegerField('权重', default=100,
        help_text='数值越小越靠前拼接')
    is_default = models.BooleanField('默认启用', default=False,
        help_text='用户未选择任何模块时自动生效')
    is_active = models.BooleanField('启用', default=True)
    applies_to_room_types = models.JSONField('限定空间', default=list, blank=True,
        help_text='为空表示全部空间适用，如 ["客厅","餐厅"]')
    applies_to_styles = models.JSONField('限定风格', default=list, blank=True,
        help_text='为空表示全部风格适用')

    class Meta:
        verbose_name = verbose_name_plural = 'Prompt 控制模块'
        ordering = ('group', 'weight', 'id')

    def __str__(self):
        return f'{self.get_group_display()} / {self.name}'

    def matches(self, room_type: str = '', style: str = '') -> bool:
        """模块是否适用于当前空间与风格。空限定表示通用。"""
        rooms = self.applies_to_room_types or []
        styles = self.applies_to_styles or []
        if rooms and room_type and room_type not in rooms:
            return False
        if styles and style and style not in styles:
            return False
        return True


class RenderWorkflow(TimestampedModel):
    """生图工作流：后台可编排的处理流水线。

    一次渲染 = 按顺序执行若干 `WorkflowStep`：
    上传图预处理 → 画面分析 → 提示词装配 → 调用生图 → 成图后处理 → 交付。
    运营在 admin 里增删步骤、调顺序、改参数，无需改代码。
    """

    name = models.CharField('工作流名称', max_length=80, unique=True)
    description = models.CharField('说明', max_length=200, blank=True)
    is_default = models.BooleanField('默认工作流', default=False,
        help_text='任务未指定工作流时使用；只应有一个默认')
    is_active = models.BooleanField('启用', default=True)
    stop_on_error = models.BooleanField('步骤失败即终止', default=False,
        help_text='关闭时单步失败仅记录并跳过，继续后续步骤（推荐）')

    class Meta:
        verbose_name = verbose_name_plural = '生图工作流'
        ordering = ('-is_default', 'name')

    def __str__(self):
        suffix = '（默认）' if self.is_default else ''
        return f'{self.name}{suffix}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 默认工作流唯一
        if self.is_default:
            RenderWorkflow.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    @classmethod
    def resolve(cls, workflow=None):
        """取用工作流：显式指定 → 默认 → 无（走内置最简链路）。"""
        if workflow and workflow.is_active:
            return workflow
        return cls.objects.filter(is_active=True, is_default=True).first()

    def active_steps(self):
        return list(self.steps.filter(is_active=True))


class WorkflowStep(TimestampedModel):
    """工作流中的一个步骤。`kind` 决定行为，`params` 为该行为的配置。"""

    class Kind(models.TextChoices):
        # ---- 上传图预处理 ----
        VALIDATE_INPUT = 'validate_input', '输入校验'
        AUTO_ORIENT = 'auto_orient', '按 EXIF 摆正'
        RESIZE_INPUT = 'resize_input', '缩放上传图'
        ENHANCE_INPUT = 'enhance_input', '增强上传图(亮度/对比度/锐化)'
        # ---- 分析与提示词 ----
        ANALYZE_INPUT = 'analyze_input', '分析上传图(亮度/色调/朝向)'
        MATCH_FURNITURE = 'match_furniture', '匹配家具库'
        BUILD_PROMPT = 'build_prompt', '装配提示词(控制模块)'
        APPEND_PROMPT = 'append_prompt', '追加提示词片段'
        # ---- 生图 ----
        GENERATE_IMAGE = 'generate_image', '调用生图'
        EDIT_IMAGE = 'edit_image', '图生图(以上传照片为参考图)'
        # ---- 成图后处理 ----
        POSTPROCESS = 'postprocess', '成图调色(亮度/对比度/饱和度/锐化)'
        RESIZE_OUTPUT = 'resize_output', '缩放成图'
        WATERMARK = 'watermark', '添加水印'
        # ---- 交付 ----
        DESIGN_NOTE = 'design_note', '生成设计说明'
        MATCH_PROVIDER = 'match_provider', '匹配施工队/设计师'

    workflow = models.ForeignKey(
        RenderWorkflow, on_delete=models.CASCADE, related_name='steps', verbose_name='所属工作流',
    )
    order = models.PositiveSmallIntegerField('执行顺序', default=100)
    kind = models.CharField('步骤类型', max_length=30, choices=Kind.choices)
    name = models.CharField('步骤名称', max_length=80, blank=True,
        help_text='留空则用步骤类型名')
    params = models.JSONField('参数', default=dict, blank=True,
        help_text='该步骤的配置，见 admin 说明；填 {} 用默认值')
    is_active = models.BooleanField('启用', default=True)
    continue_on_error = models.BooleanField('本步失败仍继续', default=True,
        help_text='勾选时该步骤报错只记录日志并跳过')

    class Meta:
        verbose_name = verbose_name_plural = '工作流步骤'
        ordering = ('workflow', 'order', 'id')

    def __str__(self):
        return f'{self.order}. {self.name or self.get_kind_display()}'


class RenderJob(TimestampedModel):
    """效果图生成任务：毛坯照片 + 需求 → 大模型生成效果图，并关联家具/施工队/设计师。"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待生成'
        RUNNING = 'running', '生成中'
        SUCCESS = 'success', '已完成'
        FAILED = 'failed', '失败'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='render_jobs', verbose_name='房屋项目',
    )
    raw_photo = models.ImageField('毛坯照片', upload_to='raw_photos/')
    style = models.CharField('目标风格', max_length=50, blank=True)
    room_type = models.CharField('空间类型', max_length=50, blank=True)
    budget_tier = models.CharField('预算档位', max_length=10, blank=True)
    requirement = models.TextField('需求描述', blank=True)
    prompt = models.TextField('实际发送给模型的提示词', blank=True)
    negative_prompt = models.TextField('负向提示词', blank=True)
    prompt_modules = models.ManyToManyField(
        'PromptModule', blank=True, verbose_name='生效的控制模块', related_name='render_jobs',
    )
    design_note = models.TextField('AI 设计说明', blank=True,
        help_text='大模型生成的装修设计说明 / 家具搭配理由')
    result_image = models.ImageField('效果图', upload_to='renders/', null=True, blank=True)
    result_image_url = models.URLField('效果图URL', blank=True, max_length=1000)
    workflow = models.ForeignKey(
        RenderWorkflow, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='使用的工作流', related_name='render_jobs',
    )
    workflow_log = models.JSONField('工作流执行日志', default=list, blank=True,
        help_text='每个步骤的状态、耗时与摘要')
    status = models.CharField('状态', max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.TextField('错误信息', blank=True)
    # 关联展示元素
    furnitures = models.ManyToManyField(Furniture, blank=True, verbose_name='关联家具')
    contractor = models.ForeignKey(
        ServiceProvider, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='推荐施工队', related_name='render_jobs',
    )
    designer = models.ForeignKey(
        Designer, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='推荐设计师', related_name='render_jobs',
    )

    class Meta:
        verbose_name = verbose_name_plural = '效果图任务'
        ordering = ('-created_at',)

    def __str__(self):
        return f'渲染#{self.pk}（{self.get_status_display()}）'


class GenerationConfig(models.Model):
    """图像生成 API 配置（单例，后台可填 Key/端点/模型/提示词模板）。"""

    name = models.CharField('配置名', max_length=50, default='default', unique=True)
    api_base = models.CharField(
        'API Base URL', max_length=300, blank=True,
        help_text='OpenAI 兼容端点。DeepSeek 填 https://api.deepseek.com/v1',
    )
    api_key = models.CharField('API Key', max_length=300, blank=True)
    model = models.CharField('模型名', max_length=100, blank=True, default='deepseek-chat',
        help_text='文本模型（DeepSeek 无图像 API），如 deepseek-chat')
    image_size = models.CharField('图像尺寸', max_length=20, blank=True, default='1024x1024')
    # ---- 图像生成（独立于文本 chat；免费方案用 Pollinations，无需 Key）----
    image_enabled = models.BooleanField('启用真实生图', default=False,
        help_text='启用后调用下方图像端点生成真实效果图；关闭则用占位图')
    image_provider = models.CharField('图像服务商', max_length=20, blank=True, default='pollinations',
        help_text='maizi（MaiziAI 异步生图，需Key）/ pollinations（免费无Key）/ openai（需Key）')
    image_api_base = models.CharField('图像 API Base', max_length=300, blank=True,
        default='https://image.pollinations.ai',
        help_text='MaiziAI 填 https://www.maizitech.xyz/v1；Pollinations 填 https://image.pollinations.ai')
    image_api_key = models.CharField('图像 API Key', max_length=300, blank=True,
        help_text='Pollinations 免费无需填写；OpenAI 兼容端点需填')
    image_model = models.CharField('图像模型', max_length=100, blank=True, default='flux',
        help_text='MaiziAI 推荐 gpt-image-2-official；Pollinations 可填 flux / turbo')
    prompt_template = models.TextField(
        '提示词模板', blank=True,
        default=(
            '你是资深室内设计师。请为一间{room_type}给出{style}风格、'
            '预算档位「{budget_tier}」的装修设计说明。用户需求：{requirement}。'
            '请输出：1) 整体设计思路；2) 空间布局与色彩建议；3) 推荐家具与软装搭配理由；'
            '4) 施工与预算提示。语言简洁专业，使用中文，分点表述。'
        ),
    )
    enabled = models.BooleanField('启用真实调用', default=False,
        help_text='未启用时仅生成占位图与规则文案；启用后调用大模型生成设计说明')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = '生成配置'

    def __str__(self):
        return f'生成配置（{self.model or "未设置"}）'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(name='default')
        return obj


class CustomerRequirement(TimestampedModel):
    """用户需求收集：用户主动填写手机号、需求与预算，同步入库供运营跟进。"""

    class Status(models.TextChoices):
        NEW = 'new', '待跟进'
        CONTACTED = 'contacted', '已联系'
        CLOSED = 'closed', '已关闭'

    name = models.CharField('姓名', max_length=50)
    phone = models.CharField('手机号', max_length=20, db_index=True)
    city = models.CharField('城市', max_length=50, blank=True)
    community = models.CharField('小区', max_length=100, blank=True)
    room_type = models.CharField('意向空间', max_length=50, blank=True)
    style = models.CharField('意向风格', max_length=50, blank=True)
    budget_min = models.PositiveIntegerField('预算下限(元)', null=True, blank=True)
    budget_max = models.PositiveIntegerField('预算上限(元)', null=True, blank=True)
    requirement = models.TextField('需求描述', blank=True)
    status = models.CharField('跟进状态', max_length=10, choices=Status.choices, default=Status.NEW)

    class Meta:
        verbose_name = verbose_name_plural = '用户需求收集'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.name}（{self.phone}）'


class HomeReport(TimestampedModel):
    """「我的家」报告书：把一次生成任务的结构化结果快照存到用户信息下。

    每次成功输出都会创建一份报告，前端按此生成报告书并支持下单。
    """

    class Status(models.TextChoices):
        SAVED = 'saved', '已保存'
        ORDERED = 'ordered', '已下单'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='home_reports', verbose_name='用户',
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='home_reports',
        verbose_name='房屋项目',
    )
    render_job = models.ForeignKey(
        'RenderJob', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='home_reports', verbose_name='生成任务',
    )
    title = models.CharField('报告名称', max_length=120, blank=True)
    room_type = models.CharField('空间类型', max_length=50, blank=True)
    style = models.CharField('目标风格', max_length=50, blank=True)
    budget_tier = models.CharField('预算档位', max_length=10, blank=True)
    report = models.JSONField('报告内容', default=dict, blank=True)
    status = models.CharField('报告状态', max_length=10, choices=Status.choices, default=Status.SAVED)

    class Meta:
        verbose_name = verbose_name_plural = '我的家报告书'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title or f'报告#{self.pk}'


class HomeOrder(TimestampedModel):
    """「我的家」项目订单：用户在报告书页点击下单后生成，关联用户、项目与报告。"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待确认'
        CONFIRMED = 'confirmed', '已确认'
        PAID = 'paid', '已支付'
        COMPLETED = 'completed', '已完成'
        CANCELLED = 'cancelled', '已取消'

    order_no = models.CharField(
        '订单编号', max_length=32, unique=True, blank=True, editable=False,
        help_text='系统自动生成，如 HD20260817123000A1B2C3',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='home_orders', verbose_name='用户',
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='home_orders',
        verbose_name='房屋项目',
    )
    report = models.ForeignKey(
        HomeReport, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='home_orders', verbose_name='关联报告',
    )
    title = models.CharField('订单名称', max_length=120, blank=True)
    customer_name = models.CharField('客户姓名', max_length=50, blank=True)
    customer_phone = models.CharField('客户电话', max_length=20, blank=True, db_index=True)
    remark = models.TextField('客户备注', blank=True)
    items = models.JSONField('订单明细', default=list, blank=True,
        help_text='[{name, category, price, quantity, amount}]')
    amount_min = models.PositiveIntegerField('预算下限(元)', null=True, blank=True)
    amount_max = models.PositiveIntegerField('预算上限(元)', null=True, blank=True)
    total_amount = models.PositiveIntegerField('订单总价(元)', null=True, blank=True)
    payload = models.JSONField('订单快照', default=dict, blank=True)
    status = models.CharField('订单状态', max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = verbose_name_plural = '我的家项目订单'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.order_no or "订单"}（{self.get_status_display()}）'

    def _generate_order_no(self):
        prefix = timezone.localtime().strftime('HD%Y%m%d%H%M%S')
        suffix = uuid.uuid4().hex[:6].upper()
        return f'{prefix}{suffix}'

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = self._generate_order_no()
        super().save(*args, **kwargs)
