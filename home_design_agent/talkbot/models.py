from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        abstract = True


class Conversation(TimestampedModel):
    """A user-owned TalkBot sales conversation."""

    class Stage(models.TextChoices):
        ICEBREAK = 'icebreak', '破冰'
        DISCOVERY = 'discovery', '需求挖掘'
        MATCHING = 'matching', '方案匹配'
        OBJECTION = 'objection', '异议处理'
        CLOSING = 'closing', '促单'
        ORDERED = 'ordered', '已下单'
        FOLLOW_UP = 'follow_up', '后续维护'

    class Status(models.TextChoices):
        ACTIVE = 'active', '进行中'
        CONVERTED = 'converted', '已转化'
        CLOSED = 'closed', '已结束'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='talkbot_conversations',
        verbose_name='用户',
    )
    project = models.ForeignKey(
        'design.Project',
        on_delete=models.SET_NULL,
        related_name='talkbot_conversations',
        verbose_name='关联项目',
        null=True,
        blank=True,
    )
    order = models.OneToOneField(
        'design.HomeOrder',
        on_delete=models.SET_NULL,
        related_name='talkbot_conversation',
        verbose_name='转化订单',
        null=True,
        blank=True,
    )
    title = models.CharField('会话标题', max_length=120, blank=True)
    stage = models.CharField(
        '销售阶段', max_length=20, choices=Stage.choices, default=Stage.ICEBREAK,
    )
    status = models.CharField(
        '会话状态', max_length=12, choices=Status.choices, default=Status.ACTIVE,
    )
    last_action = models.CharField('最近动作', max_length=20, blank=True)
    summary = models.TextField('会话摘要', blank=True)
    workflow_log = models.JSONField('最近执行轨迹', default=list, blank=True)
    is_processing = models.BooleanField('正在生成回复', default=False, editable=False)
    processing_started_at = models.DateTimeField('开始生成时间', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = verbose_name_plural = '谈单会话'
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=('user', 'status', '-updated_at'), name='talkbot_user_status_idx'),
        ]

    def __str__(self):
        return self.title or f'谈单会话#{self.pk}'


class Message(TimestampedModel):
    """A structured user, assistant, or system message."""

    class Role(models.TextChoices):
        USER = 'user', '用户'
        ASSISTANT = 'assistant', '机器人'
        SYSTEM = 'system', '系统'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='会话',
    )
    role = models.CharField('角色', max_length=12, choices=Role.choices)
    content = models.TextField('内容')
    client_id = models.CharField(
        '客户端消息标识', max_length=64, blank=True,
        help_text='同一轮的用户消息与机器人回复共享该标识，用于请求幂等。',
    )
    intent = models.CharField('识别意图', max_length=40, blank=True)
    emotion = models.CharField('识别情绪', max_length=30, blank=True)
    question_asked = models.CharField('本轮询问字段', max_length=40, blank=True)
    metadata = models.JSONField('结构化信息', default=dict, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '谈单消息'
        ordering = ('created_at', 'id')
        indexes = [
            models.Index(fields=('conversation', 'created_at'), name='talkbot_message_time_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('conversation', 'role', 'client_id'),
                condition=~models.Q(client_id=''),
                name='talkbot_message_client_unique',
            ),
        ]

    def __str__(self):
        return f'{self.get_role_display()}：{self.content[:30]}'


class CustomerProfile(TimestampedModel):
    """Progressively collected profile used for helpful, consent-based sales guidance."""

    class Persona(models.TextChoices):
        UNKNOWN = 'unknown', '待判断'
        RATIONAL = 'rational', '理性'
        EMOTIONAL = 'emotional', '感性'
        IMPULSIVE = 'impulsive', '冲动'
        CAUTIOUS = 'cautious', '谨慎'

    class Emotion(models.TextChoices):
        NEUTRAL = 'neutral', '平静'
        ANXIOUS = 'anxious', '焦虑'
        HESITANT = 'hesitant', '犹豫'
        EXPECTANT = 'expectant', '期待'
        DISTRUSTFUL = 'distrustful', '不信任'
        DEFENSIVE = 'defensive', '防御'
        SATISFIED = 'satisfied', '满意'

    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='会话',
    )
    name = models.CharField('称呼', max_length=50, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True, db_index=True)
    city = models.CharField('城市', max_length=50, blank=True)
    community = models.CharField('小区', max_length=100, blank=True)
    area = models.DecimalField('建筑面积(㎡)', max_digits=7, decimal_places=2, null=True, blank=True)
    room_type = models.CharField('重点空间', max_length=50, blank=True)
    style = models.CharField('意向风格', max_length=50, blank=True)
    situation = models.TextField('客户处境', blank=True)
    household = models.CharField('家庭结构', max_length=120, blank=True)
    has_kids = models.BooleanField('有孩子', null=True, blank=True)
    kids_age = models.CharField('孩子年龄', max_length=50, blank=True)
    has_elderly = models.BooleanField('有老人同住', null=True, blank=True)
    pets = models.CharField('宠物', max_length=80, blank=True)
    income_tier = models.CharField('消费能力档位', max_length=30, blank=True)
    budget_min = models.PositiveIntegerField('预算下限(元)', null=True, blank=True)
    budget_max = models.PositiveIntegerField('预算上限(元)', null=True, blank=True)
    decision_power = models.CharField('决策关系', max_length=80, blank=True)
    recent_events = models.JSONField('近期事件', default=list, blank=True)
    desired_timeline = models.CharField('期望入住时间', max_length=80, blank=True)
    emotion = models.CharField(
        '当前情绪', max_length=20, choices=Emotion.choices, default=Emotion.NEUTRAL,
    )
    emotion_trace = models.JSONField('情绪轨迹', default=list, blank=True)
    persona_type = models.CharField(
        '决策类型', max_length=20, choices=Persona.choices, default=Persona.UNKNOWN,
    )
    pain_points = models.JSONField('核心顾虑', default=list, blank=True)
    trust_score = models.PositiveSmallIntegerField('信任度', default=20)
    intent_score = models.PositiveSmallIntegerField('意向度', default=20)
    missing_fields = models.JSONField('待补信息', default=list, blank=True)
    consent_to_contact = models.BooleanField('同意联系', default=False)

    class Meta:
        verbose_name = verbose_name_plural = '谈单客户画像'

    def __str__(self):
        return self.name or f'画像#{self.pk}'


