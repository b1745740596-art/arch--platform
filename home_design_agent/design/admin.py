from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Designer,
    DesignScheme,
    Furniture,
    GenerationConfig,
    Lead,
    Owner,
    Project,
    PromptModule,
    RenderJob,
    RenderWorkflow,
    ServiceProvider,
    WorkflowStep,
)

User = get_user_model()

# ---- 后台站点品牌 ----
admin.site.site_header = 'Arch_AI Platform 后台'
admin.site.site_title = 'Arch_AI Platform'
admin.site.index_title = '控制台'


# 重新注册用户，展示昵称与状态，提供搜索与筛选
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'first_name',      # 昵称
        'email',
        'is_active',
        'is_staff',
        'is_superuser',
        'last_login',
        'date_joined',
    )
    list_display_links = ('username', 'first_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    list_per_page = 25

    @admin.display(description='昵称', ordering='first_name')
    def nickname(self, obj):
        return obj.first_name or '-'


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'community', 'house_status', 'created_at')
    list_filter = ('house_status', 'city')
    search_fields = ('name', 'phone', 'community')


class DesignSchemeInline(admin.TabularInline):
    model = DesignScheme
    extra = 0
    fields = ('name', 'style', 'budget_tier', 'budget_min', 'budget_max', 'is_favorited', 'version')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'owner', 'city', 'community', 'area', 'status', 'created_at')
    list_filter = ('status', 'city')
    search_fields = ('title', 'community', 'owner__name', 'owner__phone')
    inlines = [DesignSchemeInline]


@admin.register(DesignScheme)
class DesignSchemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'style', 'budget_tier', 'budget_min', 'budget_max', 'is_favorited', 'version')
    list_filter = ('budget_tier', 'style', 'is_favorited')
    search_fields = ('name', 'style', 'project__title')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('contact_name', 'contact_phone', 'project', 'scheme', 'city', 'status', 'created_at')
    list_filter = ('status', 'city')
    search_fields = ('contact_name', 'contact_phone', 'project__title')


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'city', 'rating', 'quote_range', 'is_active')
    list_filter = ('kind', 'city', 'is_active')
    search_fields = ('name', 'city', 'qualification')


@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'city', 'years', 'rating', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'title', 'city')


@admin.register(Furniture)
class FurnitureAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'style', 'rooms', 'price', 'buy_url', 'is_active')
    list_filter = ('category', 'style', 'is_active')
    search_fields = ('name', 'brand', 'model', 'supplier')


@admin.register(RenderJob)
class RenderJobAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'project', 'style', 'room_type', 'status', 'workflow',
                    'contractor', 'designer', 'created_at')
    list_filter = ('status', 'style', 'workflow')
    search_fields = ('project__title',)
    filter_horizontal = ('furnitures', 'prompt_modules')
    readonly_fields = ('prompt', 'negative_prompt', 'error', 'status', 'workflow_trace')

    @admin.display(description='工作流执行轨迹')
    def workflow_trace(self, obj):
        """把 workflow_log 渲染成可读的步骤轨迹，便于排查每一步的耗时与降级。"""
        from django.utils.html import format_html, format_html_join

        log = obj.workflow_log or []
        if not log:
            return '—'
        icons = {'ok': '✅', 'failed': '❌', 'skipped': '⏭'}
        rows = format_html_join(
            '', '<li>{} <b>{}</b> · {} <span style="color:#888">({}ms)</span></li>',
            ((icons.get(item.get('status'), '•'), item.get('name', ''),
              item.get('detail', ''), item.get('elapsed_ms', 0)) for item in log),
        )
        return format_html('<ol style="margin:0;padding-left:18px">{}</ol>', rows)


class WorkflowStepInline(admin.TabularInline):
    """在工作流页面里直接编排步骤：调顺序、开关、改参数。"""

    model = WorkflowStep
    extra = 1
    fields = ('order', 'kind', 'name', 'params', 'is_active', 'continue_on_error')
    ordering = ('order', 'id')
    verbose_name_plural = (
        '工作流步骤（params 常用键：'
        '缩放 {"max_side":1536}；增强/调色 {"brightness":1.08,"contrast":1.12,'
        '"saturation":1.05,"sharpness":1.15}；匹配家具 {"limit":6}；'
        '装配提示词 {"use_image_analysis":true}；追加提示词 {"positive":"","negative":""}；'
        '图生图 {"preserve_space":true,"fallback_to_text2img":true,"max_side":1024}；'
        '水印 {"text":"AI 效果图 · 仅供参考","position":"bottom_right","opacity":0.45}）'
    )


@admin.register(RenderWorkflow)
class RenderWorkflowAdmin(admin.ModelAdmin):
    list_display = ('name', 'step_count', 'is_default', 'is_active', 'stop_on_error', 'updated_at')
    list_filter = ('is_default', 'is_active')
    search_fields = ('name', 'description')
    inlines = (WorkflowStepInline,)
    fieldsets = (
        ('基础', {'fields': ('name', 'description')}),
        ('生效控制', {
            'fields': ('is_default', 'is_active', 'stop_on_error'),
            'description': (
                '默认工作流唯一：勾选后其他工作流会自动取消默认。'
                '任务未指定工作流时使用默认工作流；没有默认工作流则走内置最简链路。'
            ),
        }),
    )

    @admin.display(description='步骤数')
    def step_count(self, obj):
        return obj.steps.filter(is_active=True).count()


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ('workflow', 'order', 'kind', 'name', 'is_active', 'continue_on_error')
    list_filter = ('workflow', 'kind', 'is_active')
    list_editable = ('order', 'is_active', 'continue_on_error')
    search_fields = ('name',)


@admin.register(PromptModule)
class PromptModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'group', 'weight', 'is_default', 'is_active')
    list_filter = ('group', 'is_default', 'is_active')
    search_fields = ('code', 'name', 'prompt_fragment')
    list_editable = ('weight', 'is_default', 'is_active')
    fieldsets = (
        ('基础', {'fields': ('code', 'name', 'group', 'description')}),
        ('提示词', {
            'fields': ('prompt_fragment', 'negative_fragment', 'note_fragment'),
            'description': '提示词仅后端可见，前端只提交模块 code。',
        }),
        ('生效范围', {
            'fields': ('weight', 'is_default', 'is_active',
                       'applies_to_room_types', 'applies_to_styles'),
        }),
    )


@admin.register(GenerationConfig)
class GenerationConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'model', 'api_base', 'enabled', 'updated_at')
    fieldsets = (
        ('效果图生成（图像端点）', {
            'fields': ('image_enabled', 'image_provider', 'image_api_base',
                       'image_api_key', 'image_model', 'image_size'),
            'description': 'Pollinations 免费无需 Key：provider=pollinations，base=https://image.pollinations.ai，model=flux。',
        }),
        ('设计说明（文本大模型，可选）', {
            'fields': ('enabled', 'api_base', 'api_key', 'model'),
            'description': 'DeepSeek：base=https://api.deepseek.com/v1，model=deepseek-chat，需填 API Key。',
        }),
        ('基础', {'fields': ('name',)}),
        ('提示词', {'fields': ('prompt_template',)}),
    )

    def has_add_permission(self, request):
        # 单例：已存在则不允许新增
        return not GenerationConfig.objects.exists()