class TalkWorkflow(TimestampedModel):
    """Admin-configurable per-turn TalkBot workflow."""

    name = models.CharField('工作流名称', max_length=80, unique=True)
    description = models.CharField('说明', max_length=200, blank=True)
    tags = models.JSONField('匹配标签', default=list, blank=True)
    is_default = models.BooleanField('默认工作流', default=False)
    is_active = models.BooleanField('启用', default=True)
    stop_on_error = models.BooleanField('步骤失败即终止', default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='talkbot_workflows',
        verbose_name='创建者',
    )

    class Meta:
        verbose_name = verbose_name_plural = '谈单工作流'
        ordering = ('-is_default', 'name')

    def __str__(self):
        return f'{self.name}{"（默认）" if self.is_default else ""}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            TalkWorkflow.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    def active_steps(self):
        return list(self.steps.filter(is_active=True).order_by('order', 'id'))

    @classmethod
    def resolve(cls):
        return (
            cls.objects.filter(is_active=True, is_default=True).first()
            or cls.objects.filter(is_active=True).first()
        )


class TalkStep(TimestampedModel):
    class Kind(models.TextChoices):
        INTAKE = 'intake', '接收输入'
        EMOTION = 'emotion', '情绪识别'
        INTENT = 'intent', '意图识别'
        PROFILE_UPDATE = 'profile_update', '更新画像'
        STAGE_JUDGE = 'stage_judge', '阶段判断'
        STRATEGY_PLAN = 'strategy_plan', '策略决策'
        RAG_RETRIEVE = 'rag_retrieve', '知识检索'
        LLM_GENERATE = 'llm_generate', '生成回复'
        GUARD = 'guard', '安全合规'
        OUTPUT = 'output', '输出'
        LOG = 'log', '记录轨迹'

    workflow = models.ForeignKey(
        TalkWorkflow,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='所属工作流',
    )
    order = models.PositiveSmallIntegerField('执行顺序', default=100)
    kind = models.CharField('步骤类型', max_length=30, choices=Kind.choices)
    name = models.CharField('步骤名称', max_length=80, blank=True)
    params = models.JSONField('参数', default=dict, blank=True)
    is_active = models.BooleanField('启用', default=True)
    continue_on_error = models.BooleanField('失败仍继续', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '谈单工作流步骤'
        ordering = ('workflow', 'order', 'id')

    def __str__(self):
        return f'{self.order}. {self.name or self.get_kind_display()}'


class KnowledgeBase(TimestampedModel):
    class Category(models.TextChoices):
        SCRIPT = 'script', '话术'
        CASE = 'case', '案例'
        QUOTE = 'quote', '报价'
        CRAFT = 'craft', '工艺/环保'
        FAQ = 'faq', '常见问题'
        OBJECTION = 'objection', '异议处理'

    name = models.CharField('知识库名称', max_length=100, unique=True)
    category = models.CharField('分类', max_length=20, choices=Category.choices)
    description = models.CharField('说明', max_length=200, blank=True)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '谈单知识库'
        ordering = ('category', 'name')

    def __str__(self):
        return self.name


class KnowledgeDocument(TimestampedModel):
    base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='知识库',
    )
    title = models.CharField('标题', max_length=160)
    content = models.TextField('内容')
    tags = models.JSONField('标签', default=list, blank=True)
    metadata = models.JSONField('扩展信息', default=dict, blank=True)
    embedding = models.JSONField('向量（预留）', default=list, blank=True)
    priority = models.PositiveSmallIntegerField('优先级', default=100)
    is_active = models.BooleanField('启用', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '谈单知识文档'
        ordering = ('priority', '-updated_at')

    def __str__(self):
        return self.title
